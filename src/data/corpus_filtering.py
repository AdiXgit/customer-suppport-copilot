"""
Phase 7C: quality-filter the Phase 7B resolution candidates into a
canonical historical evidence corpus for the future retrieval/RAG
system.

Reads (read-only):
    data/processed/twitter/spotifycares_conversations.parquet   (Phase 7A)
    data/processed/twitter/spotifycares_resolution_candidates.parquet (Phase 7B)
    data/golden/golden_set_annotations.jsonl                    (leakage check only)
    data/golden/golden_set_candidates.jsonl                     (leakage check only)

Never modifies any of the above. Writes a NEW output:
    data/processed/twitter/spotifycares_resolution_corpus.parquet

No LLM, no embeddings, no semantic similarity. All rules are exact/
structural/deterministic, validated by manual inspection documented in
docs/PHASE_7B_RESOLUTION_CORPUS.md's Phase 7C addendum.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import polars as pl

from data.resolution_extraction import (
    BRAND_FAMILY_ACCOUNTS,
    _strip_mentions_urls,
)

# ---------------------------------------------------------------------
# Generalized broadcast-artifact detector
#
# Validated by manual inspection of 11+ conversations (see
# docs/PHASE_7B_RESOLUTION_CORPUS.md, Phase 7C addendum) before
# adoption. A conversation is flagged only when BOTH:
#   (a) it is large enough for the ratio to be meaningful (size >= 20)
#       and has an unusually high fraction of distinct customer
#       authors relative to its size (>= 0.20) -- a signature of many
#       independent people replying to one broadcast, rather than one
#       customer's deep back-and-forth; AND
#   (b) its root message is either authored by a known brand-family
#       account, or is itself a brand-authored broadcast (role=brand,
#       no parent) -- i.e. the thread did not start from a genuine
#       customer complaint.
# Both conditions together were required to avoid the false positives
# found during validation (organic multi-party "me too" / feature-
# request threads rooted in a genuine customer question, e.g.
# conversation 2211025, which have a high ratio but a customer root).
# ---------------------------------------------------------------------

BROADCAST_MIN_SIZE = 20
BROADCAST_MIN_RATIO = 0.20


@dataclass
class ConversationStats:
    conversation_id: int
    size: int
    unique_customers: int
    ratio: float
    root_author_id: str
    root_role: str
    root_is_broadcast_shaped: bool


def compute_conversation_stats(recon_df: pl.DataFrame) -> pl.DataFrame:
    """One row per conversation: size, unique customer-author count,
    the resulting ratio, and root-message identity -- used only to
    decide broadcast-artifact membership. Requires `recon_df` sorted or
    sortable by timestamp within conversation (Phase 7A output already
    provides `timestamp`)."""
    sizes = recon_df.group_by("conversation_id").agg(pl.len().alias("size"))
    cust_counts = (
        recon_df.filter(pl.col("role") == "customer")
        .group_by("conversation_id")
        .agg(pl.col("author_id").n_unique().alias("unique_customers"))
    )
    roots = (
        recon_df.sort(["conversation_id", "timestamp"])
        .group_by("conversation_id", maintain_order=True)
        .agg([
            pl.col("author_id").first().alias("root_author_id"),
            pl.col("role").first().alias("root_role"),
            pl.col("parent_tweet_id").first().alias("root_parent_tweet_id"),
        ])
    )

    stats = (
        sizes.join(cust_counts, on="conversation_id", how="left")
        .with_columns(pl.col("unique_customers").fill_null(0))
        .join(roots, on="conversation_id", how="left")
        .with_columns(
            (pl.col("unique_customers") / pl.col("size")).alias("ratio")
        )
        .with_columns(
            (
                pl.col("root_author_id").is_in(list(BRAND_FAMILY_ACCOUNTS))
                | ((pl.col("root_role") == "brand") & pl.col("root_parent_tweet_id").is_null())
            ).alias("root_is_broadcast_shaped")
        )
    )
    return stats


def identify_broadcast_conversations(
    recon_df: pl.DataFrame,
    min_size: int = BROADCAST_MIN_SIZE,
    min_ratio: float = BROADCAST_MIN_RATIO,
) -> tuple[set[int], pl.DataFrame]:
    """Returns (flagged_conversation_ids, full_stats_table) so callers
    can audit the decision, not just consume the final set."""
    stats = compute_conversation_stats(recon_df)
    flagged = stats.filter(
        (pl.col("size") >= min_size)
        & (pl.col("ratio") >= min_ratio)
        & (pl.col("root_is_broadcast_shaped"))
    )
    return set(flagged.get_column("conversation_id").to_list()), stats


# ---------------------------------------------------------------------
# Unusable-text rule (category A)
# ---------------------------------------------------------------------

def is_unusable_brand_response(text: str) -> bool:
    """A brand response with no real content once @mentions/URLs are
    stripped (a bare emoji, a bare link) -- cannot serve as retrievable
    textual evidence regardless of how it's paired."""
    return len(_strip_mentions_urls(text)) < 3


# ---------------------------------------------------------------------
# Quality flags (retained, not excluded -- category E signal, softer
# than a hard exclusion, per this phase's "do not over-filter" rule)
# ---------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def is_low_info_customer_message(text: str) -> bool:
    """<=3 real words after stripping mentions/URLs -- catches "Thanks!",
    "Thank you!", "Yes", etc. This is a FLAG, not an exclusion: these
    are genuine, verbatim historical interactions and may still carry
    retrieval value (e.g. as negative/closing examples), just with low
    diagnostic content on the customer side."""
    stripped = _strip_mentions_urls(text)
    return len(_WORD_RE.findall(stripped)) <= 3


# ---------------------------------------------------------------------
# Golden-set leakage check (exact match only -- see module docstring
# in docs/PHASE_7B_RESOLUTION_CORPUS.md's Phase 7C addendum for why
# normalized near-duplicates are reported but NOT excluded)
# ---------------------------------------------------------------------

def load_golden_leakage_keys(
    golden_annotations_path: str | Path,
    golden_candidates_path: str | Path,
) -> tuple[set[int], set[str]]:
    """Returns (golden_tweet_ids, golden_customer_messages) -- the two
    exact-match leakage keys. Reads both golden files (never writes to
    either)."""
    golden_ann = {}
    with open(golden_annotations_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                golden_ann[r["example_id"]] = r

    golden_meta = {}
    with open(golden_candidates_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                golden_meta[r["example_id"]] = r

    tweet_ids = {
        golden_meta[eid]["tweet_id"]
        for eid in golden_ann
        if eid in golden_meta
    }
    messages = {ann["customer_message"] for ann in golden_ann.values()}
    return tweet_ids, messages


def _normalize_for_near_dup_check(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"@\w+", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------

@dataclass
class FilterExclusionEntry:
    exclusion_reason: str
    conversation_id: int | None
    affected_candidate_count: int
    example_resolution_ids: list = field(default_factory=list)


@dataclass
class CorpusQualityReport:
    input_candidate_count: int = 0
    output_corpus_count: int = 0
    retained_count: int = 0
    excluded_count: int = 0
    exclusion_reason_counts: dict = field(default_factory=dict)
    response_type_distribution_before: dict = field(default_factory=dict)
    response_type_distribution_after: dict = field(default_factory=dict)
    duplicate_resolution_ids_found: int = 0
    exact_duplicate_customer_message_groups: int = 0
    exact_duplicate_customer_message_rows: int = 0
    exact_duplicate_brand_response_groups: int = 0
    exact_duplicate_brand_response_rows: int = 0
    exact_duplicate_pair_groups: int = 0
    broadcast_investigation: dict = field(default_factory=dict)
    golden_set_leakage: dict = field(default_factory=dict)
    quality_flag_counts: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")


CORPUS_COLUMNS = [
    "resolution_id",
    "conversation_id",
    "customer_tweet_id",
    "customer_author_id",
    "customer_message",
    "customer_timestamp",
    "brand_tweet_id",
    "brand_author_id",
    "brand_response",
    "brand_timestamp",
    "response_type",
    "number_of_context_messages",
    "context_messages_json",
    "intent",
    "low_info_customer_message",
    "cross_brand_response",
]


def filter_corpus(
    candidates_df: pl.DataFrame,
    recon_df: pl.DataFrame,
    golden_tweet_ids: set[int],
    golden_messages: set[str],
) -> tuple[pl.DataFrame, CorpusQualityReport, list[FilterExclusionEntry]]:
    report = CorpusQualityReport()
    report.input_candidate_count = candidates_df.height

    before_counts = candidates_df.get_column("response_type").value_counts().to_dicts()
    report.response_type_distribution_before = {d["response_type"]: d["count"] for d in before_counts}

    # ---- Duplicate resolution IDs (defensive; expect 0) ----
    n_before = candidates_df.height
    deduped = candidates_df.unique(subset=["resolution_id"], keep="first", maintain_order=True)
    report.duplicate_resolution_ids_found = n_before - deduped.height
    candidates_df = deduped

    # ---- Exact duplicate diagnostics (reported, NOT excluded -- see
    # docs: genuinely separate interactions with identical text are
    # preserved) ----
    dup_cust = (
        candidates_df.group_by("customer_message").agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    )
    report.exact_duplicate_customer_message_groups = dup_cust.height
    report.exact_duplicate_customer_message_rows = int(dup_cust.get_column("n").sum()) if dup_cust.height else 0

    dup_brand = (
        candidates_df.group_by("brand_response").agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    )
    report.exact_duplicate_brand_response_groups = dup_brand.height
    report.exact_duplicate_brand_response_rows = int(dup_brand.get_column("n").sum()) if dup_brand.height else 0

    dup_pair = (
        candidates_df.group_by(["customer_message", "brand_response"]).agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    )
    report.exact_duplicate_pair_groups = dup_pair.height

    # ---- Broadcast-artifact investigation (generalized detector) ----
    broadcast_ids, conv_stats = identify_broadcast_conversations(recon_df)
    report.broadcast_investigation = {
        "min_size_threshold": BROADCAST_MIN_SIZE,
        "min_ratio_threshold": BROADCAST_MIN_RATIO,
        "conversations_inspected_size_ge_threshold": int(
            conv_stats.filter(pl.col("size") >= BROADCAST_MIN_SIZE).height
        ),
        "conversations_flagged": len(broadcast_ids),
        "flagged_conversation_ids": sorted(broadcast_ids),
        "known_mega_thread_included": 83694 in broadcast_ids,
    }

    # ---- Golden-set leakage (exact match) ----
    exact_tid_matches = candidates_df.filter(pl.col("customer_tweet_id").is_in(list(golden_tweet_ids)))
    exact_text_matches = candidates_df.filter(pl.col("customer_message").is_in(list(golden_messages)))
    leaked_resolution_ids = set(exact_tid_matches.get_column("resolution_id").to_list()) | set(
        exact_text_matches.get_column("resolution_id").to_list()
    )

    golden_norm = {_normalize_for_near_dup_check(m) for m in golden_messages}
    normalized_matches = candidates_df.filter(
        pl.col("customer_message").map_elements(_normalize_for_near_dup_check, return_dtype=pl.Utf8).is_in(list(golden_norm))
    )
    normalized_only = set(normalized_matches.get_column("resolution_id").to_list()) - leaked_resolution_ids

    report.golden_set_leakage = {
        "golden_examples_checked": len(golden_messages),
        "exact_tweet_id_matches_candidate_rows": int(exact_tid_matches.height),
        "exact_text_matches_candidate_rows": int(exact_text_matches.height),
        "unique_golden_tweet_ids_with_a_candidate": len(
            golden_tweet_ids & set(candidates_df.get_column("customer_tweet_id").to_list())
        ),
        "total_excluded_for_leakage": len(leaked_resolution_ids),
        "additional_normalized_only_matches_NOT_excluded": len(normalized_only),
        "normalized_only_example_resolution_ids": sorted(normalized_only)[:10],
        "policy": (
            "Exact tweet_id / exact customer_message matches are excluded "
            "from the corpus (true leakage of the same historical event). "
            "Normalized-text-only matches are reported but NOT excluded: "
            "manual inspection showed these are short, generic phrases "
            "('I need help with my account', 'Come on') independently "
            "used by different real customers on different tweets -- "
            "excluding them would violate the 'preserve genuinely "
            "separate interactions' rule for no real leakage benefit."
        ),
    }

    # ---- Apply exclusions ----
    exclusion_entries: list[FilterExclusionEntry] = []

    is_broadcast = candidates_df.get_column("conversation_id").is_in(list(broadcast_ids))
    is_unusable_resp = candidates_df.get_column("brand_response").map_elements(
        is_unusable_brand_response, return_dtype=pl.Boolean
    )
    is_leaked = candidates_df.get_column("resolution_id").is_in(list(leaked_resolution_ids))

    excluded_mask = is_broadcast | is_unusable_resp | is_leaked

    for reason, mask in (
        ("broadcast_artifact", is_broadcast),
        ("unusable_brand_response", is_unusable_resp),
        ("golden_set_overlap", is_leaked),
    ):
        subset = candidates_df.filter(mask)
        if subset.height == 0:
            exclusion_entries.append(FilterExclusionEntry(reason, None, 0, []))
            continue
        conv_id = None
        if reason == "broadcast_artifact":
            conv_id = None  # spans many conversations; see broadcast_investigation for the full list
        exclusion_entries.append(FilterExclusionEntry(
            exclusion_reason=reason,
            conversation_id=conv_id,
            affected_candidate_count=int(subset.height),
            example_resolution_ids=subset.get_column("resolution_id").to_list()[:10],
        ))

    retained = candidates_df.filter(~excluded_mask)

    # ---- Quality flags on retained rows (not exclusions) ----
    retained = retained.with_columns([
        pl.col("customer_message").map_elements(is_low_info_customer_message, return_dtype=pl.Boolean).alias("low_info_customer_message"),
        (pl.col("brand_author_id") != "SpotifyCares").alias("cross_brand_response"),
    ])

    retained = retained.select(CORPUS_COLUMNS).sort(
        ["conversation_id", "brand_timestamp", "brand_tweet_id"], nulls_last=True
    )

    after_counts = retained.get_column("response_type").value_counts().to_dicts()
    report.response_type_distribution_after = {d["response_type"]: d["count"] for d in after_counts}

    report.output_corpus_count = retained.height
    report.retained_count = retained.height
    report.excluded_count = int(excluded_mask.sum())
    report.exclusion_reason_counts = {
        e.exclusion_reason: e.affected_candidate_count for e in exclusion_entries
    }
    report.quality_flag_counts = {
        "low_info_customer_message": int(retained.get_column("low_info_customer_message").sum()),
        "cross_brand_response": int(retained.get_column("cross_brand_response").sum()),
    }

    report.notes.append(
        "exclusion_reason_counts may not sum exactly to excluded_count "
        "because a candidate can match more than one exclusion rule "
        "(e.g. a broadcast-artifact conversation could also contain an "
        "unusable brand response) -- excluded_count is the count of "
        "unique candidates removed (OR of all rules), not a sum."
    )
    report.notes.append(
        "quality_flag_counts describe RETAINED rows only -- these are "
        "metadata for future retrieval-time filtering, not exclusions. "
        "response_type is unchanged from Phase 7B and is itself never "
        "treated as a quality signal (dm_redirect/acknowledgement/"
        "clarification_question are all retained where not otherwise "
        "excluded)."
    )

    return retained, report, exclusion_entries


def run_full_filtering(
    candidates_path: str | Path,
    reconstruction_path: str | Path,
    golden_annotations_path: str | Path,
    golden_candidates_path: str | Path,
    output_path: str | Path,
    quality_report_path: str | Path,
) -> CorpusQualityReport:
    candidates_df = pl.read_parquet(candidates_path)
    recon_df = pl.read_parquet(reconstruction_path)
    golden_tweet_ids, golden_messages = load_golden_leakage_keys(
        golden_annotations_path, golden_candidates_path
    )

    retained, report, exclusion_entries = filter_corpus(
        candidates_df, recon_df, golden_tweet_ids, golden_messages
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    retained.write_parquet(output_path)

    report.to_json(quality_report_path)

    return report
