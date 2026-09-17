# Hiver SDE Intern Take-Home — Project Instructions

## Project

We are building the Hiver SDE Intern take-home assignment.

The goal is to build and evaluate a brand-specific AI customer-support
agent using real customer-support conversations from Twitter.

The agent must:

1. Classify an incoming customer message into an intent taxonomy derived
   from the data.
2. Draft a reply grounded in how the selected brand historically resolved
   similar issues.
3. Decide whether the request should be AUTO_HANDLED or ESCALATED to a
   human, with a stated reason.

The most important requirement is not system complexity.

The evaluation and proof of system quality are more important than the
complexity of the implementation.

---

# Current Phase

We are currently in the RECONNAISSANCE phase.

Do NOT start building the AI agent yet.

Do NOT create the virtual environment yet.

Do NOT install project dependencies yet.

Do NOT download LLM models yet.

First understand:

1. The local development environment.
2. The available hardware.
3. Available local LLM runtimes/models.
4. The structure of the datasets.
5. The quality and size of the datasets.
6. Which brands are viable.
7. Which brand should be selected.

Only after reconnaissance will we finalize the architecture and create
the Python virtual environment.

---

# Datasets

## Primary Dataset

Customer Support on Twitter

Source:

https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter

This is the PRIMARY dataset.

Use it for:

- brand selection
- data exploration
- conversation reconstruction
- intent discovery
- intent classification
- historical resolution retrieval
- reply generation
- escalation analysis
- golden evaluation set
- final evaluation

The selected brand's historical conversations are the source of truth
for how that brand historically handled customer-support issues.

---

## Secondary Dataset

Banking77

Source:

https://huggingface.co/datasets/PolyAI/banking77

Banking77 is OPTIONAL and may only be used for INTENT-RELATED work.

Allowed uses:

- studying intent taxonomy design
- understanding fine-grained financial-support intents
- experimenting with intent classification
- testing classification approaches
- understanding ambiguous/related intent categories

Banking77 must NOT be used as:

- historical brand-response evidence
- reply-generation evidence
- brand policy evidence
- escalation evidence
- part of the selected brand's RAG/retrieval corpus

Do NOT blindly copy Banking77's 77 labels into the final project.

The final intent taxonomy must primarily come from the selected brand's
actual Twitter conversations.

---

# Data Storage

Store downloaded datasets locally.

Recommended structure:

data/
├── raw/
│ ├── twitter/
│ └── banking77/
│
├── processed/
│ ├── twitter/
│ └── banking77/
│
├── retrieval/
│ └── selected_brand/
│
└── golden/
└── golden_set.jsonl

Raw data must never be modified.

Raw datasets must never be committed to Git.

Processed data must be reproducible from the raw data.

Golden evaluation data must remain separate from the retrieval corpus.

---

# Environment

The project will eventually use:

- Python
- `.venv`
- Polars
- DuckDB
- scikit-learn
- embeddings
- FAISS or another local vector index
- configurable LLM provider
- FastAPI
- pytest
- optional Streamlit

Exact dependencies and versions must be decided AFTER the environment
audit.

Do not blindly install the entire stack.

---

# LLM Architecture

The application must use an abstraction around the LLM.

Conceptually:

LLMClient
├── LocalLLMClient
└── GroqLLMClient

The rest of the application should not depend directly on a specific
LLM provider.

We will inspect the machine first to determine whether a local LLM is
practical.

Potential local runtimes include:

- Ollama
- LM Studio
- llama.cpp
- other installed local inference runtimes

Groq may be used as a hosted inference option.

The final choice should be based on:

- quality
- latency
- hardware constraints
- reproducibility
- cost
- ease of evaluation

Never hard-code API keys.

Use environment variables.

---

# Proposed Agent

The eventual pipeline will approximately be:

Customer message
|
v
Intent classification
|
v
Historical retrieval
|
v
Resolution evidence
|
v
Reply generation
|
v
Escalation decision
|
v
Final structured response

The exact implementation must be decided after dataset analysis.

---

# Evaluation

The assignment requires a strong evaluation component.

We must eventually create:

- 150–250 hand-labelled golden examples
- at least two baselines
- automated metrics
- LLM-as-judge
- evidence of human-vs-LLM judge agreement
- top five failure modes
- real failure examples
- "What is misleading about my headline number?"
- decision log containing 10–15 non-obvious decisions

Evaluation is a first-class component of the project.

Do not optimize only for a high headline accuracy number.

---

# Baselines

At minimum:

## Baseline 1 — Trivial

Majority-class intent classifier.

## Baseline 2 — Simple

Simple LLM-based intent classifier without the full retrieval/agent
pipeline.

## Proposed System

Potentially:

intent classification

- historical retrieval
- grounded generation
- escalation policy

The exact proposed architecture must be supported by experiments.

---

# Engineering Principles

Prefer:

- simple
- modular
- reproducible
- measurable
- locally runnable
- easy to explain

Avoid unnecessary complexity.

Do NOT introduce:

- microservices
- Kubernetes
- Kafka
- Redis
- cloud vector databases
- multi-agent systems
- LangChain
- LangGraph

unless an experiment demonstrates that they provide a meaningful benefit.

The system should be understandable by an interviewer reviewing the
repository.

---

# Important Rules

1. Never invent dataset statistics.
2. Never invent evaluation results.
3. Never modify golden labels automatically.
4. Never leak golden evaluation examples into retrieval.
5. Never use Banking77 as brand-resolution evidence.
6. Never claim an LLM-generated response is grounded without evidence.
7. Record important architectural decisions.
8. Keep experiments reproducible.
9. Do not optimize the system against the test set without documenting
   the change.
10. If uncertain, inspect the data before making assumptions.

---

# Documentation

Important project documents:

docs/ENVIRONMENT.md
docs/TECH_STACK.md
docs/TODO.md

Additional documents will be created as the project develops.
