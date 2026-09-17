"""
Phase 8: retrieval-record schema, embedding-text derivation, and FAISS
index construction for the SpotifyCares historical resolution corpus.

Retrieval unit (Step 1)
------------------------
Each retrieval record represents ONE historical customer-message /
brand-response pair (a Phase 7B/7C "resolution candidate"), carrying
enough metadata to be shown as evidence without embedding the entire
raw conversation:

    retrieval_id                 -- == resolution_id (already a unique,
                                     traceable key: "RES-{conv}-{brand_tweet}")
    conversation_id               -- source conversation
    customer_tweet_id             -- source customer message tweet_id
    customer_message               -- the customer's own text (verbatim)
    context_root_message          -- text of the conversation's root
                                     message (context[0]) if this
                                     candidate is NOT itself the root,
                                     else null. A compact stand-in for
                                     "relevant preceding conversation"
                                     instead of embedding the full
                                     context_messages_json blob.
    number_of_context_messages    -- how many prior turns preceded this
                                     candidate (0 == this IS the root)
    historical_brand_response      -- the brand's reply text (verbatim)
    response_type                 -- substantive_response / dm_redirect /
                                     clarification_question / acknowledgement
                                     (Phase 7B classification -- surfaced
                                     so downstream consumers can judge
                                     evidence quality, e.g. discount a
                                     dm_redirect's evidentiary value)
    primary_intent                 -- Phase 7D deterministic intent label
                                     (may be "OTHER / UNKNOWN")
    labeling_method                -- how primary_intent was produced
                                     (deterministic / deterministic_root_context)
    customer_timestamp / brand_timestamp
    low_info_customer_message      -- Phase 7B quality flag (bare/short message)
    cross_brand_response           -- Phase 7B quality flag

Embedding text derivation
--------------------------
For most rows the embedding text is simply the customer_message. For
rows flagged low_info_customer_message == True (a bare/short follow-up
like "ok" or "yes") the customer_message alone is not informative, so
the embedding text is the ROOT message text plus the candidate's own
message, mirroring the same root-context-fallback design already used
by the Phase 7D deterministic classifier (src/intent/deterministic_classifier.py's
classify_candidate) rather than inventing a new convention. This keeps
the embedded text compact (one short root message + one short follow-up)
instead of concatenating the entire conversation.

Golden-set exclusion (Step 6) is performed by the caller
(scripts/build_retrieval_index.py) BEFORE these functions are used --
this module has no golden-set awareness at all, by design.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
import polars as pl

METADATA_COLUMNS = [
    "retrieval_id",
    "conversation_id",
    "customer_tweet_id",
    "customer_message",
    "context_root_message",
    "number_of_context_messages",
    "historical_brand_response",
    "response_type",
    "primary_intent",
    "labeling_method",
    "customer_timestamp",
    "brand_timestamp",
    "low_info_customer_message",
    "cross_brand_response",
    "embedding_text",
]


def _extract_root_text(context_messages_json: str | None) -> str | None:
    if not context_messages_json:
        return None
    try:
        context = json.loads(context_messages_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not context:
        return None
    return context[0].get("text")


def build_embedding_text(customer_message: str, root_text: str | None, low_info: bool) -> str:
    """See module docstring 'Embedding text derivation'."""
    customer_message = customer_message or ""
    if low_info and root_text:
        return f"{root_text} {customer_message}".strip()
    return customer_message


def build_retrieval_records(df: pl.DataFrame) -> pl.DataFrame:
    """Given a joined intent+resolution dataframe (one row per
    resolution candidate, already golden-filtered by the caller),
    produce the retrieval-metadata dataframe with derived columns.
    Row order is preserved -- this order IS the FAISS vector order."""
    root_texts = [_extract_root_text(v) for v in df["context_messages_json"]]
    embedding_texts = [
        build_embedding_text(msg, root, low_info)
        for msg, root, low_info in zip(df["customer_message"], root_texts, df["low_info_customer_message"])
    ]

    out = df.with_columns([
        pl.Series("retrieval_id", df["resolution_id"]),
        pl.Series("context_root_message", root_texts),
        pl.Series("historical_brand_response", df["brand_response"]),
        pl.Series("embedding_text", embedding_texts),
    ])
    return out.select(METADATA_COLUMNS)


def build_faiss_index(vectors: np.ndarray) -> faiss.Index:
    """Flat, exact inner-product index. Vectors must already be
    L2-normalized (see src/retrieval/embeddings.py) so inner product
    == cosine similarity. Flat/exact is intentional for a ~40k-row
    prototype -- no approximate-index tuning needed at this scale."""
    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    if vectors.shape[0] > 0:
        index.add(vectors)
    return index


def save_index(index: faiss.Index, path: Path) -> None:
    faiss.write_index(index, str(path))


def load_index(path: Path) -> faiss.Index:
    return faiss.read_index(str(path))
