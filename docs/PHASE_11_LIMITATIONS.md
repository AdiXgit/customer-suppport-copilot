# Phase 11 — Human Calibration Limitations

## The core limitation

Phase 11 asked for genuine human judgments on 50 calibration examples, to be
compared against the LLM judge (Phase 10) as required by the assignment's
"evidence of human-vs-LLM judge agreement" criterion.

**No human annotator was available in this session.** The 50 labels in
`data/evaluation/human_calibration_completed.jsonl` were produced by Claude
(the coding assistant) acting as a second, independent LLM annotator reading
the same customer message, retrieved evidence, generated reply, and
escalation decision the judge saw — not a person.

This is disclosed explicitly, not silently substituted:

- Every row in `human_calibration_completed.jsonl` carries
  `"annotator_type": "llm_proxy_not_genuine_human"`.
- `data/evaluation/evaluation_summary.json` labels every section that depends
  on this data with a `WARNING` field restating the limitation.
- `data/evaluation/judge_human_agreement.json` is LLM-judge-vs-LLM-proxy
  agreement, not human-vs-LLM agreement.
- `data/evaluation/escalation_metrics.json` is escalation precision/recall
  computed against an LLM-proxy "should escalate" label, not a human one.

## Why this matters for interpreting the numbers

Two LLMs (even from different vantage points / prompts) share correlated
failure modes in a way a human would not. Weak dimension-score correlation
was still observed between the judge and the proxy (Spearman r < 0.19 on all
five 1-5 dimensions, none statistically significant at n=48) — if two LLMs
already disagree this much, a real human would very plausibly diverge
further, not less. The escalation precision/recall numbers should be read as
"a worked example of the required metric, computed on the best available
data," not as a validated ground-truth comparison.

## What would close this gap

A single human reviewer spending 2-3 hours filling in the same 50-row
template (`data/evaluation/human_calibration_template.jsonl`) with genuine
judgment, saved as `human_calibration_completed.jsonl`, would let
`scripts/analyze_evaluation.py`'s escalation-metrics path and a rerun of the
agreement computation (`evaluation/metrics.py`'s `spearman_agreement` /
`cohen_kappa`) produce the metrics this phase was actually meant to produce.
No code changes would be required — the schema is already correct.
