"""
Phase 10, Steps 13-14 (+ escalation-metrics placeholder): post-hoc
analysis over an already-completed scripts/evaluate_agent.py run.

Run this AFTER scripts/evaluate_agent.py has produced
data/evaluation/agent_predictions.jsonl and data/evaluation/judge_results.jsonl.
Kept separate from evaluate_agent.py so it can be re-run cheaply
(no LLM calls) while iterating on analysis code, without re-running
the ~1000-call evaluation itself.

Usage:
    .venv/Scripts/python.exe scripts/analyze_evaluation.py

Writes:
    data/evaluation/evidence_threshold_validation.json
    data/evaluation/reply_failure_categorization.json
    data/evaluation/escalation_metrics.json (a pending-human-data placeholder,
        or the real computation if data/evaluation/human_calibration_completed.jsonl exists)
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from evaluation.evidence_validation import validate_evidence_signal  # noqa: E402
from evaluation.failure_categorization import categorize_replies  # noqa: E402
from evaluation.metrics import escalation_metrics  # noqa: E402
from evaluation.runner import RETRIEVAL_MODES  # noqa: E402

EVAL_DIR = REPO_ROOT / "data" / "evaluation"
HUMAN_COMPLETED_PATH = EVAL_DIR / "human_calibration_completed.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    predictions_path = EVAL_DIR / "agent_predictions.jsonl"
    judge_path = EVAL_DIR / "judge_results.jsonl"
    if not predictions_path.exists():
        raise SystemExit(f"{predictions_path} not found -- run scripts/evaluate_agent.py first")

    records = _load_jsonl(predictions_path)
    judge_rows = _load_jsonl(judge_path) if judge_path.exists() else []

    evidence_validation = {mode: validate_evidence_signal(records, judge_rows, mode=mode) for mode in RETRIEVAL_MODES}
    (EVAL_DIR / "evidence_threshold_validation.json").write_text(
        json.dumps(evidence_validation, indent=2, default=str), encoding="utf-8",
    )
    print(f"Wrote {EVAL_DIR / 'evidence_threshold_validation.json'}")

    failure_categorization = {mode: categorize_replies(records, judge_rows, mode=mode) for mode in RETRIEVAL_MODES}
    (EVAL_DIR / "reply_failure_categorization.json").write_text(
        json.dumps(failure_categorization, indent=2, default=str), encoding="utf-8",
    )
    print(f"Wrote {EVAL_DIR / 'reply_failure_categorization.json'}")

    if HUMAN_COMPLETED_PATH.exists():
        human_rows = _load_jsonl(HUMAN_COMPLETED_PATH)
        by_id = {r["example_id"]: r for r in records}
        system_escalate = []
        human_should = []
        for h in human_rows:
            if h.get("human_should_escalate") is None:
                continue
            record = by_id.get(h["example_id"])
            if record is None or "global" not in record:
                continue
            system_escalate.append(record["global"]["escalate"])
            human_should.append(h["human_should_escalate"])
        result = escalation_metrics(system_escalate, human_should)
        result["status"] = "computed_from_human_calibration_completed"
        (EVAL_DIR / "escalation_metrics.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {EVAL_DIR / 'escalation_metrics.json'} (from real human annotations)")
    else:
        placeholder = {
            "status": "pending_human_calibration",
            "note": (
                "Escalation precision/recall/F1, unsafe-auto-resolution rate, and "
                "unnecessary-escalation rate require genuine human 'should_escalate' "
                "judgments (Step 11), which do not exist yet. Fill in "
                "data/evaluation/human_calibration_template.jsonl's "
                "human_should_escalate field (yes/no/uncertain) for its 50 sampled "
                "examples, save the completed file as "
                "data/evaluation/human_calibration_completed.jsonl, and re-run this "
                "script to compute the real metrics. See evaluation/failure_categorization.json's "
                "'possible_unnecessary_escalation' / 'possible_unsafe_non_escalation' "
                "fields for a JUDGE-based (not human) proxy in the meantime."
            ),
        }
        (EVAL_DIR / "escalation_metrics.json").write_text(json.dumps(placeholder, indent=2), encoding="utf-8")
        print(f"Wrote {EVAL_DIR / 'escalation_metrics.json'} (placeholder -- human calibration pending)")


if __name__ == "__main__":
    main()
