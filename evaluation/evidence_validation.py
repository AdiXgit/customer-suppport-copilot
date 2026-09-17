"""
Phase 10, Step 13: evidence-sufficiency threshold observation.

Phase 9's evidence-sufficiency signals (low-similarity floor,
weak-response-type fraction, intent scatter, low-information query)
were reasoned heuristics, not calibrated against any labeled set. This
module does NOT retune them -- it only reports how often the system's
own `evidence_sufficient` flag agrees or disagrees with the judge's
`overall_evidence_supported` verdict, and surfaces concrete examples of
disagreement for the report. Calibration against genuine human
judgment happens separately once data/evaluation/human_calibration_template.jsonl
is filled in (Step 9/10) -- this function only uses the judge, which is
available for all 200 examples without waiting on a human reviewer.
"""

from __future__ import annotations


def validate_evidence_signal(records: list[dict], judge_rows: list[dict], mode: str = "global") -> dict:
    judge_lookup = {(r["example_id"], r["retrieval_mode"]): r for r in judge_rows}

    both_true = both_false = system_true_judge_false = system_false_judge_true = 0
    false_positive_examples = []  # system said sufficient, judge disagreed
    false_negative_examples = []  # system said insufficient, judge thought it was fine
    n_judged = 0

    for record in records:
        if mode not in record:
            continue
        system_sufficient = record[mode]["evidence_sufficient"]
        judge_row = judge_lookup.get((record["example_id"], mode))
        if not judge_row or judge_row.get("status") != "success" or not judge_row.get("verdict"):
            continue
        n_judged += 1
        judge_sufficient = judge_row["verdict"]["overall_evidence_supported"]

        if system_sufficient and judge_sufficient:
            both_true += 1
        elif not system_sufficient and not judge_sufficient:
            both_false += 1
        elif system_sufficient and not judge_sufficient:
            system_true_judge_false += 1
            if len(false_positive_examples) < 10:
                false_positive_examples.append({
                    "example_id": record["example_id"],
                    "customer_message": record["customer_message"],
                    "reply": record[mode]["reply"],
                    "evidence_reasons": record[mode]["evidence_reasons"],
                    "judge_reason": judge_row["verdict"].get("reasons", {}).get("groundedness"),
                })
        else:
            system_false_judge_true += 1
            if len(false_negative_examples) < 10:
                false_negative_examples.append({
                    "example_id": record["example_id"],
                    "customer_message": record["customer_message"],
                    "reply": record[mode]["reply"],
                    "evidence_reasons": record[mode]["evidence_reasons"],
                    "judge_reason": judge_row["verdict"].get("reasons", {}).get("groundedness"),
                })

    return {
        "retrieval_mode": mode,
        "n_judged": n_judged,
        "system_marked_sufficient_count": sum(1 for r in records if mode in r and r[mode]["evidence_sufficient"]),
        "judge_marked_sufficient_count": sum(
            1 for r in records
            if (jr := judge_lookup.get((r["example_id"], mode))) and jr.get("status") == "success" and jr["verdict"]["overall_evidence_supported"]
        ),
        "agreement": {
            "both_sufficient": both_true,
            "both_insufficient": both_false,
            "system_sufficient_judge_disagrees": system_true_judge_false,
            "system_insufficient_judge_disagrees": system_false_judge_true,
            "raw_agreement_rate": round((both_true + both_false) / n_judged, 4) if n_judged else None,
        },
        "system_false_positive_examples": false_positive_examples,
        "system_false_negative_examples": false_negative_examples,
        "note": (
            "This compares the system's own evidence_sufficient flag against the "
            "LLM JUDGE's overall_evidence_supported verdict, not human judgment -- "
            "it is directional evidence about threshold calibration, not a "
            "substitute for the human-calibration comparison. Thresholds in "
            "src/evidence.py were NOT changed based on this output."
        ),
    }
