# SpotifyCares Support Agent

A brand-specific AI customer-support agent built and evaluated on real
SpotifyCares (Spotify's Twitter support account) conversations from the
Kaggle ["Customer Support on Twitter"](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter)
dataset — a take-home project. Given an incoming customer message, the
agent (1) classifies its intent, (2) drafts a reply grounded in how
SpotifyCares has historically resolved similar issues, and (3) decides
whether to auto-handle the case or escalate it to a human, with a stated
reason. See `docs/FINAL_REPORT.md` for the full write-up (results, failure
modes, limitations); this file covers what the system is and how to run it.

**🚀 [Live Demo](https://customer-suppport-copilot-bstsn4wam6f8tikcaw3xbn.streamlit.app/)**

Try the deployed SpotifyCares Support Copilot on Streamlit Cloud.

This is a CLI + Streamlit-UI + evaluation-harness project, per the
assignment's engineering constraints (see `CLAUDE.md`).

## Architecture

```
customer message
      |
      v
intent classification (src/intent/)        -- deterministic classifier
      |                                        against a 9-intent taxonomy
      v                                        derived from real SpotifyCares
historical retrieval (src/retrieval/)          data (docs/INTENTS.md)
      |                                     -- FAISS IndexFlatIP over
      v                                        historical resolution pairs
evidence assessment (src/evidence.py)       -- is the retrieved evidence
      |                                        actually good enough to answer?
      v
grounded reply generation (src/generation/) -- LLM drafts a reply from
      |                                        retrieved historical evidence
      v                                        only (LLMClient abstraction)
escalation decision (src/escalation/)       -- AUTO_HANDLE or ESCALATE,
      |                                        with a stated reason
      v
structured result (src/agent.py's SupportAgent.handle())
```

Each stage is an independently testable module; `src/agent.py` only
orchestrates. The LLM layer is abstracted behind `LLMClient`
(`src/generation/llm_client.py`): only `LocalLLMClient` (Ollama,
`gemma2:9b-instruct-q4_0`, purely local HTTP, no API key) is actually
implemented — the `GroqLLMClient` hosted-provider slot from the original
architecture plan was never built, since a local model was sufficient here.

## Repository layout

```
src/            agent pipeline (intent, retrieval, evidence, generation, escalation)
evaluation/     evaluation harness (metrics, baselines, LLM judge, calibration)
scripts/        data-pipeline and evaluation entry points (see below)
tests/          pytest suite (256 tests)
docs/           final report, decision log, taxonomy, and data/design docs
data/           datasets and generated artifacts (see "What's tracked" below)
```

## How to run the project

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # see requirements.txt for a torch note
```

Requires a local [Ollama](https://ollama.com) install with
`gemma2:9b-instruct-q4_0` pulled (`ollama pull gemma2:9b-instruct-q4_0`) for
reply generation; retrieval/evidence/escalation work without it, but
generation falls back to a deterministic template if Ollama is unreachable.

Run the agent on one message:

```bash
.venv/Scripts/python.exe scripts/run_agent.py --message "I was charged twice for Premium"
.venv/Scripts/python.exe scripts/run_agent.py --message "..." --intent-filter --k 3 --json
```

## How to reproduce the data/retrieval pipeline

The raw 493MB Twitter CSV is **not** committed (see `.gitignore`). To
rebuild everything from scratch you need your own copy of
`twcs.csv` from the Kaggle dataset above, placed at
`data/raw/twitter/twcs.csv`, then:

```bash
.venv/Scripts/python.exe scripts/reconstruct_spotifycares.py
.venv/Scripts/python.exe scripts/extract_resolution_candidates.py
.venv/Scripts/python.exe scripts/filter_resolution_corpus.py
.venv/Scripts/python.exe scripts/assign_intents.py
.venv/Scripts/python.exe scripts/build_retrieval_index.py
```

The processed Parquet files these scripts read/write **are** committed
(a few MB each), so most of this pipeline is inspectable without the raw
CSV — only regenerating from scratch requires it. The FAISS index and raw
vectors (`spotifycares.index`, `spotifycares_vectors.npy`, ~122MB
combined) are also not committed; `build_retrieval_index.py` regenerates
them from the committed `spotifycares_intent_corpus.parquet`.

## How to run the evaluation

```bash
.venv/Scripts/python.exe scripts/evaluate_agent.py       # full 200-example run, ~1000 LLM calls, several hours on local Ollama
.venv/Scripts/python.exe scripts/analyze_evaluation.py   # cheap post-hoc analysis, no LLM calls
```

`scripts/evaluate_agent.py` accepts `--limit N` for a fast smoke-test run,
`--skip-llm-baseline`, and `--skip-judge`. All results already committed
under `data/evaluation/` reflect the last full run — re-running is
expensive and not required to review the results.

```bash
.venv/Scripts/python.exe -m pytest -q     # 256 tests
```

## Evaluation methodology

- **200-example golden set** (`data/golden/golden_set_annotations.jsonl`),
  sampled per `docs/GOLDEN_SET.md`.
  **Labeling provenance, stated plainly**: 25 of the 200 examples were
  labeled by a genuine human annotator (the calibration batch); the
  remaining 175 were labeled by Claude (the coding assistant) reading each
  message directly against the taxonomy contract — not by an independent
  human, and not via a separate LLM API call. **This project does not claim
  200 independently human-labelled examples.**
- **Two baselines**: majority-class intent classifier, and a simple
  single-call LLM intent classifier with no retrieval/agent pipeline
  (`evaluation/baselines.py`).
- **Automated metrics**: precision/recall/F1 per intent, confusion matrix,
  accuracy vs. both baselines (`evaluation/metrics.py`).
- **LLM-as-judge**: a structured rubric (5 quality dimensions 1-5,
  hallucination flag, evidence-supported flag) scored per example per
  retrieval mode (`evaluation/judge.py`).
- **Human/judge calibration**: a 50-example subset was independently
  re-scored and used as escalation ground truth. **This 50-example set was
  labeled by an LLM proxy (Claude), not a genuine independent human
  reviewer** — disclosed via an `annotator_type` field on every record in
  `data/evaluation/human_calibration_completed.jsonl`. See
  `docs/FINAL_REPORT.md`'s Limitations section for exactly what this does
  and doesn't establish, and what closing the gap would require.
- Full results, all five required report sections (automated / judge /
  human-calibration / human-grounded-escalation / limitations), the top-5
  failure modes with real example IDs, and the "what's misleading about my
  headline number" reflection are in
  `data/evaluation/evaluation_summary.json` and `docs/FINAL_REPORT.md`.

### Headline results (see `docs/FINAL_REPORT.md` for full context/caveats)

| Metric | Value |
|---|---|
| Majority-class baseline accuracy | 3.7% |
| Simple LLM baseline accuracy | **78.5%** |
| Proposed deterministic classifier accuracy | 50.3% |
| Judge avg correctness / groundedness (global mode) | 4.79 / 4.52 out of 5 |
| System escalation rate (global mode) | 80% |
| Escalation precision / recall (n=50, LLM-proxy ground truth) | 0.63 / 1.0 |

**The proposed intent classifier underperforms the simple LLM baseline.**
This is reported, not hidden — see `docs/FINAL_REPORT.md` Section 7.

## Documentation map

This repository's documentation was trimmed after the initial commit to
just the files a reviewer actually needs; development/phase-tracking notes
were removed once their conclusions were folded into these:

- `docs/FINAL_REPORT.md` — the assignment deliverable report (problem
  framing, results, failure modes, misleading-headline-number reflection,
  one-more-week plan, limitations).
- `docs/DECISIONS.md` — 15 non-obvious engineering/methodology decisions
  with rationale.
- `docs/DATA.md` — dataset structure/quality and brand-selection summary.
- `docs/INTENTS.md` — the 9-intent taxonomy and its tie-break rules.
- `docs/GOLDEN_SET.md` — golden-set sampling design and composition.
- `docs/TECH_STACK.md` — environment and dependency history.

There is no `docs/EVALUATION.md` or `docs/AGENT_RULES.md` in this
repository; use `docs/FINAL_REPORT.md` and `evaluation/` for evaluation
design, and `src/escalation/policy.py` / `src/evidence.py` for the actual
escalation and evidence-sufficiency rules.

## What's tracked in this repository

Not committed (see `.gitignore`): the raw 493MB Twitter CSV, the FAISS
index and raw embedding vectors (~122MB, regenerable), the Python virtual
environment, and Python/OS/editor cache files.

Committed: all source code, tests, evaluation code and results, golden-set
and human-calibration data, processed Parquet corpora (a few MB each), and
a small `data/raw/twitter/sample.csv` for browsability.
