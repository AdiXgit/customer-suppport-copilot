"""
Phase 10: end-to-end evaluation harness entry point.

Usage:
    .venv/Scripts/python.exe scripts/evaluate_agent.py                  # full 200-example run
    .venv/Scripts/python.exe scripts/evaluate_agent.py --limit 5        # quick smoke run
    .venv/Scripts/python.exe scripts/evaluate_agent.py --skip-judge --skip-llm-baseline

The golden set (data/golden/golden_set_annotations.jsonl) is read
ONLY to (a) supply the raw customer_message as agent input and (b)
record the gold label alongside the prediction for later scoring. It
is never passed into the agent, the generator, or the judge.

Writes (all under data/evaluation/):
    agent_predictions.jsonl
    intent_metrics.json
    baseline_metrics.json
    judge_results.jsonl          (unless --skip-judge)
    human_calibration_template.jsonl
    retrieval_comparison.json    (unless --skip-judge)
    evaluation_summary.json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from agent import SupportAgent  # noqa: E402
from evaluation.baselines import majority_class_baseline  # noqa: E402
from evaluation.human_calibration import build_calibration_template, select_calibration_example_ids  # noqa: E402
from evaluation.metrics import intent_classification_metrics  # noqa: E402
from evaluation.runner import (  # noqa: E402
    EVAL_DIR,
    RETRIEVAL_MODES,
    load_golden_set,
    new_run_metadata,
    run_agent_predictions,
    run_judge_over_predictions,
    write_jsonl,
)
from generation.generator import Generator  # noqa: E402
from generation.llm_client import LocalLLMClient  # noqa: E402
from intent.deterministic_classifier import CANONICAL_INTENTS  # noqa: E402
from retrieval.retriever import Retriever  # noqa: E402

CANONICAL_LABELS = sorted(CANONICAL_INTENTS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 10 evaluation harness")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N golden examples (smoke testing)")
    parser.add_argument("--k", type=int, default=5, help="Retrieval top-k")
    parser.add_argument("--skip-llm-baseline", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()

    golden_rows = load_golden_set()
    print(f"Loaded {len(golden_rows)} golden examples.")

    retriever = Retriever(
        REPO_ROOT / "data" / "retrieval" / "spotifycares.index",
        REPO_ROOT / "data" / "retrieval" / "spotifycares_metadata.parquet",
        REPO_ROOT / "data" / "retrieval" / "spotifycares_vectors.npy",
    )
    llm_client = LocalLLMClient()
    generator = Generator(llm_client)
    agent_by_mode = {mode: SupportAgent(retriever=retriever, generator=generator) for mode in RETRIEVAL_MODES}

    print("Running agent predictions (this calls the local LLM once per example per retrieval mode)...")
    records = run_agent_predictions(
        golden_rows, agent_by_mode, llm_client, k=args.k,
        run_llm_baseline=not args.skip_llm_baseline, limit=args.limit,
        checkpoint_path=EVAL_DIR / "agent_predictions.jsonl",
    )
    write_jsonl(EVAL_DIR / "agent_predictions.jsonl", records)
    print(f"Wrote {len(records)} prediction records -> {EVAL_DIR / 'agent_predictions.jsonl'}")

    # --- Intent metrics (Steps 2-5): deterministic classifier, majority baseline, LLM baseline ---
    scored = [r for r in records if r["gold_intent"] is not None]
    gold_labels = [r["gold_intent"] for r in scored]

    intent_metrics = {
        "n_total_golden_examples": len(records),
        "n_scored_examples": len(scored),
        "n_excluded_no_gold_intent": len(records) - len(scored),
        "proposed_deterministic_classifier": intent_classification_metrics(
            gold_labels, [r["predicted_intent"] for r in scored], CANONICAL_LABELS,
        ),
        "majority_baseline": intent_classification_metrics(
            gold_labels, [r["majority_baseline_intent"] for r in scored], CANONICAL_LABELS,
        ),
        "ambiguous_examples_count": sum(1 for r in scored if r.get("gold_ambiguous")),
        "non_english_examples_count": sum(1 for r in scored if r.get("gold_non_english")),
    }
    if not args.skip_llm_baseline:
        llm_scored = [r for r in scored if r.get("llm_baseline_status") == "success"]
        intent_metrics["simple_llm_baseline"] = intent_classification_metrics(
            [r["gold_intent"] for r in llm_scored], [r["llm_baseline_intent"] for r in llm_scored], CANONICAL_LABELS,
        )
        intent_metrics["simple_llm_baseline"]["n_llm_call_failures"] = len(scored) - len(llm_scored)
    else:
        intent_metrics["simple_llm_baseline"] = {"status": "skipped"}

    (EVAL_DIR / "intent_metrics.json").write_text(json.dumps(intent_metrics, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {EVAL_DIR / 'intent_metrics.json'}")

    baseline_metrics = {
        "majority_class_source": majority_class_baseline(),
        "run_metadata": new_run_metadata({"n_examples": len(records)}),
    }
    (EVAL_DIR / "baseline_metrics.json").write_text(json.dumps(baseline_metrics, indent=2, default=str), encoding="utf-8")

    # --- Judge (Steps 7-8) + retrieval comparison (Step 12) ---
    if not args.skip_judge:
        print("Running LLM judge over both retrieval modes...")
        judge_rows = run_judge_over_predictions(records, llm_client, checkpoint_path=EVAL_DIR / "judge_results.jsonl")
        write_jsonl(EVAL_DIR / "judge_results.jsonl", judge_rows)
        print(f"Wrote {len(judge_rows)} judge rows -> {EVAL_DIR / 'judge_results.jsonl'}")

        from evaluation.retrieval_comparison import build_retrieval_comparison
        comparison = build_retrieval_comparison(records, judge_rows)
        (EVAL_DIR / "retrieval_comparison.json").write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {EVAL_DIR / 'retrieval_comparison.json'}")
    else:
        judge_rows = []
        print("Skipped judge (per --skip-judge).")

    # --- Human calibration template (Step 9) ---
    all_ids = [r["example_id"] for r in records]
    calibration_ids = set(select_calibration_example_ids(all_ids))
    calibration_rows = build_calibration_template(records, calibration_ids, retrieval_mode="global")
    write_jsonl(EVAL_DIR / "human_calibration_template.jsonl", calibration_rows)
    print(f"Wrote {len(calibration_rows)} human-calibration template rows -> {EVAL_DIR / 'human_calibration_template.jsonl'}")

    # --- Evaluation summary ---
    summary = {
        "run_metadata": new_run_metadata(),
        "evaluation_set_size": len(records),
        "k": args.k,
        "retrieval_modes_evaluated": RETRIEVAL_MODES,
        "llm_baseline_run": not args.skip_llm_baseline,
        "judge_run": not args.skip_judge,
        "human_calibration_sample_size": len(calibration_rows),
        "human_calibration_pending": True,
        "note": (
            "This summary covers Steps 1-9, 12 (harness, intent eval, baselines, "
            "end-to-end run, judge, retrieval comparison, human-calibration template). "
            "Steps 10-11 (judge/human agreement, escalation ground-truth metrics) "
            "require the human_calibration_template.jsonl file to be filled in by "
            "a human reviewer and are NOT computed here -- see that file and the "
            "final report for exactly what is needed."
        ),
    }
    (EVAL_DIR / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {EVAL_DIR / 'evaluation_summary.json'}")


if __name__ == "__main__":
    main()
