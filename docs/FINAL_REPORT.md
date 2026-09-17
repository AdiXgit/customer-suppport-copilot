# SpotifyCares Support Agent — Final Report

Brand: **SpotifyCares** (Twitter customer-support account), selected from
the Kaggle "Customer Support on Twitter" dataset — see `docs/DECISIONS.md`
(decision 1) and `docs/DATA.md` for the selection process and scoring.

## 1. Problem framing

Build and evaluate an AI agent that, given an incoming customer message to
SpotifyCares, (a) classifies its intent against a taxonomy derived from the
brand's own historical conversations, (b) drafts a reply grounded in how
SpotifyCares actually resolved similar issues historically, and (c) decides
whether the case can be auto-handled or must escalate to a human, with a
stated reason. Per the assignment brief, the evaluation and evidence of
quality matter more than system sophistication.

## 2. What was built

- **Data pipeline**: raw Twitter CS dataset → conversation reconstruction
  (`src/data/reconstruction.py`) → brand-filtered corpus → resolution-pair
  extraction (`src/data/resolution_extraction.py`, `src/data/corpus_filtering.py`).
- **Intent taxonomy**: a 9-intent taxonomy (8 support intents +
  OTHER/UNKNOWN) derived from manual review of a 150-message sample of real
  SpotifyCares conversations, with an explicit, worked tie-break rule for
  its weakest ambiguity (Account Access vs. App Technical) — `docs/INTENTS.md`.
- **Intent classification**: a deterministic classifier
  (`src/intent/deterministic_classifier.py`) — the "proposed system"
  component actually tested.
- **Retrieval**: a local FAISS `IndexFlatIP` index over historical
  SpotifyCares resolution pairs (`src/retrieval/`), queried in two modes
  (global, and intent-filtered).
- **Generation**: an `LLMClient` abstraction (`LocalLLMClient` over Ollama;
  `GroqLLMClient` scaffolded) with a grounded-generation prompt
  (`src/generation/`) that drafts a reply from retrieved historical evidence.
- **Escalation policy**: a rules-based decision (`src/escalation/policy.py`)
  combining evidence sufficiency, retrieval confidence, and evidence
  conflict signals.
- **Orchestration**: `src/agent.py`'s `SupportAgent` chains all of the above.
- **Evaluation harness** (`evaluation/`, `scripts/evaluate_agent.py`,
  `scripts/analyze_evaluation.py`): automated metrics, two baselines, an
  LLM judge, a 50-example calibration process, failure categorization, and
  this report.

## 3. What was NOT built

Per the assignment's engineering-principles constraint and the Phase 11 stop
condition: no UI, no Docker, no deployment, no GitHub push, no LangChain/
LangGraph, no knowledge graph, no fine-tuning, no multi-agent architecture.
Also not built: a genuine human-annotation UI/workflow (the 50-example
calibration set is an LLM proxy — see Section 10); a GroqLLMClient
implementation beyond the abstraction's shape; retrieval
threshold auto-calibration (thresholds are reasoned, not tuned against
labeled data — explicitly not done per CLAUDE.md's "don't optimize against
the test set" rule).

## 4. Baselines

| Baseline | Accuracy | Macro-F1 |
|---|---|---|
| 1 — Majority-class intent classifier | 3.7% | 0.8% |
| 2 — Simple single-call LLM intent classifier (no retrieval/pipeline) | **78.5%** | **71.2%** |
| Proposed system — deterministic classifier | 50.3% | 51.5% |

**The proposed system's classifier loses to Baseline 2.** See Section 7.

## 5. Proposed system — reply generation & escalation results

On the full 200-example golden set (global retrieval mode; LLM judge scores,
1-5 scale unless noted):

| Metric | Value |
|---|---|
| Avg correctness | 4.79 |
| Avg groundedness | 4.52 |
| Avg helpfulness | 3.71 |
| Avg actionability | 3.92 |
| Avg brand consistency | 4.88 |
| Judge hallucination rate | 2.6% |
| System escalation rate | 80% |
| Judge-proxy "possible unnecessary escalation" rate | 67% |
| Wrong-intent rate (of 191 scored) | 47.5% |
| Copied-historical-artifact rate (links/signoffs leaked into replies) | 30% |

On the 50-example human-calibration sample (LLM-proxy ground truth — see
Section 8):

| Metric | Value |
|---|---|
| Escalation precision | 0.632 |
| Escalation recall | 1.0 |
| Escalation F1 | 0.774 |
| Unsafe auto-resolution rate | 0.0% (0/50) |
| Unnecessary escalation rate | 28% (14/50) |

## 6. Evaluation methodology

- 200-example golden set, run through the full agent pipeline in two
  retrieval modes (global, intent-filtered), plus both baselines, via
  `scripts/evaluate_agent.py`.
- Automated metrics: precision/recall/F1 per intent, confusion matrix,
  accuracy vs. both baselines (`evaluation/metrics.py`, `evaluation/baselines.py`).
- LLM-as-judge: a structured rubric (5 dimensions + hallucination +
  evidence-supported boolean) scored by a separate judge call per example
  per retrieval mode (`evaluation/judge.py`) — 400 judge calls total.
- 50-example calibration sample (seeded, reproducible selection,
  `evaluation/human_calibration.py`) compared against the judge and used as
  escalation ground truth (`evaluation/metrics.py`'s `escalation_metrics`).
- Failure categorization and evidence-threshold validation run post-hoc,
  without modifying any system code or thresholds
  (`scripts/analyze_evaluation.py`).
- Full detail, including every section's caveats, lives in
  `data/evaluation/evaluation_summary.json`.

## 7. Top 5 failure modes (with real examples)

See `data/evaluation/evaluation_summary.json`'s `6_top_failure_modes` for
the full write-up (measured signal, hypothesis, and component attribution
for each). Summary:

1. **Intent classifier underperforms Baseline 2** — 50.3% vs. 78.5%
   accuracy; over-predicts OTHER/UNKNOWN.
2. **Systematic over-escalation on well-grounded replies** — 80% global
   escalation rate; e.g. GOLD-0053, GOLD-0055, GOLD-0017 escalate despite
   high-quality, well-grounded replies.
3. **Copy-paste hallucination from retrieved evidence** — GOLD-0114
   (fabricated customer name "Alondra"), GOLD-0117 (false claim "we've
   just sent you a DM") — both missed by the LLM judge itself.
4. **Retrieved-artifact leakage** — 30% of replies carry a raw tracking
   link or another agent's signoff token (e.g. GOLD-0079's "/NJ") copied
   from historical evidence.
5. **Retrieval/intent mismatch on content-vs-technical phrasing** —
   GOLD-0059 asks whether a song was "pulled from the UK" and gets a
   generic device/OS triage question instead.

## 8. What is misleading about my headline number?

See `data/evaluation/evaluation_summary.json`'s `7_what_is_misleading...`
section for the full four-point version. In short: the intent-accuracy
number looks fine in isolation but loses to a trivial LLM baseline; the
judge's high average quality scores hide two real hallucinations the judge
itself missed and correlate weakly with an independent second LLM rating;
the 80% escalation rate looks "appropriately cautious" but a large share is
judged unnecessary; and describing the 200-example set as uniformly
human-labelled would overstate this evaluation's rigor — only 50 of the 200
have any escalation ground truth, and that ground truth is an LLM proxy,
not a person (see Section 10).

## 9. One-more-week plan

See `data/evaluation/evaluation_summary.json`'s `8_one_more_week_plan` for
the full five-item version. Top priority: get one real human annotator to
re-label the same 50 calibration examples, since that is the one
requirement this evaluation could not actually satisfy with the resources
available in this session.

## 10. Limitations

- The 50-example "human calibration" set is LLM-proxy-generated
  (Claude, disclosed via the `annotator_type` field on every record in
  `data/evaluation/human_calibration_completed.jsonl`), not genuine human
  judgment. No human annotator was available in this session; closing
  this gap would require one person spending 2-3 hours filling in
  `data/evaluation/human_calibration_template.jsonl` with real judgment
  (see Section 9) — no code changes would be needed, since the schema
  already supports it.
- Judge-proxy agreement is weak across all five rated dimensions.
- Escalation precision/recall/F1 are computed on n=50, not the full n=200.
- The judge and the proxy annotator are both LLMs, not independent human
  raters.
- Local LLM inference (Ollama) showed transient cold-start failures during
  this evaluation run; a small number of judge calls failed and are
  excluded rather than imputed.
- This evaluation reflects a single, un-tuned pass — no system code or
  threshold was changed based on golden-set results (per CLAUDE.md).
