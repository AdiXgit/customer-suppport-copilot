"""
Unit tests for src/data/corpus_filtering.py.

All tests use tiny synthetic fixtures. None reads the real Phase 7A/7B
Parquet files or the golden set -- that's covered by
tests/test_corpus_filtering_smoke.py.
"""

from datetime import datetime, timezone

import polars as pl
import pytest

from data.corpus_filtering import (
    BROADCAST_MIN_RATIO,
    BROADCAST_MIN_SIZE,
    filter_corpus,
    identify_broadcast_conversations,
    is_low_info_customer_message,
    is_unusable_brand_response,
    load_golden_leakage_keys,
)

RECON_COLUMNS = [
    "conversation_id", "tweet_id", "author_id", "role", "timestamp",
    "text", "parent_tweet_id", "parent_resolved", "source_row_id",
]

CAND_COLUMNS = [
    "resolution_id", "conversation_id", "customer_tweet_id", "customer_author_id",
    "customer_message", "customer_timestamp", "brand_tweet_id", "brand_author_id",
    "brand_response", "brand_timestamp", "parent_tweet_id", "response_type",
    "number_of_context_messages", "context_messages_json", "intent",
    "customer_source_row_id", "brand_source_row_id",
]


def ts(minute: int) -> datetime:
    return datetime(2017, 10, 31, 22, minute, 0, tzinfo=timezone.utc)


def make_recon(rows: list[dict]) -> pl.DataFrame:
    filled = []
    for i, r in enumerate(rows):
        row = {c: r.get(c) for c in RECON_COLUMNS}
        if row["source_row_id"] is None:
            row["source_row_id"] = i
        if row["parent_resolved"] is None:
            row["parent_resolved"] = True
        filled.append(row)
    return pl.DataFrame(
        filled,
        schema={
            "conversation_id": pl.Int64, "tweet_id": pl.Int64, "author_id": pl.Utf8,
            "role": pl.Utf8, "timestamp": pl.Datetime(time_zone="UTC"), "text": pl.Utf8,
            "parent_tweet_id": pl.Int64, "parent_resolved": pl.Boolean, "source_row_id": pl.UInt32,
        },
    )


def make_candidates(rows: list[dict]) -> pl.DataFrame:
    filled = []
    for r in rows:
        row = {c: r.get(c) for c in CAND_COLUMNS}
        filled.append(row)
    return pl.DataFrame(
        filled,
        schema={
            "resolution_id": pl.Utf8, "conversation_id": pl.Int64, "customer_tweet_id": pl.Int64,
            "customer_author_id": pl.Utf8, "customer_message": pl.Utf8,
            "customer_timestamp": pl.Datetime(time_zone="UTC"), "brand_tweet_id": pl.Int64,
            "brand_author_id": pl.Utf8, "brand_response": pl.Utf8,
            "brand_timestamp": pl.Datetime(time_zone="UTC"), "parent_tweet_id": pl.Int64,
            "response_type": pl.Utf8, "number_of_context_messages": pl.Int64,
            "context_messages_json": pl.Utf8, "intent": pl.Utf8,
            "customer_source_row_id": pl.Int64, "brand_source_row_id": pl.Int64,
        },
    )


def one_candidate(cid=1, cust_tid=1, brand_tid=2, cust_msg="I can't log in", brand_msg="What device are you using?", response_type="clarification_question"):
    return {
        "resolution_id": f"RES-{cid}-{brand_tid}", "conversation_id": cid,
        "customer_tweet_id": cust_tid, "customer_author_id": "cust1",
        "customer_message": cust_msg, "customer_timestamp": ts(0),
        "brand_tweet_id": brand_tid, "brand_author_id": "SpotifyCares",
        "brand_response": brand_msg, "brand_timestamp": ts(1),
        "parent_tweet_id": cust_tid, "response_type": response_type,
        "number_of_context_messages": 0, "context_messages_json": "[]", "intent": None,
        "customer_source_row_id": 0, "brand_source_row_id": 1,
    }


# ---------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------

def test_is_unusable_brand_response():
    assert is_unusable_brand_response("@user 💚") is True
    assert is_unusable_brand_response("@user https://t.co/abc") is True
    assert is_unusable_brand_response("@user Thanks for reaching out!") is False


def test_is_low_info_customer_message():
    assert is_low_info_customer_message("@SpotifyCares Thanks!") is True
    assert is_low_info_customer_message("Yes") is True
    assert is_low_info_customer_message("@SpotifyCares I can't log in to my account") is False


# ---------------------------------------------------------------------
# Broadcast-artifact detector (generalized)
# ---------------------------------------------------------------------

def _broadcast_shaped_conversation(cid, n_customers, brand_family_root=True):
    rows = []
    root_author = "115888" if brand_family_root else "SpotifyCares"
    root_role = "customer" if brand_family_root else "brand"
    rows.append({"conversation_id": cid, "tweet_id": cid * 1000, "author_id": root_author,
                 "role": root_role, "timestamp": ts(0), "text": "broadcast", "parent_tweet_id": None})
    for i in range(n_customers):
        rows.append({"conversation_id": cid, "tweet_id": cid * 1000 + i + 1, "author_id": f"cust{i}",
                     "role": "customer", "timestamp": ts(i + 1), "text": f"reply {i}", "parent_tweet_id": cid * 1000})
    return rows


def test_broadcast_detector_flags_brand_family_root_with_many_distinct_customers():
    rows = _broadcast_shaped_conversation(1, n_customers=25, brand_family_root=True)  # size 26, ratio ~0.96
    recon = make_recon(rows)
    flagged, stats = identify_broadcast_conversations(recon)
    assert 1 in flagged


def test_broadcast_detector_does_not_flag_legitimate_deep_single_customer_thread():
    """Same size class, but one customer having a long back-and-forth
    (low ratio) rooted in a genuine customer message -- must not be flagged."""
    rows = [{"conversation_id": 2, "tweet_id": 2000, "author_id": "cust1", "role": "customer",
             "timestamp": ts(0), "text": "issue", "parent_tweet_id": None}]
    parent = 2000
    for i in range(24):
        brand_id = 2000 + i * 2 + 1
        cust_id = 2000 + i * 2 + 2
        rows.append({"conversation_id": 2, "tweet_id": brand_id, "author_id": "SpotifyCares", "role": "brand",
                     "timestamp": ts(2 * i + 1), "text": f"question {i}", "parent_tweet_id": parent})
        rows.append({"conversation_id": 2, "tweet_id": cust_id, "author_id": "cust1", "role": "customer",
                     "timestamp": ts(2 * i + 2), "text": f"answer {i}", "parent_tweet_id": brand_id})
        parent = cust_id
    recon = make_recon(rows)
    flagged, stats = identify_broadcast_conversations(recon)
    assert 2 not in flagged


def test_broadcast_detector_does_not_flag_customer_rooted_high_ratio_thread():
    """High branching ratio but rooted in a genuine customer message
    (not brand-family, not a brand broadcast) -- e.g. an organic
    feature-request pile-on -- must NOT be flagged (validated false-
    positive case from real-data investigation, conversation 2211025)."""
    rows = [{"conversation_id": 3, "tweet_id": 3000, "author_id": "cust_original", "role": "customer",
             "timestamp": ts(0), "text": "please add feature X", "parent_tweet_id": None}]
    for i in range(25):
        rows.append({"conversation_id": 3, "tweet_id": 3000 + i + 1, "author_id": f"cust{i}", "role": "customer",
                     "timestamp": ts(i + 1), "text": "+1 me too", "parent_tweet_id": 3000})
    recon = make_recon(rows)
    flagged, stats = identify_broadcast_conversations(recon)
    assert 3 not in flagged


def test_broadcast_detector_respects_size_floor():
    """A small conversation with a brand-family root and high ratio
    (e.g. size 3) must not be flagged -- below the size floor."""
    rows = _broadcast_shaped_conversation(4, n_customers=2, brand_family_root=True)  # size 3
    recon = make_recon(rows)
    flagged, stats = identify_broadcast_conversations(recon)
    assert 4 not in flagged


def test_broadcast_detector_flags_spotifycares_authored_broadcast_root():
    """Root authored by SpotifyCares itself (role=brand, no parent) --
    e.g. a status/outage announcement -- with many distinct customer
    replies must also be flagged (validated real pattern, conversations
    67684/89471/79405/293875)."""
    rows = _broadcast_shaped_conversation(5, n_customers=22, brand_family_root=False)
    recon = make_recon(rows)
    flagged, stats = identify_broadcast_conversations(recon)
    assert 5 in flagged


# ---------------------------------------------------------------------
# filter_corpus: exclusion rules + retention
# ---------------------------------------------------------------------

def _base_recon_for_candidates(cand_rows):
    """Build a minimal matching reconstruction frame so broadcast
    detection has something to operate on (no broadcasts by default)."""
    rows = []
    for r in cand_rows:
        rows.append({"conversation_id": r["conversation_id"], "tweet_id": r["customer_tweet_id"],
                     "author_id": r["customer_author_id"], "role": "customer",
                     "timestamp": r["customer_timestamp"], "text": r["customer_message"], "parent_tweet_id": None})
        rows.append({"conversation_id": r["conversation_id"], "tweet_id": r["brand_tweet_id"],
                     "author_id": r["brand_author_id"], "role": "brand",
                     "timestamp": r["brand_timestamp"], "text": r["brand_response"], "parent_tweet_id": r["customer_tweet_id"]})
    return make_recon(rows)


def test_retains_valid_candidate():
    cand = make_candidates([one_candidate(cid=1, cust_tid=1, brand_tid=2)])
    recon = _base_recon_for_candidates([one_candidate(cid=1, cust_tid=1, brand_tid=2)])
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 1
    assert report.excluded_count == 0


def test_unusable_brand_response_excluded():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2, brand_msg="@user 💚")]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, entries = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 0
    assert report.exclusion_reason_counts["unusable_brand_response"] == 1


def test_broadcast_artifact_candidates_excluded():
    rows = [one_candidate(cid=99, cust_tid=99001, brand_tid=99002, cust_msg="reply 0")]
    cand = make_candidates(rows)
    broadcast_recon_rows = _broadcast_shaped_conversation(99, n_customers=25, brand_family_root=True)
    # Ensure candidate's own tweet ids exist in recon (customer=99001 matches first reply, brand reply id 99002)
    recon = make_recon(broadcast_recon_rows + [
        {"conversation_id": 99, "tweet_id": 99002, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(30), "text": "reply", "parent_tweet_id": 99001},
    ])
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 0
    assert report.exclusion_reason_counts["broadcast_artifact"] == 1


def test_known_mega_thread_still_excluded_via_generalized_detector():
    rows = _broadcast_shaped_conversation(83694, n_customers=25, brand_family_root=True)
    recon = make_recon(rows + [
        {"conversation_id": 83694, "tweet_id": 83694999, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(30), "text": "reply", "parent_tweet_id": 83694001},
    ])
    cand = make_candidates([one_candidate(cid=83694, cust_tid=83694001, brand_tid=83694999)])
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 0
    assert report.broadcast_investigation["known_mega_thread_included"] is True


def test_deterministic_output():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2)]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    r1, q1, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    r2, q2, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert r1.equals(r2)
    assert q1.to_dict() == q2.to_dict()


def test_reproducible_across_row_order():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2), one_candidate(cid=1, cust_tid=3, brand_tid=4, cust_msg="second")]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    r1, _, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    r2, _, _ = filter_corpus(cand.reverse(), recon, golden_tweet_ids=set(), golden_messages=set())
    assert (
        r1.sort("resolution_id").get_column("resolution_id").to_list()
        == r2.sort("resolution_id").get_column("resolution_id").to_list()
    )


def test_response_types_preserved_on_retained_rows():
    rows = [
        one_candidate(cid=1, cust_tid=1, brand_tid=2, response_type="dm_redirect"),
        one_candidate(cid=2, cust_tid=3, brand_tid=4, response_type="acknowledgement"),
    ]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert set(retained.get_column("response_type").to_list()) == {"dm_redirect", "acknowledgement"}
    assert report.response_type_distribution_after == {"dm_redirect": 1, "acknowledgement": 1}


def test_multi_turn_metadata_preserved():
    row = one_candidate(cid=1, cust_tid=1, brand_tid=2)
    row["number_of_context_messages"] = 3
    row["context_messages_json"] = '[{"tweet_id": 0, "role": "customer", "text": "earlier"}]'
    cand = make_candidates([row])
    recon = _base_recon_for_candidates([row])
    retained, _, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.row(0, named=True)["number_of_context_messages"] == 3
    assert "earlier" in retained.row(0, named=True)["context_messages_json"]


def test_quality_flags_added_without_excluding():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2, cust_msg="@SpotifyCares Thanks!", brand_msg="You're welcome!")]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 1  # NOT excluded just for being low-info
    assert retained.row(0, named=True)["low_info_customer_message"] is True
    assert report.quality_flag_counts["low_info_customer_message"] == 1


def test_cross_brand_response_flagged_not_excluded():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2)]
    rows[0]["brand_author_id"] = "hulu_support"
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 1
    assert retained.row(0, named=True)["cross_brand_response"] is True


def test_dm_redirect_and_short_responses_not_auto_excluded():
    rows = [
        one_candidate(cid=1, cust_tid=1, brand_tid=2, response_type="dm_redirect", brand_msg="Can you DM us your email?"),
        one_candidate(cid=2, cust_tid=3, brand_tid=4, response_type="clarification_question", brand_msg="What device?"),
    ]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 2


# ---------------------------------------------------------------------
# Duplicate resolution_id handling (defensive dedup)
# ---------------------------------------------------------------------

def test_duplicate_resolution_id_deduplicated():
    row = one_candidate(cid=1, cust_tid=1, brand_tid=2)
    cand = make_candidates([row, dict(row)])  # exact duplicate row (pipeline-artifact style)
    recon = _base_recon_for_candidates([row])
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 1
    assert report.duplicate_resolution_ids_found == 1


def test_genuinely_separate_candidates_with_identical_text_preserved():
    """Two DIFFERENT resolution_ids with identical customer_message/
    brand_response text (e.g. two agents sending the same reply to the
    same tweet) must both be preserved -- not deduplicated."""
    rows = [
        one_candidate(cid=1, cust_tid=1, brand_tid=2, brand_msg="Can you DM us your email?"),
        one_candidate(cid=1, cust_tid=1, brand_tid=3, brand_msg="Can you DM us your email?"),
    ]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(cand, recon, golden_tweet_ids=set(), golden_messages=set())
    assert retained.height == 2
    assert report.exact_duplicate_brand_response_groups == 1


# ---------------------------------------------------------------------
# Golden-set exact-match leakage detection
# ---------------------------------------------------------------------

def test_golden_set_exact_tweet_id_match_excluded():
    rows = [one_candidate(cid=1, cust_tid=555, brand_tid=2)]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, entries = filter_corpus(cand, recon, golden_tweet_ids={555}, golden_messages=set())
    assert retained.height == 0
    assert report.exclusion_reason_counts["golden_set_overlap"] == 1
    assert report.golden_set_leakage["total_excluded_for_leakage"] == 1


def test_golden_set_exact_text_match_excluded():
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2, cust_msg="my exact golden text")]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(
        cand, recon, golden_tweet_ids=set(), golden_messages={"my exact golden text"}
    )
    assert retained.height == 0
    assert report.exclusion_reason_counts["golden_set_overlap"] == 1


def test_normalized_only_match_not_excluded():
    """A different tweet with similar-but-not-identical normalized text
    to a golden example must NOT be excluded (avoid over-filtering
    genuinely separate interactions -- see docs)."""
    rows = [one_candidate(cid=1, cust_tid=1, brand_tid=2, cust_msg="I need help with my account!!")]
    cand = make_candidates(rows)
    recon = _base_recon_for_candidates(rows)
    retained, report, _ = filter_corpus(
        cand, recon, golden_tweet_ids=set(), golden_messages={"i need help with my account"}
    )
    assert retained.height == 1
    assert report.golden_set_leakage["additional_normalized_only_matches_NOT_excluded"] == 1


def test_load_golden_leakage_keys(tmp_path):
    ann_path = tmp_path / "ann.jsonl"
    cand_path = tmp_path / "cand.jsonl"
    ann_path.write_text('{"example_id": "GOLD-0001", "customer_message": "help me"}\n', encoding="utf-8")
    cand_path.write_text('{"example_id": "GOLD-0001", "tweet_id": 42}\n', encoding="utf-8")
    tweet_ids, messages = load_golden_leakage_keys(ann_path, cand_path)
    assert tweet_ids == {42}
    assert messages == {"help me"}
