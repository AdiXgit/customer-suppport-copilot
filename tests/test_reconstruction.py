"""
Unit tests for src/data/reconstruction.py.

All tests use tiny synthetic in-memory fixtures -- none reads
data/raw/twitter/twcs.csv. The real-data smoke test lives in
tests/test_smoke.py.
"""

import polars as pl
import pytest

from data.reconstruction import (
    QualityReport,
    SchemaError,
    add_source_row_id,
    assign_roles,
    compute_conversation_roots,
    deduplicate_tweet_ids,
    drop_missing_tweet_id,
    filter_to_brand_conversations,
    find_missing_required_fields,
    parse_timestamps,
    reconstruct,
    validate_schema,
)

REQUIRED = [
    "tweet_id",
    "author_id",
    "inbound",
    "created_at",
    "text",
    "response_tweet_id",
    "in_response_to_tweet_id",
]


def make_df(rows: list[dict]) -> pl.DataFrame:
    """Build a tiny TWCS-shaped DataFrame from row dicts, filling any
    omitted required column with None so tests only specify what's
    relevant to the case under test."""
    filled = []
    for r in rows:
        row = {c: r.get(c) for c in REQUIRED}
        filled.append(row)
    return pl.DataFrame(
        filled,
        schema={
            "tweet_id": pl.Int64,
            "author_id": pl.Utf8,
            "inbound": pl.Boolean,
            "created_at": pl.Utf8,
            "text": pl.Utf8,
            "response_tweet_id": pl.Utf8,
            "in_response_to_tweet_id": pl.Int64,
        },
    )


# ---------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------

def test_validate_schema_ok():
    df = make_df([{"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": "x", "text": "hi"}])
    assert validate_schema(df) == []


def test_validate_schema_missing_columns():
    df = pl.DataFrame({"tweet_id": [1], "text": ["hi"]})
    missing = validate_schema(df)
    assert "author_id" in missing
    assert "in_response_to_tweet_id" in missing


def test_reconstruct_raises_schemaerror_on_missing_columns():
    df = pl.DataFrame({"tweet_id": [1]})
    with pytest.raises(SchemaError):
        reconstruct(df, brand_authors={"SpotifyCares"})


# ---------------------------------------------------------------------
# SpotifyCares filtering (structural: by shared conversation, not by
# filtering author_id rows individually)
# ---------------------------------------------------------------------

def test_spotifycares_filtering_keeps_full_conversation():
    df = make_df([
        # A SpotifyCares conversation: customer -> brand
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "help", "in_response_to_tweet_id": None},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "sure", "in_response_to_tweet_id": 1},
        # An unrelated brand's conversation that must be excluded entirely
        {"tweet_id": 3, "author_id": "cust2", "inbound": True, "created_at": "Tue Oct 31 22:12:00 +0000 2017", "text": "help2", "in_response_to_tweet_id": None},
        {"tweet_id": 4, "author_id": "AmazonHelp", "inbound": False, "created_at": "Tue Oct 31 22:13:00 +0000 2017", "text": "sure2", "in_response_to_tweet_id": 3},
    ])
    out, report = reconstruct(df, brand_authors={"SpotifyCares"})
    assert set(out.get_column("tweet_id").to_list()) == {1, 2}
    assert report.total_spotifycares_rows == 2
    assert report.total_reconstructed_conversations == 1
    # The unrelated conversation must not leak in just because it exists in the file.
    assert 3 not in out.get_column("tweet_id").to_list()
    assert 4 not in out.get_column("tweet_id").to_list()


def test_filter_to_brand_conversations_direct():
    df = pl.DataFrame({
        "conversation_id": [1, 1, 2, 2],
        "author_id": ["cust1", "SpotifyCares", "cust2", "AmazonHelp"],
    })
    out = filter_to_brand_conversations(df, {"SpotifyCares"})
    assert set(out.get_column("conversation_id").to_list()) == {1}


# ---------------------------------------------------------------------
# Role assignment
# ---------------------------------------------------------------------

def test_role_assignment_customer_and_brand():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "hi"},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "t", "text": "hi"},
    ])
    out, missing_inbound = assign_roles(df)
    roles = dict(zip(out.get_column("tweet_id").to_list(), out.get_column("role").to_list()))
    assert roles[1] == "customer"
    assert roles[2] == "brand"
    assert missing_inbound == 0


def test_role_assignment_handles_null_inbound_without_dropping():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": None, "created_at": "t", "text": "hi"},
    ])
    out, missing_inbound = assign_roles(df)
    assert out.height == 1
    assert out.get_column("role").to_list() == ["unknown"]
    assert missing_inbound == 1


# ---------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------

def test_timestamp_parsing_valid():
    df = make_df([
        {"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": "Tue Oct 31 22:10:47 +0000 2017", "text": "hi"},
    ])
    out, invalid = parse_timestamps(df)
    assert invalid == 0
    ts = out.get_column("timestamp").to_list()[0]
    assert ts is not None
    assert ts.year == 2017 and ts.month == 10 and ts.day == 31


def test_timestamp_parsing_invalid_is_counted_not_dropped():
    df = make_df([
        {"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": "not a real timestamp", "text": "hi"},
    ])
    out, invalid = parse_timestamps(df)
    assert out.height == 1  # row kept
    assert invalid == 1
    assert out.get_column("timestamp").to_list()[0] is None


def test_timestamp_parsing_null_created_at_not_counted_as_invalid():
    df = make_df([
        {"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": None, "text": "hi"},
    ])
    out, invalid = parse_timestamps(df)
    # A genuinely missing created_at is a missing-field issue, not a
    # malformed-timestamp issue -- don't double count it.
    assert invalid == 0
    assert out.get_column("timestamp").to_list()[0] is None


# ---------------------------------------------------------------------
# Parent/child relationship handling
# ---------------------------------------------------------------------

def test_parent_child_chain_resolves_to_shared_root():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "root", "in_response_to_tweet_id": None},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "reply1", "in_response_to_tweet_id": 1},
        {"tweet_id": 3, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:12:00 +0000 2017", "text": "reply2", "in_response_to_tweet_id": 2},
    ])
    df = add_source_row_id(df)
    df, _, _ = deduplicate_tweet_ids(df)
    out, stats = compute_conversation_roots(df)
    conv_ids = set(out.get_column("conversation_id").to_list())
    assert conv_ids == {1}
    assert stats["rows_parent_broken"] == 0
    assert stats["rows_with_parent_pointer"] == 2


def test_malformed_parent_pointer_treated_as_broken_chain_not_error():
    """in_response_to_tweet_id pointing at a tweet_id absent from the
    dataset must not raise -- it becomes its own root, and is counted
    as an unresolved/broken parent."""
    df = make_df([
        {"tweet_id": 10, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "orphaned reply", "in_response_to_tweet_id": 999},
    ])
    df = add_source_row_id(df)
    df, _, _ = deduplicate_tweet_ids(df)
    out, stats = compute_conversation_roots(df)
    assert out.get_column("conversation_id").to_list() == [10]
    assert stats["rows_parent_broken"] == 1
    assert out.get_column("parent_resolved").to_list() == [False]


def test_missing_in_response_to_is_a_root():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "root", "in_response_to_tweet_id": None},
    ])
    df = add_source_row_id(df)
    df, _, _ = deduplicate_tweet_ids(df)
    out, stats = compute_conversation_roots(df)
    assert out.get_column("conversation_id").to_list() == [1]
    assert out.get_column("parent_resolved").to_list() == [True]
    assert stats["rows_with_parent_pointer"] == 0


# ---------------------------------------------------------------------
# Deterministic conversation IDs
# ---------------------------------------------------------------------

def test_conversation_ids_are_deterministic_across_runs():
    df = make_df([
        {"tweet_id": 5, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "root", "in_response_to_tweet_id": None},
        {"tweet_id": 6, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "reply", "in_response_to_tweet_id": 5},
    ])
    out1, _ = reconstruct(df, brand_authors={"SpotifyCares"})
    out2, _ = reconstruct(df, brand_authors={"SpotifyCares"})
    assert out1.sort("tweet_id").get_column("conversation_id").to_list() == \
        out2.sort("tweet_id").get_column("conversation_id").to_list()
    # conversation_id must be the root's own tweet_id, not a synthetic counter.
    assert set(out1.get_column("conversation_id").to_list()) == {5}


def test_conversation_id_independent_of_input_row_order():
    rows = [
        {"tweet_id": 5, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "root", "in_response_to_tweet_id": None},
        {"tweet_id": 6, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "reply", "in_response_to_tweet_id": 5},
    ]
    out_forward, _ = reconstruct(make_df(rows), brand_authors={"SpotifyCares"})
    out_reversed, _ = reconstruct(make_df(list(reversed(rows))), brand_authors={"SpotifyCares"})
    assert (
        out_forward.sort("tweet_id").get_column("conversation_id").to_list()
        == out_reversed.sort("tweet_id").get_column("conversation_id").to_list()
    )


# ---------------------------------------------------------------------
# Duplicate tweet detection
# ---------------------------------------------------------------------

def test_duplicate_tweet_ids_detected_and_first_occurrence_kept():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "first version"},
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "duplicate row, should be dropped"},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "t", "text": "reply"},
    ])
    df = add_source_row_id(df)
    out, n_dropped, dup_ids = deduplicate_tweet_ids(df)
    assert n_dropped == 1
    assert dup_ids == [1]
    assert out.height == 2
    kept_text = out.filter(pl.col("tweet_id") == 1).get_column("text").to_list()[0]
    assert kept_text == "first version"


def test_no_duplicates_reports_zero():
    df = make_df([
        {"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": "t", "text": "hi"},
    ])
    df = add_source_row_id(df)
    out, n_dropped, dup_ids = deduplicate_tweet_ids(df)
    assert n_dropped == 0
    assert dup_ids == []
    assert out.height == 1


def test_full_pipeline_reports_duplicate_count_end_to_end():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "v1", "in_response_to_tweet_id": None},
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "v2 dup", "in_response_to_tweet_id": None},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "reply", "in_response_to_tweet_id": 1},
    ])
    out, report = reconstruct(df, brand_authors={"SpotifyCares"})
    assert report.duplicate_tweet_id_rows_dropped == 1
    assert report.duplicate_tweet_ids_sample == [1]
    assert out.height == 2  # deduped root (1) + reply (2), no duplicate leaked through


# ---------------------------------------------------------------------
# Missing required fields / malformed relationship handling
# ---------------------------------------------------------------------

def test_missing_required_fields_are_counted():
    df = make_df([
        {"tweet_id": 1, "author_id": None, "inbound": True, "created_at": "t", "text": None},
    ])
    counts = find_missing_required_fields(df)
    assert counts["author_id"] == 1
    assert counts["text"] == 1
    assert counts["tweet_id"] == 0


def test_rows_with_null_tweet_id_are_dropped_and_counted():
    df = make_df([
        {"tweet_id": None, "author_id": "a", "inbound": True, "created_at": "t", "text": "orphan, no id"},
        {"tweet_id": 1, "author_id": "a", "inbound": True, "created_at": "t", "text": "valid"},
    ])
    df = add_source_row_id(df)
    out, n_dropped = drop_missing_tweet_id(df)
    assert n_dropped == 1
    assert out.height == 1
    assert out.get_column("tweet_id").to_list() == [1]


def test_full_pipeline_reports_missing_field_and_dropped_id_counts():
    df = make_df([
        {"tweet_id": None, "author_id": "cust1", "inbound": True, "created_at": "t", "text": "no id, dropped"},
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "root", "in_response_to_tweet_id": None},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "reply", "in_response_to_tweet_id": 1},
    ])
    out, report = reconstruct(df, brand_authors={"SpotifyCares"})
    assert report.missing_tweet_id_rows_dropped == 1
    assert report.input_rows == 3
    assert out.height == 2


# ---------------------------------------------------------------------
# QualityReport plumbing
# ---------------------------------------------------------------------

def test_quality_report_serializes_to_json(tmp_path):
    report = QualityReport(total_spotifycares_rows=5)
    out_path = tmp_path / "quality.json"
    report.to_json(out_path)
    assert out_path.exists()
    import json
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["total_spotifycares_rows"] == 5


def test_reconstruct_end_to_end_counts_customer_and_brand_messages():
    df = make_df([
        {"tweet_id": 1, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:10:00 +0000 2017", "text": "help", "in_response_to_tweet_id": None},
        {"tweet_id": 2, "author_id": "SpotifyCares", "inbound": False, "created_at": "Tue Oct 31 22:11:00 +0000 2017", "text": "sure", "in_response_to_tweet_id": 1},
        {"tweet_id": 3, "author_id": "cust1", "inbound": True, "created_at": "Tue Oct 31 22:12:00 +0000 2017", "text": "thanks", "in_response_to_tweet_id": 2},
    ])
    out, report = reconstruct(df, brand_authors={"SpotifyCares"})
    assert report.customer_messages == 2
    assert report.brand_messages == 1
    assert report.total_reconstructed_conversations == 1
    assert out.get_column("conversation_id").unique().to_list() == [1]
