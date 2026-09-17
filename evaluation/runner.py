"""
Phase 10, Step 1 & 6: evaluation harness runner.

Loads the 200-example golden set as HELD-OUT evaluation data only.
The agent receives ONLY the raw customer_message at inference time --
gold_intent, gold_secondary_issue, ambiguous/non_english flags, and
annotator_notes are read here purely to be recorded ALONGSIDE the
agent's prediction for later scoring, never passed into
SupportAgent.handle() or any prompt.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from agent import SupportAgent
from evaluation.baselines import majority_class_baseline, predict_majority_baseline, simple_llm_intent_classifier
from evaluation.judge import JUDGE_PROMPT_VERSION, run_judge
from generation.generator import Generator
from generation.llm_client import LocalLLMClient

REPO_ROOT = Path(__file__).parent.parent
GOLDEN_PATH = REPO_ROOT / "data" / "golden" / "golden_set_annotations.jsonl"
EVAL_DIR = REPO_ROOT / "data" / "evaluation"

RETRIEVAL_MODES = ["global", "intent_filtered"]


def load_golden_set(path: Path = GOLDEN_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_agent_predictions(golden_rows: list[dict], agent_by_mode: dict[str, SupportAgent],
                           llm_client_for_baseline, k: int = 5,
                           run_llm_baseline: bool = True, limit: int | None = None,
                           checkpoint_path: Path | None = None, progress_every: int = 5) -> list[dict]:
    """Runs, for each golden row: the majority baseline, the simple LLM
    baseline, and the full agent in each retrieval mode. Returns one
    combined record per example, ready to write as JSONL. The gold
    fields are carried through for later scoring only -- never fed
    into any of the predictors above.

    Since a full 200-example run makes ~1000 sequential local-LLM
    calls and can take hours, `checkpoint_path` (if given) is
    rewritten after every example so progress survives an interruption,
    and a one-line progress note prints every `progress_every` examples."""
    rows = golden_rows[:limit] if limit else golden_rows
    majority = majority_class_baseline()
    majority_intent = majority["majority_intent"]

    records = []
    total = len(rows)
    start_time = time.time()
    for i, row in enumerate(rows, start=1):
        customer_message = row["customer_message"]
        record = {
            "example_id": row["example_id"],
            "customer_message": customer_message,
            "gold_intent": row.get("primary_intent"),
            "gold_secondary_issue": row.get("secondary_issue"),
            "gold_ambiguous": row.get("ambiguous"),
            "gold_non_english": row.get("non_english"),
            "gold_excluded": row.get("excluded", False),
            "gold_exclusion_reason": row.get("exclusion_reason"),
            "majority_baseline_intent": predict_majority_baseline([customer_message], majority_intent)[0],
        }

        if run_llm_baseline:
            baseline_result = simple_llm_intent_classifier(llm_client_for_baseline, customer_message)
            record["llm_baseline_intent"] = baseline_result["predicted_intent"]
            record["llm_baseline_raw_output"] = baseline_result.get("raw_output")
            record["llm_baseline_status"] = baseline_result["status"]
        else:
            record["llm_baseline_intent"] = None
            record["llm_baseline_raw_output"] = None
            record["llm_baseline_status"] = "skipped"

        for mode, agent in agent_by_mode.items():
            use_filter = mode == "intent_filtered"
            result = agent.handle(customer_message, k=k, use_intent_filter=use_filter).to_dict()

            if mode == "global":
                record["predicted_intent"] = result["intent"]
                record["predicted_intent_confidence"] = result["intent_confidence"]
                record["predicted_secondary_issue"] = result["secondary_issue"]
                record["predicted_intent_reason"] = result["trace"]["intent_reason"]

            record[mode] = {
                "retrieved_cases": result["retrieved_cases"],
                "evidence_sufficient": result["evidence_sufficient"],
                "reply": result["reply"],
                "escalate": result["escalate"],
                "escalation_reason": result["escalation_reason"],
                "generation_status": result["trace"]["generation_status"],
                "generation_reason": result["trace"]["generation_reason"],
                "evidence_reasons": result["trace"]["evidence_reasons"],
                "evidence_top_similarity": result["trace"]["evidence_top_similarity"],
            }

        records.append(record)

        if checkpoint_path is not None:
            write_jsonl(checkpoint_path, records)
        if i % progress_every == 0 or i == total:
            elapsed = time.time() - start_time
            rate = elapsed / i
            remaining = rate * (total - i)
            print(f"[{i}/{total}] elapsed={elapsed/60:.1f}min avg={rate:.1f}s/example "
                  f"est_remaining={remaining/60:.1f}min", flush=True)

    return records


def run_judge_over_predictions(records: list[dict], judge_llm_client,
                                checkpoint_path: Path | None = None, progress_every: int = 10) -> list[dict]:
    """One judge row per (example_id, retrieval_mode)."""
    judge_rows = []
    total_calls = sum(1 for r in records for m in RETRIEVAL_MODES if m in r)
    start_time = time.time()
    n_done = 0
    for record in records:
        for mode in RETRIEVAL_MODES:
            if mode not in record:
                continue
            mode_data = record[mode]
            verdict = run_judge(
                judge_llm_client,
                record["customer_message"],
                mode_data["retrieved_cases"],
                mode_data["reply"],
            )
            judge_rows.append({
                "example_id": record["example_id"],
                "retrieval_mode": mode,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                **verdict,
            })
            n_done += 1
            if checkpoint_path is not None:
                write_jsonl(checkpoint_path, judge_rows)
            if n_done % progress_every == 0 or n_done == total_calls:
                elapsed = time.time() - start_time
                rate = elapsed / n_done
                remaining = rate * (total_calls - n_done)
                print(f"[judge {n_done}/{total_calls}] elapsed={elapsed/60:.1f}min "
                      f"avg={rate:.1f}s/call est_remaining={remaining/60:.1f}min", flush=True)
    return judge_rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def new_run_metadata(extra: dict | None = None) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "run_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **(extra or {}),
    }
