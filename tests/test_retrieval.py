"""
Unit tests for src/retrieval/*.

Uses small synthetic fixtures built in-memory -- never the real
41,092-row corpus (covered by tests/test_retrieval_smoke.py) and never
the golden set as training/tuning data (the one golden-related test
here checks EXCLUSION logic using synthetic stand-in rows, not real
golden content).
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from retrieval.embeddings import EMBEDDING_DIMENSION, embed_texts  # noqa: E402
from retrieval.index import build_faiss_index, build_retrieval_records, build_embedding_text  # noqa: E402
from retrieval.retriever import Retriever, OTHER_INTENT  # noqa: E402


def _synthetic_corpus_df(n=None):
    rows = [
        {
            "resolution_id": "RES-1-1", "conversation_id": 1, "customer_tweet_id": 1,
            "customer_message": "I can't log in, my password is invalid",
            "brand_response": "Please try resetting your password via the app.",
            "response_type": "substantive_response", "number_of_context_messages": 0,
            "context_messages_json": "[]", "primary_intent": "Account Access & Login",
            "labeling_method": "deterministic", "customer_timestamp": "2020-01-01T00:00:00",
            "brand_timestamp": "2020-01-01T00:05:00", "low_info_customer_message": False,
            "cross_brand_response": False,
        },
        {
            "resolution_id": "RES-2-2", "conversation_id": 2, "customer_tweet_id": 2,
            "customer_message": "I was charged twice this month for my subscription",
            "brand_response": "We'll issue a refund for the duplicate charge.",
            "response_type": "substantive_response", "number_of_context_messages": 0,
            "context_messages_json": "[]", "primary_intent": "Premium Subscription & Billing",
            "labeling_method": "deterministic", "customer_timestamp": "2020-01-02T00:00:00",
            "brand_timestamp": "2020-01-02T00:05:00", "low_info_customer_message": False,
            "cross_brand_response": False,
        },
        {
            "resolution_id": "RES-3-3", "conversation_id": 3, "customer_tweet_id": 3,
            "customer_message": "The app keeps crashing when I play a song",
            "brand_response": "Try reinstalling the app.",
            "response_type": "substantive_response", "number_of_context_messages": 0,
            "context_messages_json": "[]", "primary_intent": "App & Playback Technical Issues",
            "labeling_method": "deterministic", "customer_timestamp": "2020-01-03T00:00:00",
            "brand_timestamp": "2020-01-03T00:05:00", "low_info_customer_message": False,
            "cross_brand_response": False,
        },
        {
            "resolution_id": "RES-4-4", "conversation_id": 4, "customer_tweet_id": 4,
            "customer_message": "thanks",
            "brand_response": "You're welcome!",
            "response_type": "acknowledgement", "number_of_context_messages": 1,
            "context_messages_json": json.dumps([
                {"tweet_id": 5, "role": "customer", "author_id": "c", "text": "My account was hacked!", "timestamp": None},
            ]),
            "primary_intent": "OTHER / UNKNOWN",
            "labeling_method": "deterministic", "customer_timestamp": "2020-01-04T00:00:00",
            "brand_timestamp": "2020-01-04T00:05:00", "low_info_customer_message": True,
            "cross_brand_response": False,
        },
        {
            "resolution_id": "RES-5-5", "conversation_id": 5, "customer_tweet_id": 5,
            "customer_message": "Why isn't the new album on Spotify",
            "brand_response": "It should be available now, please check.",
            "response_type": "substantive_response", "number_of_context_messages": 0,
            "context_messages_json": "[]", "primary_intent": "Content Availability & Catalog Accuracy",
            "labeling_method": "deterministic", "customer_timestamp": "2020-01-05T00:00:00",
            "brand_timestamp": "2020-01-05T00:05:00", "low_info_customer_message": False,
            "cross_brand_response": False,
        },
    ]
    if n:
        rows = rows[:n]
    return pl.DataFrame(rows)


def _build_test_retriever(tmp_path, df=None):
    df = df if df is not None else _synthetic_corpus_df()
    records = build_retrieval_records(df)
    vectors = embed_texts(list(records["embedding_text"]))
    index = build_faiss_index(vectors)

    index_path = tmp_path / "test.index"
    vectors_path = tmp_path / "test_vectors.npy"
    metadata_path = tmp_path / "test_metadata.parquet"

    import faiss
    faiss.write_index(index, str(index_path))
    np.save(vectors_path, vectors)
    records.write_parquet(metadata_path)

    return Retriever(index_path, metadata_path, vectors_path)


# ---------------------------------------------------------------------
# Embedding-text derivation (no model call needed)
# ---------------------------------------------------------------------

def test_embedding_text_uses_customer_message_when_not_low_info():
    text = build_embedding_text("I can't log in", "some root", low_info=False)
    assert text == "I can't log in"


def test_embedding_text_prepends_root_when_low_info():
    text = build_embedding_text("thanks", "My account was hacked!", low_info=True)
    assert text == "My account was hacked! thanks"


def test_embedding_text_falls_back_to_message_when_no_root():
    text = build_embedding_text("thanks", None, low_info=True)
    assert text == "thanks"


# ---------------------------------------------------------------------
# Deterministic metadata <-> vector mapping
# ---------------------------------------------------------------------

def test_metadata_and_vector_row_order_match(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    for i in range(len(retriever)):
        row = retriever.metadata.row(i, named=True)
        assert row["retrieval_id"] is not None
    assert retriever.vectors.shape == (5, EMBEDDING_DIMENSION)
    assert retriever.index.ntotal == 5


# ---------------------------------------------------------------------
# Top-k retrieval
# ---------------------------------------------------------------------

def test_topk_retrieval_returns_ranked_results(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    results = retriever.search("I forgot my password and can't sign in", k=3)
    assert len(results) == 3
    ranks = [r["rank"] for r in results]
    assert ranks == [1, 2, 3]
    scores = [r["similarity_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["primary_intent"] == "Account Access & Login"


def test_k_greater_than_corpus_size_is_clipped(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    results = retriever.search("billing question", k=1000)
    assert len(results) == len(retriever)


# ---------------------------------------------------------------------
# Empty / invalid query handling
# ---------------------------------------------------------------------

def test_empty_query_returns_empty_list(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    assert retriever.search("", k=5) == []
    assert retriever.search("   ", k=5) == []


def test_zero_or_negative_k_returns_empty_list(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    assert retriever.search("anything", k=0) == []
    assert retriever.search("anything", k=-1) == []


# ---------------------------------------------------------------------
# Intent filtering + OTHER/UNKNOWN fallback
# ---------------------------------------------------------------------

def test_intent_filtered_search_restricts_to_matching_intent(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    results = retriever.search("my card was charged", k=5, intent="Premium Subscription & Billing")
    assert len(results) == 1
    assert results[0]["primary_intent"] == "Premium Subscription & Billing"


def test_other_unknown_intent_uses_global_retrieval(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    global_results = retriever.search("random query text", k=5)
    other_results = retriever.search("random query text", k=5, intent=OTHER_INTENT)
    assert [r["retrieval_id"] for r in global_results] == [r["retrieval_id"] for r in other_results]


def test_intent_filter_with_no_matches_falls_back_to_global(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    filtered = retriever.search("some query", k=5, intent="Account Security")  # no row has this intent
    glob = retriever.search("some query", k=5)
    assert [r["retrieval_id"] for r in filtered] == [r["retrieval_id"] for r in glob]


# ---------------------------------------------------------------------
# Provenance preservation
# ---------------------------------------------------------------------

def test_results_carry_full_provenance(tmp_path):
    retriever = _build_test_retriever(tmp_path)
    results = retriever.search("password reset help", k=1)
    r = results[0]
    for field in ("rank", "similarity_score", "retrieval_id", "conversation_id",
                  "customer_tweet_id", "customer_message", "historical_brand_response",
                  "response_type", "primary_intent", "customer_timestamp"):
        assert field in r


# ---------------------------------------------------------------------
# Deterministic index construction
# ---------------------------------------------------------------------

def test_embedding_is_deterministic_for_same_input():
    v1 = embed_texts(["I can't log in, it says my password is invalid"])
    v2 = embed_texts(["I can't log in, it says my password is invalid"])
    assert np.allclose(v1, v2)


def test_vectors_are_l2_normalized():
    v = embed_texts(["some example customer message"])
    norm = np.linalg.norm(v[0])
    assert abs(norm - 1.0) < 1e-4


# ---------------------------------------------------------------------
# Golden exclusion (uses synthetic stand-in rows, not real golden data)
# ---------------------------------------------------------------------

def test_golden_exclusion_logic_removes_exact_tweet_id_and_text_matches():
    from build_retrieval_index import verify_golden_exclusion

    df = _synthetic_corpus_df()
    # RES-1-1's tweet_id (1) will be treated as a "golden" tweet_id via monkeypatched loader.
    import build_retrieval_index as bri

    def fake_loader(path):
        if "candidates" in str(path):
            return [{"tweet_id": 1, "customer_message": "unrelated golden text"}]
        return [{"tweet_id": None, "customer_message": "I was charged twice this month for my subscription"}]

    original = bri._load_jsonl
    bri._load_jsonl = fake_loader
    try:
        report, hit_ids = verify_golden_exclusion(df)
    finally:
        bri._load_jsonl = original

    assert "RES-1-1" in hit_ids  # matched by tweet_id
    assert "RES-2-2" in hit_ids  # matched by exact text
    assert report["unique_rows_excluded_for_golden_leakage"] == 2


# ---------------------------------------------------------------------
# Source corpus immutability (build_retrieval_records must not mutate input)
# ---------------------------------------------------------------------

def test_build_retrieval_records_does_not_mutate_input_df():
    df = _synthetic_corpus_df()
    before_cols = set(df.columns)
    build_retrieval_records(df)
    assert set(df.columns) == before_cols
