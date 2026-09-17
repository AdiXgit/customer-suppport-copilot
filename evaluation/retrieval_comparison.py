"""
Phase 10, Step 12: global vs. intent-filtered retrieval comparison,
using the LLM judge's scores on the SAME 200 examples (no threshold
retuning, no golden-set-based selection of which examples to compare).
"""

from __future__ import annotations

from collections import defaultdict


def _judge_lookup(judge_rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(r["example_id"], r["retrieval_mode"]): r for r in judge_rows}


def build_retrieval_comparison(records: list[dict], judge_rows: list[dict]) -> dict:
    lookup = _judge_lookup(judge_rows)
    modes = ["global", "intent_filtered"]

    per_mode = {mode: defaultdict(list) for mode in modes}
    escalation_by_mode = {mode: {"escalate_true": 0, "escalate_false": 0} for mode in modes}
    evidence_sufficient_by_mode = {mode: 0 for mode in modes}
    n = len(records)
    escalation_diffs = []

    for record in records:
        mode_escalations = {}
        for mode in modes:
            if mode not in record:
                continue
            mode_data = record[mode]
            if mode_data["escalate"]:
                escalation_by_mode[mode]["escalate_true"] += 1
            else:
                escalation_by_mode[mode]["escalate_false"] += 1
            if mode_data["evidence_sufficient"]:
                evidence_sufficient_by_mode[mode] += 1
            mode_escalations[mode] = (mode_data["escalate"], mode_data["escalation_reason"])

            judge_row = lookup.get((record["example_id"], mode))
            if judge_row and judge_row.get("status") == "success" and judge_row.get("verdict"):
                v = judge_row["verdict"]
                for field in ("correctness", "groundedness", "helpfulness", "actionability", "brand_consistency"):
                    per_mode[mode][field].append(v[field])
                per_mode[mode]["hallucination"].append(1 if v["hallucination"] else 0)
                per_mode[mode]["overall_evidence_supported"].append(1 if v["overall_evidence_supported"] else 0)

        if len(mode_escalations) == 2 and mode_escalations["global"] != mode_escalations["intent_filtered"]:
            escalation_diffs.append({
                "example_id": record["example_id"],
                "global": mode_escalations["global"],
                "intent_filtered": mode_escalations["intent_filtered"],
            })

    def _avg(values):
        return round(sum(values) / len(values), 4) if values else None

    judge_summary = {}
    for mode in modes:
        judge_summary[mode] = {
            "n_judged": len(per_mode[mode].get("correctness", [])),
            "avg_correctness": _avg(per_mode[mode].get("correctness", [])),
            "avg_groundedness": _avg(per_mode[mode].get("groundedness", [])),
            "avg_helpfulness": _avg(per_mode[mode].get("helpfulness", [])),
            "avg_actionability": _avg(per_mode[mode].get("actionability", [])),
            "avg_brand_consistency": _avg(per_mode[mode].get("brand_consistency", [])),
            "hallucination_rate": _avg(per_mode[mode].get("hallucination", [])),
            "overall_evidence_supported_rate": _avg(per_mode[mode].get("overall_evidence_supported", [])),
        }

    return {
        "n_examples": n,
        "judge_scores_by_mode": judge_summary,
        "escalation_counts_by_mode": escalation_by_mode,
        "evidence_sufficient_counts_by_mode": evidence_sufficient_by_mode,
        "n_examples_where_escalation_decision_differs_by_mode": len(escalation_diffs),
        "escalation_decision_diffs": escalation_diffs,
        "note": (
            "This compares the SAME 200 examples under global vs. intent-filtered "
            "retrieval using the LLM judge's own scores -- it is not a claim of "
            "ground truth, and no threshold was retuned to produce these numbers. "
            "See the final report for factual, non-ranking observations."
        ),
    }
