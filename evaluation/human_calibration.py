"""
Phase 10, Step 9: human calibration sample + template.

Selects ~50 examples from the 200 golden examples with a reproducible
seed, chosen WITHOUT looking at judge scores (selection happens over
example_id order only, before any judge score is consulted). Produces
a clean template file with the score/verdict fields left null for a
human reviewer to fill in -- this module never fabricates a human
label.
"""

from __future__ import annotations

import random

HUMAN_CALIBRATION_SEED = 2026
HUMAN_CALIBRATION_SAMPLE_SIZE = 50


def select_calibration_example_ids(all_example_ids: list[str], seed: int = HUMAN_CALIBRATION_SEED,
                                    n: int = HUMAN_CALIBRATION_SAMPLE_SIZE) -> list[str]:
    rng = random.Random(seed)
    return sorted(rng.sample(all_example_ids, min(n, len(all_example_ids))))


def build_calibration_template(records: list[dict], example_ids: set[str], retrieval_mode: str = "global") -> list[dict]:
    """records: the same combined records produced by evaluation/runner.py.
    Only the selected example_ids are included. Each row shows the
    customer message, the historical evidence actually retrieved, and
    the generated reply/escalation decision for ONE retrieval mode
    (global by default, per Phase 8/9's recommended default) -- with
    every human-facing judgment field left as null for completion."""
    rows = []
    for record in records:
        if record["example_id"] not in example_ids:
            continue
        mode_data = record[retrieval_mode]
        rows.append({
            "example_id": record["example_id"],
            "customer_message": record["customer_message"],
            "retrieval_mode_shown": retrieval_mode,
            "historical_evidence": [
                {
                    "rank": c["rank"],
                    "customer_message": c["customer_message"],
                    "historical_response": c["historical_response"],
                    "similarity": c["similarity"],
                }
                for c in mode_data["retrieved_cases"]
            ],
            "generated_reply": mode_data["reply"],
            "system_escalation_decision": mode_data["escalate"],
            "system_escalation_reason": mode_data["escalation_reason"],
            # --- Human reviewer: fill in the fields below. Leave any
            # field you are unsure about as null rather than guessing. ---
            "human_correctness_1_5": None,
            "human_groundedness_1_5": None,
            "human_helpfulness_1_5": None,
            "human_actionability_1_5": None,
            "human_brand_consistency_1_5": None,
            "human_hallucination": None,          # true / false
            "human_should_escalate": None,        # "yes" / "no" / "uncertain"
            "human_reviewer_notes": None,
        })
    return rows
