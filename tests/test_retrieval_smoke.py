"""
Real-data smoke test for the Phase 8 retrieval layer (Step 13).

Loads the actual built index/metadata/vectors under data/retrieval/ (if
present) and runs representative queries. Does NOT rebuild the index
and does NOT touch the golden set at all -- golden isolation is
verified independently by scripts/build_retrieval_index.py's own
verify_golden_exclusion step and recorded in
spotifycares_retrieval_quality.json.
"""

import json
from pathlib import Path

import polars as pl
import pytest

from retrieval.retriever import Retriever, OTHER_INTENT

REPO_ROOT = Path(__file__).parent.parent
INDEX_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares.index"
METADATA_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_metadata.parquet"
VECTORS_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_vectors.npy"
QUALITY_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_retrieval_quality.json"
GOLDEN_CANDIDATES_PATH = REPO_ROOT / "data" / "golden" / "golden_set_candidates.jsonl"

_ALL_PRESENT = INDEX_PATH.exists() and METADATA_PATH.exists() and VECTORS_PATH.exists()

pytestmark = pytest.mark.skipif(not _ALL_PRESENT, reason="Retrieval index not built in this environment")


@pytest.fixture(scope="module")
def retriever():
    return Retriever(INDEX_PATH, METADATA_PATH, VECTORS_PATH)


def test_index_loads_and_sizes_match(retriever):
    assert len(retriever) > 0
    assert retriever.index.ntotal == len(retriever)
    assert retriever.vectors.shape[0] == len(retriever)


REPRESENTATIVE_QUERIES = [
    ("I can't log in, it keeps saying my password is wrong", "Account Access & Login"),
    ("my account was hacked and someone changed my email", "Account Security"),
    ("I was charged twice for my premium subscription this month", "Premium Subscription & Billing"),
    ("the app keeps crashing every time I try to play a song", "App & Playback Technical Issues"),
    ("why isn't the new album available on Spotify", "Content Availability & Catalog Accuracy"),
    ("please add a dark mode option to the app", "Feature Request & Product Feedback"),
    ("this is the worst customer service I've ever experienced", "General Complaint / Service Dissatisfaction"),
    ("when will Spotify be available in my country", "Country/Market Availability Inquiry"),
    ("ok thanks", OTHER_INTENT),
]


@pytest.mark.parametrize("query,intent", REPRESENTATIVE_QUERIES)
def test_representative_query_returns_sensible_results(retriever, query, intent):
    results = retriever.search(query, k=5)
    assert len(results) > 0
    for r in results:
        assert -1.0001 <= r["similarity_score"] <= 1.0001
        assert r["retrieval_id"]
        assert r["conversation_id"] is not None
    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("query,intent", REPRESENTATIVE_QUERIES)
def test_intent_filtered_query_matches_requested_intent_or_falls_back(retriever, query, intent):
    results = retriever.search(query, k=5, intent=intent)
    assert len(results) > 0
    if intent != OTHER_INTENT and intent in retriever._intent_positions and len(retriever._intent_positions[intent]) > 0:
        for r in results:
            assert r["primary_intent"] == intent


def test_no_golden_customer_messages_are_indexed(retriever):
    with open(GOLDEN_CANDIDATES_PATH, encoding="utf-8") as f:
        golden = [json.loads(line) for line in f if line.strip()]
    golden_tweet_ids = {g["tweet_id"] for g in golden if g.get("tweet_id") is not None}
    indexed_tweet_ids = set(retriever.metadata["customer_tweet_id"].to_list())
    overlap = golden_tweet_ids & indexed_tweet_ids
    assert overlap == set(), f"Golden tweet_ids leaked into the retrieval index: {overlap}"


def test_golden_message_cannot_retrieve_itself_from_index(retriever):
    """Isolation test only (Step 6): golden text used purely to confirm
    it is absent, never to tune retrieval behavior."""
    with open(GOLDEN_CANDIDATES_PATH, encoding="utf-8") as f:
        golden = [json.loads(line) for line in f if line.strip()]
    sample = golden[:5]
    for g in sample:
        results = retriever.search(g["customer_message"], k=5)
        retrieved_texts = {r["customer_message"] for r in results}
        assert g["customer_message"] not in retrieved_texts


def test_quality_report_confirms_zero_golden_leakage():
    report = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    assert report["excluded_golden_leakage"]["unique_rows_excluded_for_golden_leakage"] >= 0
    # The build script's OWN found-leakage count (independent of any prior
    # phase's exclusion) should be zero, since Phase 7C already excluded
    # golden overlaps before Phase 8 ever ran.
    assert report["excluded_golden_leakage"]["exact_tweet_id_matches_found_in_corpus"] == 0
    assert report["excluded_golden_leakage"]["exact_text_matches_found_in_corpus"] == 0
