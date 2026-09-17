"""
Phase 10, Step 14: first-pass reply failure categorization.

This is an INITIAL, evaluation-level pass using only signals already
measured elsewhere in this phase (judge verdicts, the system's own
evidence/escalation decisions, gold intent where available) -- never
invented percentages, and never a human ground-truth label (that
doesn't exist yet; see human_calibration.py). A dedicated, deeper
failure-analysis phase comes later per the task instructions.

Categories and the measured signal used to flag each one (a record can
land in more than one category):

  unsupported_policy_claim / invented_action -- judge hallucination == True
  wrong_intent                    -- predicted_intent != gold_intent (scored examples only)
  insufficient_evidence_but_confident -- system evidence_sufficient == False
                                          but system did NOT escalate
  retrieval_evidence_disputed      -- system evidence_sufficient == True but
                                       judge overall_evidence_supported == False
  copied_historical_artifact       -- reply text contains a raw tracking
                                       link (t.co) or a brand-agent
                                       signature token (e.g. "/AB")
  vague_or_non_actionable          -- judge actionability score <= 2
  possible_unnecessary_escalation  -- system escalated AND judge scored
                                       correctness/groundedness both >= 4
                                       and hallucination == False (a
                                       PROXY signal only -- see note)
  possible_unsafe_non_escalation   -- system did NOT escalate AND
                                       (judge hallucination == True OR
                                       judge correctness <= 2) (a PROXY
                                       signal only -- see note)

The last two are explicitly labeled "possible" and are a proxy using
the judge, not a substitute for the human-judgment-based
unsafe-auto-resolution / unnecessary-escalation metrics defined in
evaluation/metrics.py, which require the human calibration data.
"""

from __future__ import annotations

import re
from collections import defaultdict

_ARTIFACT_RE = re.compile(r"https?://t\.co/\S+|/[A-Z]{2,3}\b")


def categorize_replies(records: list[dict], judge_rows: list[dict], mode: str = "global") -> dict:
    judge_lookup = {(r["example_id"], r["retrieval_mode"]): r for r in judge_rows}
    categories: dict[str, list[str]] = defaultdict(list)
    n_considered = 0

    for record in records:
        if mode not in record:
            continue
        n_considered += 1
        eid = record["example_id"]
        mode_data = record[mode]
        judge_row = judge_lookup.get((eid, mode))
        verdict = judge_row["verdict"] if judge_row and judge_row.get("status") == "success" else None

        if verdict and verdict["hallucination"]:
            categories["unsupported_policy_claim_or_invented_action"].append(eid)

        if record.get("gold_intent") and record["predicted_intent"] != record["gold_intent"]:
            categories["wrong_intent"].append(eid)

        if not mode_data["evidence_sufficient"] and not mode_data["escalate"]:
            categories["insufficient_evidence_but_confident"].append(eid)

        if mode_data["evidence_sufficient"] and verdict and not verdict["overall_evidence_supported"]:
            categories["retrieval_evidence_disputed"].append(eid)

        if _ARTIFACT_RE.search(mode_data["reply"] or ""):
            categories["copied_historical_artifact"].append(eid)

        if verdict and verdict["actionability"] <= 2:
            categories["vague_or_non_actionable"].append(eid)

        if verdict and mode_data["escalate"] and verdict["correctness"] >= 4 and verdict["groundedness"] >= 4 and not verdict["hallucination"]:
            categories["possible_unnecessary_escalation"].append(eid)

        if verdict and not mode_data["escalate"] and (verdict["hallucination"] or verdict["correctness"] <= 2):
            categories["possible_unsafe_non_escalation"].append(eid)

    return {
        "retrieval_mode": mode,
        "n_considered": n_considered,
        "category_counts": {k: len(v) for k, v in categories.items()},
        "category_example_ids": dict(categories),
        "note": (
            "'possible_unnecessary_escalation' and 'possible_unsafe_non_escalation' "
            "are judge-based PROXY signals, not the human-judgment-based metrics in "
            "evaluation/metrics.py's escalation_metrics() -- those require the "
            "completed human_calibration_template.jsonl. Counts here are exact "
            "over this run's records, not estimated/invented percentages."
        ),
    }
