"""
Unit tests for evaluation/evidence_validation.py and
evaluation/failure_categorization.py. Synthetic data only.
"""

from evaluation.evidence_validation import validate_evidence_signal
from evaluation.failure_categorization import categorize_replies


def _verdict(correctness=4, groundedness=4, actionability=4, hallucination=False, evidence_supported=True):
    return {
        "correctness": correctness, "groundedness": groundedness, "helpfulness": 4,
        "actionability": actionability, "brand_consistency": 4,
        "hallucination": hallucination, "overall_evidence_supported": evidence_supported,
        "reasons": {"groundedness": "because reasons"},
    }


def _judge_row(eid, mode, **kwargs):
    return {"example_id": eid, "retrieval_mode": mode, "status": "success", "verdict": _verdict(**kwargs)}


def _record(eid, evidence_sufficient=True, escalate=False, reply="Thanks, we'll look into it.",
            predicted_intent="Premium Subscription & Billing", gold_intent="Premium Subscription & Billing"):
    return {
        "example_id": eid, "customer_message": "msg", "predicted_intent": predicted_intent, "gold_intent": gold_intent,
        "global": {
            "evidence_sufficient": evidence_sufficient, "escalate": escalate, "reply": reply,
            "escalation_reason": "NONE", "evidence_reasons": [],
        },
    }


# ---------------------------------------------------------------------
# evidence_validation
# ---------------------------------------------------------------------

def test_evidence_validation_counts_agreement_and_disagreement():
    records = [
        _record("A", evidence_sufficient=True),
        _record("B", evidence_sufficient=False),
        _record("C", evidence_sufficient=True),
    ]
    judge_rows = [
        _judge_row("A", "global", evidence_supported=True),   # both true
        _judge_row("B", "global", evidence_supported=False),  # both false
        _judge_row("C", "global", evidence_supported=False),  # system true, judge disagrees
    ]
    result = validate_evidence_signal(records, judge_rows, mode="global")
    assert result["agreement"]["both_sufficient"] == 1
    assert result["agreement"]["both_insufficient"] == 1
    assert result["agreement"]["system_sufficient_judge_disagrees"] == 1
    assert len(result["system_false_positive_examples"]) == 1
    assert result["system_false_positive_examples"][0]["example_id"] == "C"


def test_evidence_validation_skips_examples_without_judge_verdict():
    records = [_record("A", evidence_sufficient=True)]
    result = validate_evidence_signal(records, judge_rows=[], mode="global")
    assert result["n_judged"] == 0
    assert result["agreement"]["raw_agreement_rate"] is None


# ---------------------------------------------------------------------
# failure_categorization
# ---------------------------------------------------------------------

def test_categorize_flags_hallucination():
    records = [_record("A")]
    judge_rows = [_judge_row("A", "global", hallucination=True)]
    result = categorize_replies(records, judge_rows)
    assert "A" in result["category_example_ids"]["unsupported_policy_claim_or_invented_action"]


def test_categorize_flags_wrong_intent():
    records = [_record("A", predicted_intent="OTHER / UNKNOWN", gold_intent="Feature Request & Product Feedback")]
    result = categorize_replies(records, judge_rows=[])
    assert "A" in result["category_example_ids"]["wrong_intent"]


def test_categorize_flags_insufficient_evidence_but_confident():
    records = [_record("A", evidence_sufficient=False, escalate=False)]
    result = categorize_replies(records, judge_rows=[])
    assert "A" in result["category_example_ids"]["insufficient_evidence_but_confident"]


def test_categorize_flags_copied_artifact():
    records = [_record("A", reply="Check https://t.co/abc123 for more info /LO")]
    result = categorize_replies(records, judge_rows=[])
    assert "A" in result["category_example_ids"]["copied_historical_artifact"]


def test_categorize_flags_vague_reply():
    records = [_record("A")]
    judge_rows = [_judge_row("A", "global", actionability=1)]
    result = categorize_replies(records, judge_rows)
    assert "A" in result["category_example_ids"]["vague_or_non_actionable"]


def test_categorize_flags_possible_unnecessary_escalation():
    records = [_record("A", escalate=True)]
    judge_rows = [_judge_row("A", "global", correctness=5, groundedness=5, hallucination=False)]
    result = categorize_replies(records, judge_rows)
    assert "A" in result["category_example_ids"]["possible_unnecessary_escalation"]


def test_categorize_flags_possible_unsafe_non_escalation():
    records = [_record("A", escalate=False)]
    judge_rows = [_judge_row("A", "global", hallucination=True)]
    result = categorize_replies(records, judge_rows)
    assert "A" in result["category_example_ids"]["possible_unsafe_non_escalation"]


def test_categorize_counts_match_example_id_lists():
    records = [_record("A", escalate=False)]
    judge_rows = [_judge_row("A", "global", hallucination=True)]
    result = categorize_replies(records, judge_rows)
    for key, ids in result["category_example_ids"].items():
        assert result["category_counts"][key] == len(ids)
