# Environment Audit

## Purpose

Determine what is already available on the development machine before
installing anything for the Hiver SDE Intern take-home assignment.

IMPORTANT:

This is an AUDIT ONLY.

Do NOT:

- create `.venv`
- install Python packages
- install system packages
- install CUDA
- install LLM runtimes
- download LLM models
- modify system configuration

Only inspect and report.

---

# 1. Operating System

Determine:

- OS
- version
- architecture

---

# 2. Python

Check:

- Python version
- Python executable path
- pip version
- whether `python` and `python3` exist
- whether they point to the same installation

Determine whether Python 3.11 or newer is available.

---

# 3. Virtual Environments

Check whether the repository currently contains:

- `.venv`
- `venv`
- other virtual environments

Do not create one.

Recommend whether we should use `.venv`.

---

# 4. Hardware

Inspect:

## CPU

Report:

- CPU model
- number of cores/threads if available

## RAM

Report:

- total RAM
- available RAM if easily accessible

## GPU

Determine whether an NVIDIA GPU exists.

If present report:

- GPU model
- VRAM
- driver version
- CUDA availability

Do not modify the CUDA installation.

---

# 5. Local LLM Runtimes

Check whether any of the following are already installed:

- Ollama
- LM Studio
- llama.cpp
- llamafile
- vLLM
- other obvious local LLM runtimes

For Ollama:

- check whether the command exists
- check whether the service is running
- list installed models
- report model names
- report model sizes if available

For LM Studio:

- determine whether a CLI/runtime is available
- do not launch or download models

For llama.cpp:

- determine whether binaries are available

Do not install anything.

---

# 6. Existing Python Packages

Determine whether the current Python environment already has these:

- numpy
- pandas
- polars
- duckdb
- scipy
- scikit-learn
- torch
- transformers
- sentence-transformers
- faiss
- faiss-cpu
- fastapi
- uvicorn
- pytest
- streamlit
- python-dotenv

Do not install missing packages.

Report versions when available.

---

# 7. Git

Check:

- Git version
- repository status

---

# 8. Disk Space

Determine available disk space.

We need enough space for:

- raw Twitter dataset
- processed data
- Parquet files
- embeddings
- vector index
- optional local LLM models

Do not download anything.

---

# 9. Dataset Directories

Check whether these directories exist:

data/
data/raw/
data/raw/twitter/
data/raw/banking77/
data/processed/

Do not create them unless explicitly instructed later.

---

# 10. Output

## Audit Results (2026-09-15)

| Component             | Available | Version / Details | Notes |
| ---------------------- | --------- | ------------------ | ----- |
| OS                    | Yes       | Windows 11 Home Single Language, build 26200, 64-bit | |
| Python                | Yes       | 3.12.6 at `C:\Users\Aditya Dwaraki Rao\AppData\Local\Programs\Python\Python312\python.exe` | Meets 3.11+ requirement. `python3` alias is broken (Microsoft Store stub); `python` and `py -3.12` resolve to the same install. No system `python3` shadowing risk. |
| pip                   | Yes       | 25.2 (python 3.12) | |
| GPU                   | Yes       | NVIDIA GeForce RTX 3060 Laptop GPU (also has integrated AMD Radeon Graphics) | Laptop dGPU; only ~6GB reported by nvidia-smi (mobile 3060 variant) |
| VRAM                  | ~6 GB     | 6144 MiB total, ~358 MiB in use at audit time | Room for small/quantized local models only |
| CUDA                  | Yes       | Driver 32.0.16.1074 (CUDA UMD 13.3); CUDA Toolkit 12.8 (`nvcc`) installed; PyTorch built with CUDA 12.1 reports `torch.cuda.is_available() == True` | GPU is usable for local inference/embeddings |
| RAM                   | Yes       | 13.86 GB total physical RAM | Modest; leave headroom for OS + browser + IDE when running local models |
| Ollama                | Yes       | v0.20.0 installed, service running (visible in `nvidia-smi` process list) | Installed models: `gemma2:9b-instruct-q4_0` (5.4 GB) and `cow/gemma2_tools:9b` (5.4 GB) |
| LM Studio             | No        | Not installed | No CLI, no install directory found |
| llama.cpp             | No        | Not installed | `main` resolved to unrelated Windows Control Panel applet, not llama.cpp |
| Polars                | No        | Not installed | |
| DuckDB                | No        | Not installed | |
| PyTorch               | Yes       | 2.5.1+cu121 (torchvision 0.20.1+cu121, torchaudio 2.5.1+cu121); also torch-geometric stack (torch_scatter/sparse/cluster/spline_conv) | CUDA-enabled build already present |
| Sentence Transformers | Yes       | 3.1.1 | transformers 4.45.2 also present |
| FAISS                 | No        | Not installed (neither `faiss` nor `faiss-cpu`) | |
| FastAPI               | Yes       | 0.115.13 | uvicorn 0.34.3 also present |
| pytest                | Yes       | 8.4.2 | |

Additional packages present but not in the checklist: numpy 1.26.3, pandas 2.2.0, scipy 1.12.0, scikit-learn 1.4.0, python-dotenv 1.1.1, streamlit 1.41.1 (+ streamlit-option-menu).

Note: these packages are installed in the **global/base Python 3.12 environment** (no `.venv` exists in the repo yet), which is why so many appear "already available."

### Virtual Environments

No `.venv` or `venv` directory exists in the repository. All the packages listed above live in the global Python 3.12 install.

### Git

- Git 2.42.0.windows.2 is installed.
- `E:\hiver-support-agent` is **not currently a git repository** (`fatal: not a git repository`).

### Disk Space

| Drive | Used | Free |
| ----- | ---- | ---- |
| C:    | 387.66 GB | 11.99 GB |
| D:    | 206.64 GB | 44.36 GB |
| E:    | 115.72 GB | 185.27 GB |

The project lives on `E:`, which has ample free space (185 GB) for raw data, Parquet, embeddings, and a vector index. `C:` is nearly full (12 GB free) — avoid installing large packages/models to a location that defaults to `C:` (e.g. default pip cache, default Ollama model store, default `.venv` if placed outside the project) without checking; keep project-local `.venv` on `E:`.

### CPU

AMD Ryzen 7 5800H, 8 cores / 16 logical processors.

### Dataset Directories

All expected directories already exist: `data/`, `data/raw/`, `data/raw/twitter/`, `data/raw/banking77/`, `data/processed/`, plus `data/golden/` and a (misspelled) `data/retriveal/` directory.

- `data/raw/twitter/twcs.csv` — **516,508,641 bytes (~493 MB)**, the full Customer Support on Twitter dataset, already present. Header: `tweet_id,author_id,inbound,created_at,text,response_tweet_id,in_response_to_tweet_id`.
- `data/raw/twitter/sample.csv` — 17,357 bytes, a small sample slice of the same schema.
- `data/raw/banking77/` — exists but is **empty**; Banking77 has not been downloaded yet.
- `data/processed/`, `data/golden/` — exist and are empty (expected at this phase).

## Environment Recommendation

1. **Python version**: Use the existing Python 3.12.6 install. It exceeds the 3.11+ requirement; no need to install a different version. Ignore the broken `python3` Microsoft Store alias — use `python` (or `py -3.12`) consistently in docs/scripts.

2. **`.venv`**: Yes, create a project-local `.venv` (not yet created, per instructions). The global Python environment already has a large, unrelated package set (torch-geometric stack, streamlit, etc.) that has nothing to do with this project — isolating into `.venv` avoids version drift and keeps the dependency list honest for the interviewer. Place it under the project root on `E:` since `C:` is nearly out of space.

3. **Local LLM inference practicality**: Practical but constrained. The RTX 3060 Laptop GPU has only ~6 GB VRAM and the machine has ~14 GB RAM total, so only small/quantized models (≤9B params, 4-bit quantization) fit comfortably alongside the OS and other apps. CUDA is correctly installed and PyTorch already detects the GPU, so GPU-accelerated embeddings or a quantized local LLM via Ollama are both feasible.

4. **Useful installed local models**: Ollama is already installed and running with `gemma2:9b-instruct-q4_0` (a 4-bit quantized 9B model, ~5.4 GB) pulled locally. This is a reasonable candidate for `LocalLLMClient` experimentation (intent classification drafts, reply drafting) without any new downloads. `cow/gemma2_tools:9b` is a tool-calling variant of the same base model, potentially useful if function-calling/structured output is needed from the local model.

5. **Groq support**: Yes, still worth supporting as `GroqLLMClient`. Given only ~6 GB VRAM, a hosted option gives access to larger, higher-quality models and avoids tying evaluation quality/latency to this machine's constrained GPU. The `LLMClient` abstraction described in CLAUDE.md/TECH_STACK.md should keep both paths swappable via `LLM_PROVIDER`.

6. **Embedding strategy**: `sentence-transformers` (3.1.1) is already installed with a CUDA-capable PyTorch backend, so a local sentence-transformers model (e.g. a small `all-MiniLM`-class model, to be selected after dataset review) run on the GPU is a practical, reproducible, zero-additional-cost embedding strategy — no need for an embedding API.

7. **FAISS**: Appropriate to add later. Not currently installed, but it's lightweight, purely local, has no GPU dependency requirement (CPU FAISS is fine at this data scale), and matches the "avoid unnecessary complexity" principle better than a cloud vector DB. Install `faiss-cpu` inside `.venv` once the retrieval design is finalized — the ~493 MB / small-brand-subset corpus size does not need FAISS-GPU.

8. **DuckDB**: Appropriate. Not currently installed, but well suited to running analytical SQL directly over the existing `data/raw/twitter/twcs.csv` (493 MB) for brand-frequency counts, author analysis, and sampling without loading the whole file into memory — a good fit given only ~14 GB RAM. Add it in `.venv` during the dataset-reconnaissance phase.

**Not yet installed but expected to be needed**: Polars, DuckDB, FAISS (or faiss-cpu). These should be added incrementally to a new `.venv`, not the global environment, once brand selection and architecture are finalized — per instructions, no installation has been performed during this audit.
