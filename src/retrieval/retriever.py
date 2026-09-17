"""
Phase 8: retrieval API.

Retriever.search(query, k=5, intent=None) -> list[dict]

Two modes, chosen per-call (Step 4 -- no assumption that intent
filtering is automatically better):

  - global (intent=None or intent == "OTHER / UNKNOWN"): FAISS exact
    inner-product search over the full index.
  - intent-filtered (intent is one of the 8 substantive canonical
    intents): restrict the candidate pool to metadata rows whose
    primary_intent matches, then brute-force cosine (matrix dot
    product with the pre-normalized vectors kept in memory) over just
    that subset. Brute force is deliberate: the largest intent subset
    (Billing, ~6k rows x 384 dims) is trivially small for a dot
    product, so introducing a second FAISS index per intent would add
    complexity with no measurable benefit at this corpus size.

If a caller passes an intent with zero matching rows in the metadata
(e.g. a typo, or a subset that happens to be empty), search falls back
to global retrieval rather than raising -- this mirrors the Phase 7D
principle "never force a query into a filter that has no evidence."
"""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
import polars as pl

from .embeddings import embed_query

OTHER_INTENT = "OTHER / UNKNOWN"


class Retriever:
    def __init__(self, index_path: Path | str, metadata_path: Path | str, vectors_path: Path | str):
        self.index = faiss.read_index(str(index_path))
        self.metadata = pl.read_parquet(metadata_path)
        self.vectors = np.load(vectors_path)
        if self.vectors.shape[0] != self.metadata.height:
            raise ValueError(
                f"Vector/metadata row-count mismatch: {self.vectors.shape[0]} vectors "
                f"vs {self.metadata.height} metadata rows -- index is corrupt or stale."
            )
        if self.index.ntotal != self.metadata.height:
            raise ValueError(
                f"FAISS index size ({self.index.ntotal}) does not match metadata "
                f"row count ({self.metadata.height}) -- index is corrupt or stale."
            )
        self._intent_positions: dict[str, np.ndarray] = {}
        for intent in self.metadata["primary_intent"].unique():
            mask = (self.metadata["primary_intent"] == intent).to_numpy()
            self._intent_positions[intent] = np.nonzero(mask)[0]

    def __len__(self) -> int:
        return self.metadata.height

    def _row_to_result(self, position: int, rank: int, score: float) -> dict:
        row = self.metadata.row(position, named=True)
        return {
            "rank": rank,
            "similarity_score": float(score),
            "retrieval_id": row["retrieval_id"],
            "conversation_id": row["conversation_id"],
            "customer_tweet_id": row["customer_tweet_id"],
            "customer_message": row["customer_message"],
            "context_root_message": row["context_root_message"],
            "historical_brand_response": row["historical_brand_response"],
            "response_type": row["response_type"],
            "primary_intent": row["primary_intent"],
            "customer_timestamp": row["customer_timestamp"],
        }

    def search(self, query: str, k: int = 5, intent: str | None = None,
               exclude_retrieval_ids: set[str] | None = None) -> list[dict]:
        """Returns up to k results, ranked most-similar first.

        - Empty/whitespace-only query returns [].
        - k is clipped to the size of the searchable candidate pool.
        - exclude_retrieval_ids lets evaluation code do leave-one-out
          search (exclude a query's own historical row from its own
          results) without needing a second index.
        """
        if not query or not query.strip():
            return []
        if k <= 0:
            return []

        query_vec = embed_query(query)

        use_intent_filter = intent is not None and intent != OTHER_INTENT and intent in self._intent_positions
        exclude_retrieval_ids = exclude_retrieval_ids or set()

        if use_intent_filter:
            positions = self._intent_positions[intent]
            if len(positions) == 0:
                use_intent_filter = False

        if use_intent_filter:
            candidate_vectors = self.vectors[positions]
            scores = candidate_vectors @ query_vec[0]
            order = np.argsort(-scores)
            results = []
            for idx in order:
                position = int(positions[idx])
                rid = self.metadata[position, "retrieval_id"]
                if rid in exclude_retrieval_ids:
                    continue
                results.append((position, float(scores[idx])))
                if len(results) >= k:
                    break
            return [self._row_to_result(pos, rank + 1, score) for rank, (pos, score) in enumerate(results)]

        # Global FAISS search. Over-fetch to allow room for exclusions.
        search_k = min(self.index.ntotal, k + len(exclude_retrieval_ids))
        if search_k <= 0:
            return []
        scores, indices = self.index.search(query_vec, search_k)
        results = []
        for score, position in zip(scores[0], indices[0]):
            if position < 0:
                continue
            rid = self.metadata[int(position), "retrieval_id"]
            if rid in exclude_retrieval_ids:
                continue
            results.append((int(position), float(score)))
            if len(results) >= k:
                break
        return [self._row_to_result(pos, rank + 1, score) for rank, (pos, score) in enumerate(results)]
