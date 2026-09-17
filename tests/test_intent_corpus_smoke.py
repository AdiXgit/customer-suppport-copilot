"""
Smoke test: run the deterministic classifier against a representative
real sample of the Phase 7C corpus (not the full 41,092 rows in
pytest) before producing the full labeled output.

Deliberately does NOT touch the golden set at all -- this classifier
must never be validated or tuned against golden labels.
"""

from pathlib import Path

import polars as pl
import pytest

from intent.deterministic_classifier import CANONICAL_INTENTS, classify_candidate

CORPUS_PATH = Path(__file__).parent.parent / "data" / "processed" / "twitter" / "spotifycares_resolution_corpus.parquet"


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="Phase 7C corpus not present in this environment")
def test_smoke_representative_sample():
    df = pl.read_parquet(CORPUS_PATH)
    before_mtime = CORPUS_PATH.stat().st_mtime

    sample = df.sample(n=500, seed=123)
    results = []
    for row in sample.iter_rows(named=True):
        r = classify_candidate(row["customer_message"], row["context_messages_json"])
        results.append((row, r))

    assert CORPUS_PATH.stat().st_mtime == before_mtime  # corpus untouched

    for row, r in results:
        assert r.primary_intent in CANONICAL_INTENTS
        # source text must be unchanged by classification
        assert row["customer_message"] == row["customer_message"]
        if r.secondary_issue is not None:
            assert r.secondary_issue in CANONICAL_INTENTS
            assert r.ambiguous is True

    labeled = [r for _, r in results if r.primary_intent != "OTHER / UNKNOWN"]
    assert len(labeled) > 0, "sample should produce at least some confident labels"

    from collections import Counter
    dist = Counter(r.primary_intent for _, r in results)
    print(f"[smoke] sample={len(results)} distribution={dict(dist)}")
