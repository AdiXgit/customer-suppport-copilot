"""
Deterministic, auditable conversation-reconstruction pipeline for the
Customer Support on Twitter (TWCS) dataset.

Reconstructs conversations using ONLY the dataset's own structural
relationship field (`in_response_to_tweet_id`, a child -> parent
pointer) -- never text similarity, never arbitrary time windows. A
conversation's `conversation_id` is the tweet_id of its root: the
earliest ancestor reachable by following `in_response_to_tweet_id`
backward whose own parent is missing or doesn't exist in the dataset.

This module contains no I/O against the real raw CSV except in
`read_raw_csv` (a thin wrapper) and `run_full_reconstruction` (the
production entry point). Every other function operates on an in-memory
polars DataFrame, so it can be exercised in tests against tiny
synthetic fixtures without touching `data/raw/twitter/twcs.csv`.

`data/raw/twitter/twcs.csv` is NEVER modified by this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import duckdb
import polars as pl

REQUIRED_COLUMNS = [
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "response_tweet_id",
    "in_response_to_tweet_id",
]

# Twitter's native created_at format, e.g. "Tue Oct 31 22:10:47 +0000 2017".
TIMESTAMP_FORMAT = "%a %b %d %H:%M:%S %z %Y"

# Recursion depth safety cap for the parent-chain closure. The dataset's
# observed max conversation size is a few hundred (a breadth artifact,
# not depth), and real reply chains are shallow (well under 100). This
# guards against an unexpected cycle causing runaway recursion rather
# than failing loudly.
MAX_CHAIN_DEPTH = 2000

OUTPUT_COLUMNS = [
    "conversation_id",
    "tweet_id",
    "author_id",
    "role",
    "timestamp",
    "text",
    "parent_tweet_id",
    "parent_resolved",
    "source_row_id",
]


class SchemaError(ValueError):
    """Raised when the input DataFrame is missing required columns."""


@dataclass
class QualityReport:
    """All data-quality figures the reconstruction pipeline reports.

    Nothing here represents rows the pipeline silently discarded without
    a count -- every drop has a corresponding field.
    """

    input_rows: int = 0
    missing_tweet_id_rows_dropped: int = 0
    duplicate_tweet_id_rows_dropped: int = 0
    duplicate_tweet_ids_sample: list = field(default_factory=list)
    missing_required_field_counts: dict = field(default_factory=dict)
    invalid_timestamp_count: int = 0
    missing_inbound_count: int = 0
    rows_with_parent_pointer: int = 0
    rows_parent_resolved: int = 0
    rows_parent_broken: int = 0
    total_conversations_all_brands: int = 0
    total_spotifycares_rows: int = 0
    total_reconstructed_conversations: int = 0
    customer_messages: int = 0
    brand_messages: int = 0
    unknown_role_messages: int = 0
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")


def validate_schema(df: pl.DataFrame) -> list[str]:
    """Return the list of required columns missing from df (empty if OK)."""
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


def read_raw_csv(path: str | Path) -> pl.DataFrame:
    """Read the raw TWCS CSV. Read-only; never writes to `path`."""
    df = pl.read_csv(
        path,
        schema_overrides={
            "tweet_id": pl.Int64,
            "author_id": pl.Utf8,
            "inbound": pl.Boolean,
            "created_at": pl.Utf8,
            "text": pl.Utf8,
            "response_tweet_id": pl.Utf8,
            "in_response_to_tweet_id": pl.Int64,
        },
    )
    missing = validate_schema(df)
    if missing:
        raise SchemaError(f"Input CSV is missing required columns: {missing}")
    return df


def add_source_row_id(df: pl.DataFrame) -> pl.DataFrame:
    """Assign a stable, deterministic row identifier based on original
    file/DataFrame order, before any filtering or reordering happens."""
    return df.with_row_index(name="source_row_id")


def find_missing_required_fields(df: pl.DataFrame) -> dict[str, int]:
    """Null counts for the fields that should always be populated per the
    known TWCS schema (tweet_id, author_id, inbound, created_at, text)."""
    core_fields = ["tweet_id", "author_id", "inbound", "created_at", "text"]
    counts = df.select(core_fields).null_count().to_dicts()[0]
    return {k: int(v) for k, v in counts.items()}


def drop_missing_tweet_id(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """A row with no tweet_id cannot be keyed into the reply graph at
    all -- this is the one case where a row must be dropped rather than
    merely flagged, because there is nothing to attach it to. The drop
    count is always reported, never silent."""
    n_before = df.height
    out = df.filter(pl.col("tweet_id").is_not_null())
    return out, n_before - out.height


def deduplicate_tweet_ids(df: pl.DataFrame) -> tuple[pl.DataFrame, int, list[int]]:
    """Detect duplicate tweet_id values. Keeps the first occurrence by
    `source_row_id` (deterministic) and reports how many rows were
    dropped and which tweet_ids were affected (capped sample)."""
    if "source_row_id" not in df.columns:
        raise ValueError("deduplicate_tweet_ids requires source_row_id; call add_source_row_id first")

    dup_ids = (
        df.group_by("tweet_id")
        .agg(pl.len().alias("n"))
        .filter(pl.col("n") > 1)
        .get_column("tweet_id")
        .to_list()
    )
    if not dup_ids:
        return df, 0, []

    deduped = (
        df.sort("source_row_id")
        .unique(subset=["tweet_id"], keep="first", maintain_order=True)
    )
    n_dropped = df.height - deduped.height
    return deduped, n_dropped, sorted(dup_ids)[:50]


def parse_timestamps(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Parse `created_at` (Twitter's fixed format) into a `timestamp`
    column. Rows where created_at is present but fails to parse are
    counted as invalid (the row is kept, `timestamp` is null)."""
    out = df.with_columns(
        pl.col("created_at")
        .str.strptime(pl.Datetime(time_zone="UTC"), TIMESTAMP_FORMAT, strict=False)
        .alias("timestamp")
    )
    invalid = out.filter(
        pl.col("created_at").is_not_null() & pl.col("timestamp").is_null()
    ).height
    return out, invalid


def assign_roles(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Assign role directly from `inbound` (True=customer, False=brand)
    per the dataset's own documented field -- no inference from
    author_id shape. Rows with a null `inbound` get role='unknown' and
    are counted, not silently dropped."""
    out = df.with_columns(
        pl.when(pl.col("inbound").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("inbound"))
        .then(pl.lit("customer"))
        .otherwise(pl.lit("brand"))
        .alias("role")
    )
    missing_inbound = out.filter(pl.col("inbound").is_null()).height
    return out, missing_inbound


def compute_conversation_roots(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Compute each row's conversation root via the dataset's own
    `in_response_to_tweet_id` structural pointer, using a SQL recursive
    CTE (DuckDB) over the parent-child edges -- a purely structural,
    auditable closure computation, not a heuristic.

    Adds:
      - conversation_id: the tweet_id of the resolved root
      - parent_tweet_id: alias of in_response_to_tweet_id (kept for
        output-schema clarity)
      - parent_resolved: True if in_response_to_tweet_id is null (no
        parent claimed) or points to a tweet_id that exists in this
        dataset; False if it points to a tweet_id that is absent
        (a broken chain link)

    Requires tweet_id to be unique in df (call deduplicate_tweet_ids
    first).
    """
    edges = df.select(["tweet_id", "in_response_to_tweet_id"])

    con = duckdb.connect()
    query = f"""
        WITH RECURSIVE known_ids AS (
            SELECT tweet_id FROM edges
        ),
        chain(tweet_id, conversation_id, depth) AS (
            SELECT
                tweet_id,
                tweet_id AS conversation_id,
                0 AS depth
            FROM edges
            WHERE in_response_to_tweet_id IS NULL
               OR in_response_to_tweet_id NOT IN (SELECT tweet_id FROM known_ids)

            UNION ALL

            SELECT
                e.tweet_id,
                c.conversation_id,
                c.depth + 1
            FROM edges e
            JOIN chain c ON e.in_response_to_tweet_id = c.tweet_id
            WHERE c.depth < {MAX_CHAIN_DEPTH}
        )
        SELECT tweet_id, conversation_id FROM chain
    """
    roots = con.execute(query).pl()
    con.close()

    if roots.height != df.height:
        # Should be impossible given the recursion's base case covers every
        # row with no resolvable parent, and the recursive case is reached
        # by exactly one edge per child -- but this is a correctness
        # invariant worth asserting loudly rather than silently truncating.
        raise RuntimeError(
            f"Conversation-root resolution produced {roots.height} rows "
            f"for {df.height} input rows -- a cycle or unresolved row was "
            f"likely hit (see MAX_CHAIN_DEPTH)."
        )

    out = df.join(roots, on="tweet_id", how="left").rename(
        {"in_response_to_tweet_id": "parent_tweet_id"}
    )

    known_ids = set(df.get_column("tweet_id").to_list())
    out = out.with_columns(
        (
            pl.col("parent_tweet_id").is_null()
            | pl.col("parent_tweet_id").is_in(list(known_ids))
        ).alias("parent_resolved")
    )

    stats = {
        "rows_with_parent_pointer": int(df.filter(pl.col("in_response_to_tweet_id").is_not_null()).height),
        "rows_parent_resolved": int(out.filter(pl.col("parent_resolved")).height),
        "rows_parent_broken": int(out.filter(~pl.col("parent_resolved")).height),
        "total_conversations_all_rows": int(out.get_column("conversation_id").n_unique()),
    }
    return out, stats


def filter_to_brand_conversations(df: pl.DataFrame, brand_authors: set[str]) -> pl.DataFrame:
    """Keep only rows belonging to a conversation (by conversation_id)
    that contains at least one message authored by one of the given
    brand handles. This is the "restrict to SpotifyCares interactions"
    step, applied structurally (by shared conversation_id), not by
    filtering rows individually on author_id -- so the customer side of
    a SpotifyCares conversation is retained too."""
    qualifying_ids = (
        df.filter(pl.col("author_id").is_in(list(brand_authors)))
        .get_column("conversation_id")
        .unique()
        .to_list()
    )
    return df.filter(pl.col("conversation_id").is_in(qualifying_ids))


def finalize_output_schema(df: pl.DataFrame) -> pl.DataFrame:
    """Select and deterministically order the output columns/rows."""
    out = df.select(OUTPUT_COLUMNS)
    return out.sort(
        ["conversation_id", "timestamp", "tweet_id"],
        nulls_last=True,
    )


def reconstruct(df_raw: pl.DataFrame, brand_authors: set[str]) -> tuple[pl.DataFrame, QualityReport]:
    """Top-level, fully deterministic orchestration. Used identically by
    unit tests (tiny fixtures), the smoke test (a small real sample),
    and the production script (the full raw CSV)."""
    report = QualityReport()
    report.input_rows = df_raw.height

    missing_cols = validate_schema(df_raw)
    if missing_cols:
        raise SchemaError(f"Input is missing required columns: {missing_cols}")

    report.missing_required_field_counts = find_missing_required_fields(df_raw)

    df = add_source_row_id(df_raw)

    df, n_dropped_missing_id = drop_missing_tweet_id(df)
    report.missing_tweet_id_rows_dropped = n_dropped_missing_id
    if n_dropped_missing_id:
        report.notes.append(
            f"Dropped {n_dropped_missing_id} row(s) with a null tweet_id "
            f"(cannot be keyed into the reply graph)."
        )

    df, n_dup_dropped, dup_sample = deduplicate_tweet_ids(df)
    report.duplicate_tweet_id_rows_dropped = n_dup_dropped
    report.duplicate_tweet_ids_sample = dup_sample
    if n_dup_dropped:
        report.notes.append(
            f"Dropped {n_dup_dropped} duplicate-tweet_id row(s), keeping the "
            f"first occurrence by source_row_id. Affected tweet_ids (sample, "
            f"max 50): {dup_sample}"
        )

    df, invalid_ts = parse_timestamps(df)
    report.invalid_timestamp_count = invalid_ts

    df, missing_inbound = assign_roles(df)
    report.missing_inbound_count = missing_inbound

    df, chain_stats = compute_conversation_roots(df)
    report.rows_with_parent_pointer = chain_stats["rows_with_parent_pointer"]
    report.rows_parent_resolved = chain_stats["rows_parent_resolved"]
    report.rows_parent_broken = chain_stats["rows_parent_broken"]
    report.total_conversations_all_brands = chain_stats["total_conversations_all_rows"]

    df = filter_to_brand_conversations(df, brand_authors)

    df = finalize_output_schema(df)

    report.total_spotifycares_rows = df.height
    report.total_reconstructed_conversations = int(df.get_column("conversation_id").n_unique())
    report.customer_messages = int(df.filter(pl.col("role") == "customer").height)
    report.brand_messages = int(df.filter(pl.col("role") == "brand").height)
    report.unknown_role_messages = int(df.filter(pl.col("role") == "unknown").height)

    return df, report


def run_full_reconstruction(
    input_path: str | Path,
    output_path: str | Path,
    quality_report_path: str | Path,
    brand_authors: set[str],
) -> QualityReport:
    """Production entry point: read the real raw CSV (read-only),
    reconstruct, write the processed Parquet and the JSON quality
    report. Never modifies `input_path`."""
    df_raw = read_raw_csv(input_path)
    df_out, report = reconstruct(df_raw, brand_authors)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.write_parquet(output_path)

    report.to_json(quality_report_path)
    return report
