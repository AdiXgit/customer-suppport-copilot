"""
Phase 8, Steps 7-10: retrieval quality evaluation.

Builds a reproducible evaluation query set from the ALREADY-INDEXED,
already golden-free retrieval metadata (data/retrieval/spotifycares_metadata.parquet)
-- never from the golden set, and never used to tune the retriever.

For each query row we search the index with itself excluded
(leave-one-out), so a query never trivially retrieves its own row.

Metrics (documented precisely here since there is no external labeled
"correct document" for this corpus -- the only available reference
signal is the Phase 7D deterministic primary_intent label):

  - Recall@k ("hit rate"): fraction of eligible queries (primary_intent
    != OTHER/UNKNOWN) for which AT LEAST ONE of the top-k results
    (self excluded) shares the query's primary_intent. This treats
    "same deterministic intent" as the practical relevance signal --
    it is a proxy, not proof that the retrieved case actually resolves
    the same problem (that requires the manual audit in Step 7/10).
  - same-intent@k: average fraction of the top-k results (self
    excluded) that share the query's primary_intent -- a precision-at-k
    view of the same signal.

Both metrics are computed for GLOBAL and INTENT-FILTERED retrieval
(Step 8) so they can be compared directly. Queries with primary_intent
== OTHER/UNKNOWN are excluded from these two metrics (no meaningful
"same intent" ground truth) but ARE included in the manual-audit sample,
since Step 8 explicitly says "if intent is OTHER/UNKNOWN, evaluate
global retrieval."

Usage:
    .venv/Scripts/python.exe scripts/evaluate_retrieval.py

Reads (read-only): data/retrieval/{spotifycares.index,spotifycares_metadata.parquet,spotifycares_vectors.npy}
Writes: data/retrieval/spotifycares_retrieval_evaluation.json
"""

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from retrieval.retriever import Retriever, OTHER_INTENT  # noqa: E402

INDEX_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares.index"
METADATA_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_metadata.parquet"
VECTORS_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_vectors.npy"
OUTPUT_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_retrieval_evaluation.json"

SEED = 99
EVAL_SAMPLE_SIZE = 1000       # for quantitative recall / same-intent metrics
MANUAL_AUDIT_SAMPLE_SIZE = 40  # for the human-readable audit dump
K_VALUES = [1, 3, 5, 10]
MAX_K = max(K_VALUES)


def recall_and_precision_at_k(retriever: Retriever, queries: pl.DataFrame, intent_filtered: bool) -> dict:
    hit_at_k = {k: 0 for k in K_VALUES}
    precision_sum_at_k = {k: 0.0 for k in K_VALUES}
    n_eligible = 0

    for row in queries.iter_rows(named=True):
        query_intent = row["primary_intent"]
        if query_intent == OTHER_INTENT:
            continue
        n_eligible += 1

        intent_arg = query_intent if intent_filtered else None
        results = retriever.search(
            row["customer_message"], k=MAX_K, intent=intent_arg,
            exclude_retrieval_ids={row["retrieval_id"]},
        )
        result_intents = [r["primary_intent"] for r in results]

        for k in K_VALUES:
            top_k = result_intents[:k]
            if any(i == query_intent for i in top_k):
                hit_at_k[k] += 1
            if top_k:
                precision_sum_at_k[k] += sum(1 for i in top_k if i == query_intent) / len(top_k)

    return {
        "n_eligible_queries": n_eligible,
        "recall_at_k": {str(k): round(hit_at_k[k] / n_eligible, 4) if n_eligible else None for k in K_VALUES},
        "same_intent_at_k": {str(k): round(precision_sum_at_k[k] / n_eligible, 4) if n_eligible else None for k in K_VALUES},
    }


def duplicate_analysis(metadata: pl.DataFrame) -> dict:
    msg_counts = Counter(metadata["customer_message"].to_list())
    dup_groups = {msg: c for msg, c in msg_counts.items() if c > 1}
    resp_counts = Counter(metadata["historical_brand_response"].to_list())
    dup_resp_groups = {r: c for r, c in resp_counts.items() if c > 1}
    return {
        "exact_duplicate_customer_message_groups": len(dup_groups),
        "exact_duplicate_customer_message_rows": sum(dup_groups.values()),
        "exact_duplicate_brand_response_groups": len(dup_resp_groups),
        "exact_duplicate_brand_response_rows": sum(dup_resp_groups.values()),
        "duplicate_retrieval_ids": (
            metadata.height - metadata["retrieval_id"].n_unique()
        ),
        "note": (
            "Repeated real historical customer messages/responses are not "
            "automatically removed -- they reflect genuinely common support "
            "patterns. Flagged here only so retrieval-metric interpretation "
            "accounts for the possibility that near-identical historical "
            "cases inflate apparent recall."
        ),
    }


def build_manual_audit_sample(retriever: Retriever, metadata: pl.DataFrame, seed: int, n: int) -> list[dict]:
    rng = random.Random(seed)
    indices = rng.sample(range(metadata.height), min(n, metadata.height))
    sample = []
    for idx in indices:
        row = metadata.row(idx, named=True)
        global_results = retriever.search(
            row["customer_message"], k=3, exclude_retrieval_ids={row["retrieval_id"]},
        )
        intent_results = retriever.search(
            row["customer_message"], k=3, intent=row["primary_intent"],
            exclude_retrieval_ids={row["retrieval_id"]},
        )
        sample.append({
            "query_retrieval_id": row["retrieval_id"],
            "query_customer_message": row["customer_message"],
            "query_primary_intent": row["primary_intent"],
            "query_response_type": row["response_type"],
            "query_low_info": row["low_info_customer_message"],
            "global_top3": [
                {
                    "rank": r["rank"], "score": round(r["similarity_score"], 4),
                    "customer_message": r["customer_message"],
                    "historical_brand_response": r["historical_brand_response"],
                    "primary_intent": r["primary_intent"],
                    "response_type": r["response_type"],
                }
                for r in global_results
            ],
            "intent_filtered_top3": [
                {
                    "rank": r["rank"], "score": round(r["similarity_score"], 4),
                    "customer_message": r["customer_message"],
                    "historical_brand_response": r["historical_brand_response"],
                    "primary_intent": r["primary_intent"],
                    "response_type": r["response_type"],
                }
                for r in intent_results
            ],
            # Filled in by a separate manual-audit pass (Step 7/10) -- left
            # null here since this script does not fabricate human judgment.
            "manual_audit": {
                "problem_actually_similar": None,
                "response_relevant": None,
                "usable_resolution_evidence": None,
                "intent_compatible": None,
                "misleading_or_unrelated": None,
                "notes": None,
            },
        })
    return sample


def main() -> None:
    if not (INDEX_PATH.exists() and METADATA_PATH.exists() and VECTORS_PATH.exists()):
        raise SystemExit("Retrieval index not found -- run scripts/build_retrieval_index.py first")

    t0 = time.time()
    retriever = Retriever(INDEX_PATH, METADATA_PATH, VECTORS_PATH)
    metadata = retriever.metadata

    rng = random.Random(SEED)
    eval_indices = rng.sample(range(metadata.height), min(EVAL_SAMPLE_SIZE, metadata.height))
    eval_queries = metadata[eval_indices]

    print(f"Evaluating on {eval_queries.height} sampled queries (seed={SEED})...")

    t_query0 = time.time()
    _ = retriever.search(eval_queries.row(0, named=True)["customer_message"], k=5)
    single_query_latency = time.time() - t_query0

    global_metrics = recall_and_precision_at_k(retriever, eval_queries, intent_filtered=False)
    intent_metrics = recall_and_precision_at_k(retriever, eval_queries, intent_filtered=True)

    dup_report = duplicate_analysis(metadata)

    manual_sample = build_manual_audit_sample(retriever, metadata, seed=SEED, n=MANUAL_AUDIT_SAMPLE_SIZE)

    elapsed = time.time() - t0

    report = {
        "seed": SEED,
        "eval_sample_size": eval_queries.height,
        "manual_audit_sample_size": len(manual_sample),
        "methodology": (
            "Eval queries are a seeded sample of ALREADY-INDEXED, golden-free "
            "retrieval metadata rows -- never the golden set. Each query is "
            "searched with its own retrieval_id excluded (leave-one-out), so "
            "it cannot trivially retrieve itself. 'Relevance' for Recall@k / "
            "same-intent@k is defined as sharing the query's Phase 7D "
            "deterministic primary_intent label -- a proxy signal, not human "
            "judgment; human judgment is captured separately in the "
            "manual_audit_sample for a small seeded subset."
        ),
        "global_retrieval": global_metrics,
        "intent_filtered_retrieval": intent_metrics,
        "duplicate_analysis": dup_report,
        "performance": {
            "single_query_latency_seconds": round(single_query_latency, 4),
            "total_evaluation_elapsed_seconds": round(elapsed, 2),
        },
        "manual_audit_sample": manual_sample,
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"Global   Recall@k: {global_metrics['recall_at_k']}  same-intent@k: {global_metrics['same_intent_at_k']}")
    print(f"IntentFl Recall@k: {intent_metrics['recall_at_k']}  same-intent@k: {intent_metrics['same_intent_at_k']}")
    print(f"Duplicates: {dup_report['exact_duplicate_customer_message_groups']} groups / "
          f"{dup_report['exact_duplicate_customer_message_rows']} rows")
    print(f"Wrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
