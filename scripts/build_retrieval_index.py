"""
Phase 8, Steps 1-3 & 6: build the SpotifyCares historical-resolution
retrieval index.

Usage:
    .venv/Scripts/python.exe scripts/build_retrieval_index.py

Reads (read-only):
    data/processed/twitter/spotifycares_intent_corpus.parquet
    data/golden/golden_set_candidates.jsonl
    data/golden/golden_set_annotations.jsonl

Writes:
    data/retrieval/spotifycares.index            (FAISS IndexFlatIP)
    data/retrieval/spotifycares_vectors.npy       (raw normalized vectors,
                                                    same row order as metadata --
                                                    used for intent-filtered
                                                    brute-force search)
    data/retrieval/spotifycares_metadata.parquet  (one row per indexed record,
                                                    same order as the FAISS index)
    data/retrieval/spotifycares_retrieval_quality.json

Does NOT modify the source corpus or the golden set.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from retrieval.embeddings import DEFAULT_BATCH_SIZE, EMBEDDING_DIMENSION, MODEL_NAME, embed_texts  # noqa: E402
from retrieval.index import build_faiss_index, build_retrieval_records, save_index  # noqa: E402

CORPUS_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_corpus.parquet"
GOLDEN_CANDIDATES_PATH = REPO_ROOT / "data" / "golden" / "golden_set_candidates.jsonl"
GOLDEN_ANNOTATIONS_PATH = REPO_ROOT / "data" / "golden" / "golden_set_annotations.jsonl"

OUT_DIR = REPO_ROOT / "data" / "retrieval"
INDEX_PATH = OUT_DIR / "spotifycares.index"
VECTORS_PATH = OUT_DIR / "spotifycares_vectors.npy"
METADATA_PATH = OUT_DIR / "spotifycares_metadata.parquet"
QUALITY_PATH = OUT_DIR / "spotifycares_retrieval_quality.json"


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_golden_exclusion(df: pl.DataFrame) -> dict:
    """Independent Step-6 re-verification (does not trust Phase 7C's
    prior exclusion blindly). Uses the two strongest identifiers:
    exact tweet_id match and exact customer_message text match. Does
    NOT exclude on normalized-text-only collisions, per instructions."""
    golden_rows = _load_jsonl(GOLDEN_CANDIDATES_PATH) + _load_jsonl(GOLDEN_ANNOTATIONS_PATH)
    golden_tweet_ids = {r["tweet_id"] for r in golden_rows if r.get("tweet_id") is not None}
    golden_texts = {r["customer_message"] for r in golden_rows if r.get("customer_message")}

    tweet_id_hits = df.filter(pl.col("customer_tweet_id").is_in(list(golden_tweet_ids)))
    text_hits = df.filter(pl.col("customer_message").is_in(list(golden_texts)))
    hit_ids = set(tweet_id_hits["resolution_id"]) | set(text_hits["resolution_id"])

    return {
        "golden_examples_checked": len(golden_tweet_ids),
        "exact_tweet_id_matches_found_in_corpus": tweet_id_hits.height,
        "exact_text_matches_found_in_corpus": text_hits.height,
        "unique_rows_excluded_for_golden_leakage": len(hit_ids),
        "excluded_resolution_ids": sorted(hit_ids),
    }, hit_ids


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(f"Intent corpus not found at {CORPUS_PATH}")

    before_mtime = CORPUS_PATH.stat().st_mtime
    corpus_checksum = _sha256(CORPUS_PATH)

    df = pl.read_parquet(CORPUS_PATH)
    n_total = df.height

    golden_check, golden_hit_ids = verify_golden_exclusion(df)
    if golden_hit_ids:
        df = df.filter(~pl.col("resolution_id").is_in(list(golden_hit_ids)))

    n_excluded_golden = len(golden_hit_ids)
    n_after_golden = df.height

    empty_text_mask = (df["customer_message"].is_null()) | (df["customer_message"].str.strip_chars() == "")
    n_excluded_empty = int(empty_text_mask.sum())
    df = df.filter(~empty_text_mask)

    n_indexed = df.height

    records = build_retrieval_records(df)

    assert CORPUS_PATH.stat().st_mtime == before_mtime, "Source intent corpus must not be modified!"

    print(f"Embedding {n_indexed} records with {MODEL_NAME} (dim={EMBEDDING_DIMENSION})...")
    t0 = time.time()
    vectors = embed_texts(list(records["embedding_text"]), batch_size=DEFAULT_BATCH_SIZE)
    embed_elapsed = time.time() - t0
    throughput = n_indexed / embed_elapsed if embed_elapsed > 0 else 0.0

    t1 = time.time()
    index = build_faiss_index(vectors)
    index_build_elapsed = time.time() - t1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_index(index, INDEX_PATH)
    np.save(VECTORS_PATH, vectors)
    records.write_parquet(METADATA_PATH)

    index_size_bytes = INDEX_PATH.stat().st_size
    vectors_size_bytes = VECTORS_PATH.stat().st_size
    metadata_size_bytes = METADATA_PATH.stat().st_size

    intent_counts = records["primary_intent"].value_counts().sort("count", descending=True).to_dicts()
    response_type_counts = records["response_type"].value_counts().sort("count", descending=True).to_dicts()

    quality_report = {
        "build_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_corpus_path": str(CORPUS_PATH.relative_to(REPO_ROOT)),
        "source_corpus_sha256": corpus_checksum,
        "source_corpus_row_count": n_total,
        "excluded_golden_leakage": golden_check,
        "excluded_empty_customer_message": n_excluded_empty,
        "indexed_row_count": n_indexed,
        "excluded_total": n_total - n_indexed,
        "embedding_model": MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_normalization": "L2-normalized at encode time (normalize_embeddings=True)",
        "embedding_device": "cpu",
        "embedding_batch_size": DEFAULT_BATCH_SIZE,
        "index_type": "faiss.IndexFlatIP (exact inner product over L2-normalized vectors == cosine similarity)",
        "vector_metadata_mapping": (
            "Deterministic and positional: metadata parquet row i corresponds "
            "exactly to FAISS index vector position i and spotifycares_vectors.npy "
            "row i. No row shuffling occurs anywhere in the build pipeline."
        ),
        "performance": {
            "embedding_elapsed_seconds": round(embed_elapsed, 2),
            "embedding_throughput_rows_per_second": round(throughput, 1),
            "index_build_elapsed_seconds": round(index_build_elapsed, 4),
            "index_file_size_bytes": index_size_bytes,
            "vectors_file_size_bytes": vectors_size_bytes,
            "metadata_file_size_bytes": metadata_size_bytes,
        },
        "primary_intent_distribution": intent_counts,
        "response_type_distribution": response_type_counts,
        "low_info_customer_message_count": int(records["low_info_customer_message"].sum()),
        "rows_using_root_context_in_embedding_text": int(
            records.filter(pl.col("context_root_message").is_not_null() & pl.col("low_info_customer_message")).height
        ),
    }

    QUALITY_PATH.write_text(json.dumps(quality_report, indent=2, default=str), encoding="utf-8")

    print(f"Indexed: {n_indexed} / {n_total} (excluded {n_total - n_indexed}: "
          f"{n_excluded_golden} golden-leakage, {n_excluded_empty} empty-message)")
    print(f"Embedding throughput: {throughput:.1f} rows/sec")
    print(f"Wrote: {INDEX_PATH}")
    print(f"Wrote: {VECTORS_PATH}")
    print(f"Wrote: {METADATA_PATH}")
    print(f"Wrote: {QUALITY_PATH}")


if __name__ == "__main__":
    main()
