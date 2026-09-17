"""
Unit tests for src/data/resolution_extraction.py.

All tests use tiny synthetic fixtures shaped like the Phase 7A output
schema (conversation_id, tweet_id, author_id, role, timestamp, text,
parent_tweet_id, parent_resolved, source_row_id). None reads the real
Phase 7A Parquet file or the raw CSV -- that's covered by the smoke
test in tests/test_resolution_smoke.py.
"""

from datetime import datetime, timezone

import polars as pl
import pytest

from data.resolution_extraction import (
    BRAND_FAMILY_ACCOUNTS,
    MEGA_THREAD_CONVERSATION_IDS,
    apply_exclusions,
    classify_response_type,
    deduplicate_candidates,
    extract_resolution_candidates,
    is_bare_dm_followup,
    is_unusable_fragment,
)

COLUMNS = [
    "conversation_id", "tweet_id", "author_id", "role", "timestamp",
    "text", "parent_tweet_id", "parent_resolved", "source_row_id",
]


def ts(minute: int) -> datetime:
    return datetime(2017, 10, 31, 22, minute, 0, tzinfo=timezone.utc)


def make_df(rows: list[dict]) -> pl.DataFrame:
    filled = []
    for i, r in enumerate(rows):
        row = {c: r.get(c) for c in COLUMNS}
        if row["source_row_id"] is None:
            row["source_row_id"] = i
        if row["parent_resolved"] is None:
            row["parent_resolved"] = True
        filled.append(row)
    return pl.DataFrame(
        filled,
        schema={
            "conversation_id": pl.Int64,
            "tweet_id": pl.Int64,
            "author_id": pl.Utf8,
            "role": pl.Utf8,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "text": pl.Utf8,
            "parent_tweet_id": pl.Int64,
            "parent_resolved": pl.Boolean,
            "source_row_id": pl.UInt32,
        },
    )


def simple_conversation():
    """conv 1: customer(1) -> brand(2)"""
    return make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "I can't access Premium.", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "Can you tell us which account you're using?", "parent_tweet_id": 1},
    ])


# ---------------------------------------------------------------------
# Customer -> brand pairing (structural, via parent_tweet_id)
# ---------------------------------------------------------------------

def test_customer_to_brand_pairing_basic():
    df = simple_conversation()
    candidates, report, _ = extract_resolution_candidates(df)
    assert candidates.height == 1
    row = candidates.row(0, named=True)
    assert row["customer_tweet_id"] == 1
    assert row["brand_tweet_id"] == 2
    assert row["customer_message"] == "I can't access Premium."
    assert row["brand_response"] == "Can you tell us which account you're using?"


def test_pairing_uses_parent_pointer_not_chronological_adjacency():
    """Two independent customer threads interleaved in time must not
    get cross-paired just because they're chronologically adjacent."""
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "custA", "role": "customer",
         "timestamp": ts(0), "text": "Thread A problem", "parent_tweet_id": None},
        {"conversation_id": 2, "tweet_id": 2, "author_id": "custB", "role": "customer",
         "timestamp": ts(1), "text": "Thread B problem", "parent_tweet_id": None},
        # Brand replies to A at t=2, chronologically after B's message (t=1) -- must still pair with A, not B.
        {"conversation_id": 1, "tweet_id": 3, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(2), "text": "Reply to A", "parent_tweet_id": 1},
    ])
    candidates, _, _ = extract_resolution_candidates(df)
    assert candidates.height == 1
    row = candidates.row(0, named=True)
    assert row["customer_tweet_id"] == 1
    assert row["conversation_id"] == 1


def test_only_customer_authored_parents_produce_candidates():
    """A brand reply whose parent is another brand message (e.g. a
    two-part brand reply "1:... 2:...") must not itself be paired as if
    the first brand message were a customer trigger."""
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "issue", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "1: first part", "parent_tweet_id": 1},
        {"conversation_id": 1, "tweet_id": 3, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(2), "text": "2: second part", "parent_tweet_id": 2},
    ])
    candidates, _, _ = extract_resolution_candidates(df)
    # Only tweet_id=2 has a customer parent; tweet_id=3's parent (2) is a brand message.
    assert candidates.height == 1
    assert candidates.row(0, named=True)["brand_tweet_id"] == 2


# ---------------------------------------------------------------------
# Chronological ordering
# ---------------------------------------------------------------------

def test_output_sorted_chronologically_within_conversation():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "first", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(5), "text": "later reply", "parent_tweet_id": 1},
        {"conversation_id": 1, "tweet_id": 3, "author_id": "cust1", "role": "customer",
         "timestamp": ts(1), "text": "second", "parent_tweet_id": 2},
        {"conversation_id": 1, "tweet_id": 4, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(2), "text": "earlier reply", "parent_tweet_id": 3},
    ])
    candidates, _, _ = extract_resolution_candidates(df)
    timestamps = candidates.get_column("brand_timestamp").to_list()
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------
# Parent/child relationship handling
# ---------------------------------------------------------------------

def test_broken_parent_chain_produces_no_candidate():
    """A brand row whose parent_tweet_id doesn't exist in the working
    set (broken chain) must not crash and must not produce a candidate
    with a fabricated customer message."""
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(0), "text": "orphaned reply", "parent_tweet_id": 999, "parent_resolved": False},
    ])
    candidates, report, _ = extract_resolution_candidates(df)
    assert candidates.height == 0


def test_root_message_with_no_parent_is_never_a_brand_candidate():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "root, no reply yet", "parent_tweet_id": None},
    ])
    candidates, report, _ = extract_resolution_candidates(df)
    assert candidates.height == 0
    assert report.conversations_with_no_brand_response == 1


# ---------------------------------------------------------------------
# Multiple brand responses to the same customer message
# ---------------------------------------------------------------------

def test_multiple_brand_responses_produce_multiple_candidates():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "issue", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "reply from agent A", "parent_tweet_id": 1},
        {"conversation_id": 1, "tweet_id": 3, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "reply from agent B", "parent_tweet_id": 1},
    ])
    candidates, _, _ = extract_resolution_candidates(df)
    assert candidates.height == 2
    assert set(candidates.get_column("brand_tweet_id").to_list()) == {2, 3}
    assert all(c == 1 for c in candidates.get_column("customer_tweet_id").to_list())


# ---------------------------------------------------------------------
# Multi-turn context
# ---------------------------------------------------------------------

def test_multi_turn_context_preserved_without_duplicating_full_conversation():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "I can't access Premium.", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "Can you tell us which account you're using?", "parent_tweet_id": 1},
        {"conversation_id": 1, "tweet_id": 3, "author_id": "cust1", "role": "customer",
         "timestamp": ts(2), "text": "aditya@example.com", "parent_tweet_id": 2},
        {"conversation_id": 1, "tweet_id": 4, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(3), "text": "Please DM us so we can investigate.", "parent_tweet_id": 3},
    ])
    candidates, report, _ = extract_resolution_candidates(df)
    assert candidates.height == 2

    final = candidates.filter(pl.col("brand_tweet_id") == 4).row(0, named=True)
    assert final["customer_message"] == "aditya@example.com"
    assert final["number_of_context_messages"] == 2

    import json
    context = json.loads(final["context_messages_json"])
    assert [c["tweet_id"] for c in context] == [1, 2]
    assert context[0]["text"] == "I can't access Premium."
    assert context[1]["text"] == "Can you tell us which account you're using?"

    first = candidates.filter(pl.col("brand_tweet_id") == 2).row(0, named=True)
    assert first["number_of_context_messages"] == 0

    assert report.multi_turn_candidate_count == 1
    assert report.max_context_messages == 2


# ---------------------------------------------------------------------
# Response-type handling
# ---------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Can you DM us your account email?", "dm_redirect"),
    ("Please send us a private message with your details.", "dm_redirect"),
    ("You're welcome!", "acknowledgement"),
    ("Thanks!", "acknowledgement"),
    ("What device are you using?", "clarification_question"),
    ("Sometimes content gets temporarily removed because of licensing changes, hopefully it'll be back soon.", "substantive_response"),
])
def test_classify_response_type(text, expected):
    assert classify_response_type(text) == expected


def test_response_type_counts_in_quality_report():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "issue one", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "Can you DM us your email?", "parent_tweet_id": 1},
        {"conversation_id": 2, "tweet_id": 3, "author_id": "cust2", "role": "customer",
         "timestamp": ts(0), "text": "issue two", "parent_tweet_id": None},
        {"conversation_id": 2, "tweet_id": 4, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "Thanks!", "parent_tweet_id": 3},
    ])
    _, report, _ = extract_resolution_candidates(df)
    assert report.dm_redirect_count == 1
    assert report.acknowledgement_count == 1
    assert report.candidate_resolution_count == 2


# ---------------------------------------------------------------------
# Known brand-family exclusion
# ---------------------------------------------------------------------

def test_brand_family_account_excluded_as_trigger():
    account = sorted(BRAND_FAMILY_ACCOUNTS)[0]
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": account, "role": "customer",
         "timestamp": ts(0), "text": "3 months of Premium for $9!", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "Hey! Can you DM us your email?", "parent_tweet_id": 1},
    ])
    candidates, report, exclusions = extract_resolution_candidates(df)
    assert candidates.height == 0
    reasons = [e.exclusion_reason for e in exclusions.entries if e.author_id == account]
    assert "brand_family_account" in reasons
    entry = next(e for e in exclusions.entries if e.author_id == account)
    assert entry.affected_candidate_count == 1


def test_genuine_customer_not_excluded():
    df = simple_conversation()
    _, _, exclusions = extract_resolution_candidates(df)
    for e in exclusions.entries:
        assert "cust1" != e.author_id


# ---------------------------------------------------------------------
# DM-followup exclusion
# ---------------------------------------------------------------------

def test_bare_dm_followup_excluded_as_trigger():
    df = make_df([
        {"conversation_id": 1, "tweet_id": 1, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "check your dms please", "parent_tweet_id": None},
        {"conversation_id": 1, "tweet_id": 2, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "We've replied, let's continue there.", "parent_tweet_id": 1},
    ])
    candidates, _, exclusions = extract_resolution_candidates(df)
    assert candidates.height == 0
    reasons = [e.exclusion_reason for e in exclusions.entries]
    assert "dm_followup_no_issue" in reasons


def test_dm_followup_regex_helper_direct():
    assert is_bare_dm_followup("check your dms please") is True
    assert is_bare_dm_followup("please respond to my dms") is True
    assert is_bare_dm_followup("urgent please check dm") is True
    assert is_bare_dm_followup("My account has been hacked, please DM me back with a solution") is False


def test_fragment_helper_direct():
    assert is_unusable_fragment("@SpotifyCares https://t.co/abc123") is True
    assert is_unusable_fragment("my account was hacked and I can't log in") is False


# ---------------------------------------------------------------------
# Mega-thread exclusion
# ---------------------------------------------------------------------

def test_mega_thread_conversation_fully_excluded():
    mega_id = next(iter(MEGA_THREAD_CONVERSATION_IDS))
    df = make_df([
        {"conversation_id": mega_id, "tweet_id": 1, "author_id": "115888", "role": "customer",
         "timestamp": ts(0), "text": "promo broadcast", "parent_tweet_id": None},
        {"conversation_id": mega_id, "tweet_id": 2, "author_id": "custX", "role": "customer",
         "timestamp": ts(1), "text": "question about the promo", "parent_tweet_id": None},
        {"conversation_id": mega_id, "tweet_id": 3, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(2), "text": "Hey! Can you DM us?", "parent_tweet_id": 2},
        # An unrelated, legitimate conversation must be unaffected.
        {"conversation_id": 999, "tweet_id": 4, "author_id": "cust1", "role": "customer",
         "timestamp": ts(0), "text": "real issue", "parent_tweet_id": None},
        {"conversation_id": 999, "tweet_id": 5, "author_id": "SpotifyCares", "role": "brand",
         "timestamp": ts(1), "text": "real reply", "parent_tweet_id": 4},
    ])
    candidates, report, exclusions = extract_resolution_candidates(df)
    assert mega_id not in candidates.get_column("conversation_id").to_list()
    assert candidates.height == 1
    assert candidates.row(0, named=True)["conversation_id"] == 999

    mega_entries = [e for e in exclusions.entries if e.exclusion_reason == "mega_thread"]
    assert len(mega_entries) == 1
    assert mega_entries[0].conversation_id == mega_id
    assert mega_entries[0].affected_message_count == 3
    assert mega_entries[0].affected_candidate_count == 1  # the one brand reply that would have paired
    assert report.mega_thread_message_count == 3


# ---------------------------------------------------------------------
# Deterministic resolution IDs
# ---------------------------------------------------------------------

def test_resolution_id_deterministic_and_stable_across_row_order():
    rows = simple_conversation()
    reversed_rows = rows.reverse()
    c1, _, _ = extract_resolution_candidates(rows)
    c2, _, _ = extract_resolution_candidates(reversed_rows)
    assert c1.get_column("resolution_id").to_list() == c2.get_column("resolution_id").to_list()
    assert c1.row(0, named=True)["resolution_id"] == "RES-1-2"


# ---------------------------------------------------------------------
# Duplicate resolution detection
# ---------------------------------------------------------------------

def test_deduplicate_candidates_detects_and_drops_duplicates():
    df = pl.DataFrame({
        "resolution_id": ["RES-1-2", "RES-1-2", "RES-1-3"],
        "brand_response": ["first", "duplicate, should be dropped", "other"],
    })
    out, n_dropped = deduplicate_candidates(df)
    assert n_dropped == 1
    assert out.height == 2
    kept = out.filter(pl.col("resolution_id") == "RES-1-2").row(0, named=True)
    assert kept["brand_response"] == "first"


def test_no_duplicate_resolutions_reports_zero_end_to_end():
    df = simple_conversation()
    _, report, _ = extract_resolution_candidates(df)
    assert report.duplicate_resolution_ids_found == 0


# ---------------------------------------------------------------------
# Reproducible output
# ---------------------------------------------------------------------

def test_full_extraction_is_reproducible():
    df = simple_conversation()
    c1, r1, _ = extract_resolution_candidates(df)
    c2, r2, _ = extract_resolution_candidates(df)
    assert c1.equals(c2)
    assert r1.to_dict() == r2.to_dict()


def test_intent_field_present_and_null_by_design():
    df = simple_conversation()
    candidates, _, _ = extract_resolution_candidates(df)
    assert "intent" in candidates.columns
    assert candidates.get_column("intent").is_null().all()
