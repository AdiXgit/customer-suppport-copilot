"""
Phase 11, Step 2: validation of data/evaluation/human_calibration_completed.jsonl
against data/evaluation/human_calibration_template.jsonl.

Skips (does not fail) if the completed file doesn't exist yet, since the
template is generated before the completed file and this test can run at
any point in that lifecycle.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = REPO_ROOT / "data" / "evaluation" / "human_calibration_template.jsonl"
COMPLETED_PATH = REPO_ROOT / "data" / "evaluation" / "human_calibration_completed.jsonl"

ORIGINAL_FIELDS = [
    "customer_message", "retrieval_mode_shown", "historical_evidence",
    "generated_reply", "system_escalation_decision", "system_escalation_reason",
]
RATING_FIELDS = [
    "human_correctness_1_5", "human_groundedness_1_5", "human_helpfulness_1_5",
    "human_actionability_1_5", "human_brand_consistency_1_5",
]


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


pytestmark = pytest.mark.skipif(
    not COMPLETED_PATH.exists(),
    reason="human_calibration_completed.jsonl not produced yet",
)


@pytest.fixture(scope="module")
def rows():
    return _load_jsonl(COMPLETED_PATH), _load_jsonl(TEMPLATE_PATH)


def test_exactly_fifty_examples(rows):
    completed, _ = rows
    assert len(completed) == 50


def test_ids_match_template_exactly(rows):
    completed, template = rows
    assert {r["example_id"] for r in completed} == {r["example_id"] for r in template}


def test_no_duplicate_ids(rows):
    completed, _ = rows
    ids = [r["example_id"] for r in completed]
    assert len(ids) == len(set(ids))


def test_original_fields_unchanged(rows):
    completed, template = rows
    t_by_id = {r["example_id"]: r for r in template}
    for row in completed:
        t = t_by_id[row["example_id"]]
        for field in ORIGINAL_FIELDS:
            assert row[field] == t[field], f"{row['example_id']}: {field} was modified"


def test_rating_fields_are_ints_in_range(rows):
    completed, _ = rows
    for row in completed:
        for field in RATING_FIELDS:
            v = row[field]
            assert isinstance(v, int) and not isinstance(v, bool)
            assert 1 <= v <= 5


def test_hallucination_is_boolean(rows):
    completed, _ = rows
    for row in completed:
        assert isinstance(row["human_hallucination"], bool)


def test_should_escalate_is_boolean_or_none(rows):
    completed, _ = rows
    for row in completed:
        v = row["human_should_escalate"]
        assert v is None or isinstance(v, bool)


def test_annotator_type_disclosed_as_llm_proxy(rows):
    """These are NOT genuine human labels -- see the labeling-honesty
    constraint in evaluation_summary.json. Every row must carry an explicit
    marker so downstream consumers can't mistake this for real human data."""
    completed, _ = rows
    for row in completed:
        assert row.get("annotator_type") == "llm_proxy_not_genuine_human"
