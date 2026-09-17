"""
Smoke test: run the Phase 7B resolution extraction against the real
Phase 7A output (data/processed/twitter/spotifycares_conversations.parquet),
not a synthetic fixture, to catch anything that only shows up with real
data before generating the full corpus.

Reads the Phase 7A Parquet read-only. Never writes to it. Never reads
the raw 493MB CSV.
"""

from pathlib import Path

import polars as pl
import pytest

from data.resolution_extraction import (
    BRAND_FAMILY_ACCOUNTS,
    MEGA_THREAD_CONVERSATION_IDS,
    extract_resolution_candidates,
)

RECON_PARQUET = (
    Path(__file__).parent.parent / "data" / "processed" / "twitter" / "spotifycares_conversations.parquet"
)


@pytest.mark.skipif(not RECON_PARQUET.exists(), reason="Phase 7A output not present in this environment")
def test_smoke_real_reconstructed_data():
    df = pl.read_parquet(RECON_PARQUET)
    before_mtime = RECON_PARQUET.stat().st_mtime

    candidates, report, exclusions = extract_resolution_candidates(df)

    # Phase 7A output must be untouched by running this.
    assert RECON_PARQUET.stat().st_mtime == before_mtime

    assert candidates.height > 0
    assert report.candidate_resolution_count == candidates.height

    # Every customer_message must actually come from a customer-role row,
    # and every brand_response from a brand-role row, cross-checked
    # directly against the source frame (not trusted blindly).
    src_by_id = {r["tweet_id"]: r for r in df.iter_rows(named=True)}
    sample = candidates.sample(n=min(200, candidates.height), seed=42)
    for row in sample.iter_rows(named=True):
        cust_src = src_by_id[row["customer_tweet_id"]]
        brand_src = src_by_id[row["brand_tweet_id"]]
        assert cust_src["role"] == "customer"
        assert brand_src["role"] == "brand"
        # No cross-conversation contamination.
        assert cust_src["conversation_id"] == row["conversation_id"]
        assert brand_src["conversation_id"] == row["conversation_id"]
        # Chronological ordering: reply must not precede the message it replies to.
        assert brand_src["timestamp"] >= cust_src["timestamp"]
        # The structural link must hold exactly.
        assert brand_src["parent_tweet_id"] == row["customer_tweet_id"]

    # Excluded accounts must never appear as a candidate's customer_author_id.
    candidate_customer_authors = set(candidates.get_column("customer_author_id").to_list())
    assert candidate_customer_authors.isdisjoint(BRAND_FAMILY_ACCOUNTS)

    # The known mega-thread must not appear at all in the output.
    assert candidates.filter(
        pl.col("conversation_id").is_in(list(MEGA_THREAD_CONVERSATION_IDS))
    ).height == 0

    # Multi-turn context: at least some real candidates should have
    # nonzero context (deep conversations exist in the real data).
    assert (candidates.get_column("number_of_context_messages") > 0).any()

    print(
        f"[smoke] source_rows={report.source_row_count} "
        f"conversations_inspected={report.conversations_inspected} "
        f"candidates={report.candidate_resolution_count} "
        f"dm_redirect={report.dm_redirect_count} "
        f"clarification={report.clarification_question_count} "
        f"acknowledgement={report.acknowledgement_count} "
        f"substantive={report.substantive_response_count} "
        f"excluded_conversations={report.excluded_conversations} "
        f"excluded_candidate_pairs={report.excluded_candidate_pairs} "
        f"mega_thread_would_be_candidates={report.mega_thread_would_be_candidate_count}"
    )
