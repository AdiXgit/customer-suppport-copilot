"""
Unit tests for evaluation/retrieval_comparison.py. Synthetic data only.
"""

from evaluation.retrieval_comparison import build_retrieval_comparison


def _record(example_id, global_escalate, filtered_escalate):
    return {
        "example_id": example_id,
        "global": {"escalate": global_escalate, "escalation_reason": "NONE" if not global_escalate else "INSUFFICIENT_EVIDENCE",
                   "evidence_sufficient": not global_escalate},
        "intent_filtered": {"escalate": filtered_escalate, "escalation_reason": "NONE" if not filtered_escalate else "INSUFFICIENT_EVIDENCE",
                            "evidence_sufficient": not filtered_escalate},
    }


def _judge_row(example_id, mode, correctness=4, hallucination=False):
    return {
        "example_id": example_id, "retrieval_mode": mode, "status": "success",
        "verdict": {
            "correctness": correctness, "groundedness": 4, "helpfulness": 4, "actionability": 4,
            "brand_consistency": 4, "hallucination": hallucination, "overall_evidence_supported": not hallucination,
        },
    }


def test_identifies_escalation_decision_differences():
    records = [_record("GOLD-0001", True, False), _record("GOLD-0002", True, True)]
    judge_rows = [_judge_row("GOLD-0001", "global"), _judge_row("GOLD-0001", "intent_filtered"),
                  _judge_row("GOLD-0002", "global"), _judge_row("GOLD-0002", "intent_filtered")]
    result = build_retrieval_comparison(records, judge_rows)
    assert result["n_examples_where_escalation_decision_differs_by_mode"] == 1
    assert result["escalation_decision_diffs"][0]["example_id"] == "GOLD-0001"


def test_aggregates_judge_scores_per_mode():
    records = [_record("GOLD-0001", False, False)]
    judge_rows = [_judge_row("GOLD-0001", "global", correctness=5), _judge_row("GOLD-0001", "intent_filtered", correctness=3)]
    result = build_retrieval_comparison(records, judge_rows)
    assert result["judge_scores_by_mode"]["global"]["avg_correctness"] == 5.0
    assert result["judge_scores_by_mode"]["intent_filtered"]["avg_correctness"] == 3.0


def test_handles_missing_judge_rows_gracefully():
    records = [_record("GOLD-0001", False, False)]
    result = build_retrieval_comparison(records, judge_rows=[])
    assert result["judge_scores_by_mode"]["global"]["n_judged"] == 0
    assert result["judge_scores_by_mode"]["global"]["avg_correctness"] is None
