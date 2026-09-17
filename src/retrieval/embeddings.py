"""
Phase 8: local sentence-embedding wrapper for the historical-resolution
retrieval layer.

Uses sentence-transformers/all-MiniLM-L6-v2 -- a small (~80MB), widely
used, CPU-practical general-purpose sentence embedding model. No
OpenAI/Anthropic/Groq embeddings are used anywhere in this module.

Model facts (recorded here per Phase 8 Step 2 instructions):
  - model: sentence-transformers/all-MiniLM-L6-v2
  - embedding dimension: 384
  - normalization: L2-normalized at encode time (so cosine similarity
    == inner product, which lets us use a plain FAISS IndexFlatIP)
  - device: CPU only (no torch.cuda available in this environment;
    verified via torch.cuda.is_available() == False at install time)
  - cache: first call downloads the model into the default
    sentence-transformers cache directory (~/.cache/torch/sentence_transformers
    or HF cache); subsequent calls are local/offline.
"""

from __future__ import annotations

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
DEFAULT_BATCH_SIZE = 64

_model = None


def get_model():
    """Lazily load and cache the sentence-transformers model (avoids
    paying model-load cost when this module is only imported for its
    constants, e.g. in tests)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def embed_texts(texts: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> np.ndarray:
    """Encode a list of strings into L2-normalized float32 vectors of
    shape (len(texts), EMBEDDING_DIMENSION). Empty input returns an
    empty (0, EMBEDDING_DIMENSION) array rather than erroring."""
    if not texts:
        return np.zeros((0, EMBEDDING_DIMENSION), dtype=np.float32)
    model = get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vectors.astype(np.float32)


def embed_query(text: str) -> np.ndarray:
    """Encode a single query string into a (1, EMBEDDING_DIMENSION) vector."""
    return embed_texts([text])
