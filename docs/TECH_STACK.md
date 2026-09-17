# Hiver Support Agent — Technical Stack

## Status

ESTABLISHED (Phase 4 — Project Environment Setup, done; superseded by later
phases below).

**Update (Phase 12 audit)**: the "confirmed absent" list below is stale.
FAISS (`faiss-cpu`), `sentence-transformers`, and `torch` (CPU build) were
installed in Phase 8 for the retrieval index and are now part of the
environment — see `requirements.txt` at the repo root for the exact,
current dependency set (captured via `pip freeze`). FastAPI, Streamlit, and
LangChain/LangGraph remain genuinely not installed and not used, per
CLAUDE.md's engineering constraints (no UI was built in this project). The
rest of this document is kept as-is below as the original Phase 4 record.

---

# Environment (Phase 4 — actual, MEASURED 2026-09-15)

| Property | Value |
|---|---|
| Venv path | `E:\hiver-support-agent\.venv` |
| Python | 3.12.6 (`E:\hiver-support-agent\.venv\Scripts\python.exe`) |
| pip | 26.2.1 (upgraded from the bundled 24.2 at venv creation) |
| `sys.prefix` | `E:\hiver-support-agent\.venv` (confirmed isolated from the global Python 3.12 install used in Phase 0) |
| venv on-disk size | ~716 MB |
| Pip cache location | `E:\hiver-support-agent\.pip-cache` (redirected here via `PIP_CACHE_DIR`, since `C:` has very little free space) |

### Installed packages (exact versions, MEASURED via `pip list --format=freeze`)

Requested minimum set for the data-engineering/evaluation phases:

| Package | Version |
|---|---|
| pandas | 3.0.5 |
| polars | 1.44.2 |
| duckdb | 1.5.5 |
| pyarrow | 25.0.1 |
| scikit-learn | 1.9.1 |
| python-dotenv | 1.2.3 |
| pytest | 9.1.1 |
| matplotlib | 3.11.2 |
| datasets | 5.0.1 |

Transitive dependencies pulled in automatically (numpy 2.5.3, scipy
1.18.1, pyyaml, requests, httpx, huggingface_hub, tqdm, filelock,
fsspec, joblib, cloudpickle, threadpoolctl, aiohttp + related async
libs, pillow, fonttools, contourpy, cycler, kiwisolver, pyparsing,
pygments, click, colorama, iniconfig, pluggy, packaging, narwhals,
dill, multiprocess, xxhash, hf-xet, python-dateutil, six, tzdata,
typing_extensions, urllib3, certifi, idna, charset-normalizer, attrs,
anyio, h11, httpcore, multidict, propcache, yarl, frozenlist,
aiosignal, aiohappyeyeballs). None of these are unusual or
version-conflicting; `pip install` reported no dependency resolution
errors.

**Confirmed absent at Phase 4** (verified via `pip list` grep, per the
Phase 4 instruction not to install these yet): LangChain, LangGraph, FAISS/
faiss-cpu, FastAPI, uvicorn, Streamlit, torch, transformers,
sentence-transformers. These remained global-only (Phase 0 finding) — not
present in `.venv` **at that point in the project**. `faiss-cpu`, `torch`,
`sentence-transformers`, and `transformers` were subsequently installed in
Phase 8 for the retrieval index (see the Phase 12 note at the top of this
document); FastAPI, uvicorn, Streamlit, LangChain, and LangGraph remain
absent for the life of the project.

**Verification performed**: imported all 8 requested packages from the
venv interpreter (`sys.executable` confirmed pointing at
`.venv\Scripts\python.exe`), and ran a live DuckDB query
(`SELECT 1+1` → `2`) to confirm the installation is functional, not
just present on disk.

Note: package versions above are current as of the install date
(2026-09-15) and are newer than what was originally sketched in this
document's earlier "Preferred" sections below (e.g. pandas 3.x rather
than 2.x) — the sections below describe intended *usage*, not a
pinned version target; this table is the source of truth for actual
installed versions.

---

# Core Language

Python 3.11+ — actually running **3.12.6** in `.venv` (see above).

Use a project-local `.venv`. Done — see above. Located at
`E:\hiver-support-agent\.venv` (project-local, on the `E:` drive since
`C:` has very little free space).

All dependencies should eventually be installed inside `.venv`.
Currently installed: the Phase 4 minimum set above only.

The `.venv` directory must never be committed to Git — enforced via
`.gitignore` (the repository was still pre-`git init` when this rule was
first written; it is a public GitHub repository now).

---

# Data Processing

Preferred:

- Polars
- DuckDB
- Parquet

## Polars

Use for efficient dataframe processing and transformations.

## DuckDB

Use for analytical queries over large CSV/Parquet datasets.

Potential uses:

- brand frequency analysis
- author analysis
- conversation statistics
- sampling
- data-quality analysis

## Parquet

Use processed Parquet files where practical.

Keep raw data untouched.

---

# Primary Dataset

Customer Support on Twitter.

Source:

https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter

Primary uses:

- brand selection
- conversation reconstruction
- intent discovery
- historical resolution corpus
- golden evaluation
- agent evaluation

---

# Secondary Dataset

Banking77.

Source:

https://huggingface.co/datasets/PolyAI/banking77

Intent work only.

Do not include Banking77 in the historical-resolution retrieval corpus.

Do not use Banking77 to justify brand-specific response behavior.

---

# Intent Classification

We will experiment with multiple approaches.

## Baseline 1

Majority-class classifier.

## Baseline 2

Simple LLM-based classification.

## Candidate Proposed Approaches

Potentially:

- embedding nearest-neighbour classification
- few-shot classification
- supervised classifier
- hybrid embedding + LLM approach

The final approach will be selected using evaluation results.

Do not assume that the most complicated approach is best.

---

# Embeddings

Potential candidates:

- Sentence Transformers
- local embedding model
- embedding API

Selection criteria:

- retrieval quality
- hardware requirements
- speed
- reproducibility
- cost

---

# Retrieval

Candidate:

FAISS.

Historical Twitter conversations will be embedded and indexed.

Retrieved records should contain useful metadata such as:

- conversation ID
- customer message
- brand response
- resolution
- intent
- timestamp

The golden evaluation set must never be included in the retrieval index.

---

# LLM

Use an abstraction:

LLMClient

with implementations such as:

LocalLLMClient
GroqLLMClient

Potential local runtimes:

- Ollama
- LM Studio
- llama.cpp

Potential hosted inference:

- Groq

The application must be able to switch providers through configuration.

Example:

LLM_PROVIDER=local

or:

LLM_PROVIDER=groq

Never hard-code API keys.

---

# Reply Generation

Input:

- current customer message
- conversation context
- predicted intent
- confidence
- retrieved historical examples

Output:

- draft response
- evidence
- grounding information

The model must not invent:

- policies
- refund guarantees
- timelines
- procedures
- unsupported actions

---

# Escalation

Use a hybrid approach.

Potential signals:

- intent confidence
- retrieval confidence
- amount/quality of evidence
- intent category
- security/fraud risk
- explicit request for human
- unsupported request
- conflicting evidence

Possible outputs:

AUTO_HANDLE

or

ESCALATE

Every escalation should contain a reason.

---

# Evaluation

Use:

- scikit-learn
- custom deterministic metrics
- LLM judge
- human calibration

## Intent Metrics

- accuracy
- macro F1
- per-intent precision
- per-intent recall
- per-intent F1
- confusion matrix

## Reply Metrics

Evaluate:

- correctness
- groundedness
- helpfulness
- actionability
- brand consistency
- hallucination

## Escalation Metrics

Evaluate:

- precision
- recall
- F1
- unsafe auto-resolution rate
- unnecessary escalation rate

---

# LLM Judge

Use an LLM to evaluate reply quality.

Potential rubric:

1. Correctness
2. Groundedness
3. Helpfulness
4. Actionability
5. Brand consistency
6. Hallucination

The judge must be calibrated against human evaluation.

The project must report how well the automated judge agrees with humans.

---

# API

Potential API:

FastAPI

Example:

POST /predict

Input:

{
"message": "..."
}

Output:

{
"intent": "...",
"confidence": 0.0,
"action": "AUTO_HANDLE",
"reply": "...",
"evidence": [],
"reason": null
}

---

# Testing

pytest.

Focus on:

- data transformations
- conversation reconstruction
- intent classification
- retrieval
- escalation policy
- structured outputs
- evaluation metrics

---

# Optional Demo

Streamlit may be used for a small demonstration UI.

The UI is lower priority than:

- evaluation
- reproducibility
- failure analysis
- report quality

---

# Dependencies

Do not install the complete stack immediately.

Install dependencies incrementally after the environment and dataset
audit.

Avoid unnecessary packages.
