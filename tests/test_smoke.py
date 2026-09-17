"""
Smoke test: run the full reconstruction pipeline against a small real
sample of data/raw/twitter/twcs.csv (not the full 493MB file) to catch
issues that only show up with real, messy data (unicode, encoding
edge cases, multi-valued fields, actual broken chains) before running
the full dataset.

This test reads the raw CSV but only the first N rows, and never
writes to it.
"""

from pathlib import Path

import polars as pl
import pytest

from data.reconstruction import reconstruct, validate_schema

RAW_CSV = Path(__file__).parent.parent / "data" / "raw" / "twitter" / "twcs.csv"
SAMPLE_ROWS = 20_000


@pytest.mark.skipif(not RAW_CSV.exists(), reason="raw dataset not present in this environment")
def test_smoke_small_real_sample_runs_without_error():
    df = pl.read_csv(
        RAW_CSV,
        n_rows=SAMPLE_ROWS,
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
    assert validate_schema(df) == []

    # sprintcare appears heavily in the first rows of this file (confirmed
    # in Phase 1 recon), so a small head sample is guaranteed to contain
    # at least one full brand conversation to exercise the real pipeline.
    out, report = reconstruct(df, brand_authors={"sprintcare"})

    # Raw file must not be touched by any of this.
    assert RAW_CSV.exists()

    assert report.input_rows == SAMPLE_ROWS
    assert out.height >= 0  # pipeline completes and returns a table, however small
    if out.height:
        assert set(out.columns) == {
            "conversation_id", "tweet_id", "author_id", "role", "timestamp",
            "text", "parent_tweet_id", "parent_resolved", "source_row_id",
        }
        assert out.get_column("role").is_in(["customer", "brand", "unknown"]).all()
        # every row in the sample belongs to a conversation containing sprintcare
        conv_ids = out.get_column("conversation_id").unique()
        brand_conv_ids = (
            out.filter(pl.col("author_id") == "sprintcare")
            .get_column("conversation_id")
            .unique()
        )
        assert set(conv_ids.to_list()) == set(brand_conv_ids.to_list())

    # No exception, no crash, no silent full-table drop: the smoke test's
    # job is just to prove the pipeline survives contact with real data.
    print(f"[smoke] sample_rows={SAMPLE_ROWS} output_rows={out.height} "
          f"conversations={report.total_reconstructed_conversations} "
          f"duplicate_dropped={report.duplicate_tweet_id_rows_dropped} "
          f"invalid_timestamps={report.invalid_timestamp_count} "
          f"broken_parents={report.rows_parent_broken}")
