"""
Smoke test: run Phase 7C filtering against the real Phase 7A/7B outputs
and the real golden set (read-only) before generating the full filtered
corpus.
"""

from pathlib import Path

import polars as pl
import pytest

from data.corpus_filtering import filter_corpus, load_golden_leakage_keys

RECON_PATH = Path(__file__).parent.parent / "data" / "processed" / "twitter" / "spotifycares_conversations.parquet"
CAND_PATH = Path(__file__).parent.parent / "data" / "processed" / "twitter" / "spotifycares_resolution_candidates.parquet"
GOLDEN_ANN_PATH = Path(__file__).parent.parent / "data" / "golden" / "golden_set_annotations.jsonl"
GOLDEN_CAND_PATH = Path(__file__).parent.parent / "data" / "golden" / "golden_set_candidates.jsonl"

_ALL_PRESENT = RECON_PATH.exists() and CAND_PATH.exists() and GOLDEN_ANN_PATH.exists() and GOLDEN_CAND_PATH.exists()


@pytest.mark.skipif(not _ALL_PRESENT, reason="Phase 7A/7B outputs or golden set not present in this environment")
def test_smoke_real_data_filtering():
    recon = pl.read_parquet(RECON_PATH)
    candidates = pl.read_parquet(CAND_PATH)
    golden_tweet_ids, golden_messages = load_golden_leakage_keys(GOLDEN_ANN_PATH, GOLDEN_CAND_PATH)
    assert len(golden_messages) == 200

    before_cand_mtime = CAND_PATH.stat().st_mtime
    before_recon_mtime = RECON_PATH.stat().st_mtime
    before_golden_ann_mtime = GOLDEN_ANN_PATH.stat().st_mtime

    retained, report, exclusion_entries = filter_corpus(candidates, recon, golden_tweet_ids, golden_messages)

    # Phase 7A/7B outputs and golden set must be untouched by running this.
    assert CAND_PATH.stat().st_mtime == before_cand_mtime
    assert RECON_PATH.stat().st_mtime == before_recon_mtime
    assert GOLDEN_ANN_PATH.stat().st_mtime == before_golden_ann_mtime

    assert retained.height > 0
    assert retained.height < candidates.height  # filtering must remove something

    # No excluded conversation may appear in the output.
    broadcast_ids = set(report.broadcast_investigation["flagged_conversation_ids"])
    assert candidates.filter(pl.col("conversation_id").is_in(list(broadcast_ids))).height > 0  # sanity: rule fires on real data
    assert retained.filter(pl.col("conversation_id").is_in(list(broadcast_ids))).height == 0

    # No golden-set tweet_id may appear as a customer_tweet_id in the output.
    leaked_in_output = retained.filter(pl.col("customer_tweet_id").is_in(list(golden_tweet_ids)))
    assert leaked_in_output.height == 0

    # Spot-check representative examples across response types survive filtering.
    for rt in ["substantive_response", "dm_redirect", "clarification_question", "acknowledgement"]:
        assert retained.filter(pl.col("response_type") == rt).height > 0, f"{rt} should not be fully wiped out"

    # Multi-turn metadata still present.
    assert (retained.get_column("number_of_context_messages") > 0).any()

    print(
        f"[smoke] input={report.input_candidate_count} output={report.output_corpus_count} "
        f"excluded={report.excluded_count} broadcast_conversations={len(broadcast_ids)} "
        f"golden_overlap_excluded={report.golden_set_leakage['total_excluded_for_leakage']} "
        f"unusable_brand_response={report.exclusion_reason_counts.get('unusable_brand_response')}"
    )
