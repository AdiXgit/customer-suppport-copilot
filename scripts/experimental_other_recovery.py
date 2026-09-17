"""
Phase 7E, Step 2/3: EXPERIMENTAL rule-improvement proposal for the
OTHER/UNKNOWN bucket.

This module does NOT modify src/intent/deterministic_classifier.py and
does NOT touch data/processed/twitter/spotifycares_intent_corpus.parquet.
It defines a small number of additional, narrowly-scoped candidate
patterns -- found via the Step 1 loose-signal audit in
spotifycares_other_analysis.json -- and measures what they would
recover from the CURRENT production OTHER/UNKNOWN rows, purely as an
experiment. Nothing here is applied to the production corpus.

Candidate additions and their motivating evidence (see audit in the
Phase 7E report):

1. TECHNICAL: "glitch(y|ing)?", bare "error" (not just "error message"),
   "deactivat(ed|ing)", "stuck" co-occurring with "load", and
   "still/constantly + skip/pause/stop/disconnect/freeze" (production
   only matched "keeps? <verb>", missing "still skipping" phrasing).
   Evidence: 7/8 audited E_technical loose-hits were genuine technical
   malfunctions the production regex missed on vocabulary alone.

2. CONTENT: "<song/album/track noun> ... is not available" without
   requiring the literal "on/available on/in spotify" suffix the
   production regex currently demands.
   Evidence: audited F_content examples were almost all genuine
   ("this song is not available", "says song not available") but used
   phrasing the production regex's suffix requirement excludes.

3. FEATURE: "wish <mention-or-brand-word> had/would/could", where
   <mention-or-brand-word> also accepts an anonymized @-mention
   (e.g. "@115888"), not just the literal words "you"/"spotify".
   Evidence: this Twitter dataset anonymizes the brand handle as a
   numeric @-mention; the production wish-pattern only recognizes the
   literal words "you"/"spotify" and therefore systematically misses
   any wish phrased as "I wish @115888 had...".

4. MARKET: extend the whole-service noun-phrase alternation to include
   "your app"/"your service" (customers very often address the brand
   in second person -- "why is your app not available in India" --
   which the production pattern does not recognize because it only
   lists "the app"/"this app", not "your app").

Each candidate is deliberately narrow and was chosen because it is a
vocabulary/phrasing gap in an ALREADY-EXISTING production rule
category, not a new category or a loosened precision bar.

Usage:
    .venv/Scripts/python.exe scripts/experimental_other_recovery.py

Reads (read-only): data/processed/twitter/spotifycares_intent_corpus.parquet
Writes: data/processed/twitter/spotifycares_other_recovery_experiment.json
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from intent.deterministic_classifier import (  # noqa: E402
    BILLING,
    CONTENT,
    FEATURE,
    MARKET,
    OTHER,
    TECHNICAL,
    classify_text,
)

CORPUS_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_corpus.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_other_recovery_experiment.json"

SEED = 7
AUDIT_SAMPLE_SIZE = 60  # per-category manual-style audit sample size (seeded)

# ---------------------------------------------------------------------
# Candidate experimental patterns (see module docstring for evidence)
# ---------------------------------------------------------------------

_EXP_TECHNICAL_RE = re.compile(
    r"\bglitch(y|ing|es)?\b|\berror\b|\bdeactivat(ed|ing)\b|"
    r"\bstuck\b[^.?!\n]{0,15}\bload(ing)?\b|"
    r"\b(still|constantly|keeps?)\b[^.?!\n]{0,10}\b(skip(ping)?|pausing|stopping|"
    r"disconnecting|cutting out|freezing)\b",
    re.IGNORECASE,
)

_EXP_CONTENT_RE = re.compile(
    r"\b(song|album|track|artist|podcast)\b[^.?!\n]{0,20}\b(is|are)\s*(not|n'?t)\s*available\b",
    re.IGNORECASE,
)

_EXP_FEATURE_RE = re.compile(
    r"\bwish\b[^.?!\n]{0,20}\b(@\w+|you|spotify)\b[^.?!\n]{0,10}\b(had|would|could)\b",
    re.IGNORECASE,
)

_EXP_MARKET_RE = re.compile(
    r"\b(your app|your service)\b[^.?!\n]{0,40}\b(available|launch(ed|ing)?)\b"
    r"[^.?!\n]{0,30}\b(in|to)\b[^.?!\n]{0,25}\b[A-Z][a-zA-Z]+\b",
    re.IGNORECASE,
)

_EXPERIMENTAL_RULES = [
    ("exp_technical_vocab_gap", TECHNICAL, _EXP_TECHNICAL_RE),
    ("exp_content_not_available_phrasing", CONTENT, _EXP_CONTENT_RE),
    ("exp_feature_wish_with_mention", FEATURE, _EXP_FEATURE_RE),
    ("exp_market_your_app_phrasing", MARKET, _EXP_MARKET_RE),
]


def classify_experimental(text: str):
    """Production classify_text first; if OTHER, try experimental
    add-on rules layered on top (never replacing production logic)."""
    base = classify_text(text)
    if base.primary_intent != OTHER:
        return base, None
    for reason, intent, pattern in _EXPERIMENTAL_RULES:
        if pattern.search(text or ""):
            return base, (intent, reason)
    return base, None


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(f"Intent corpus not found at {CORPUS_PATH}")

    before_mtime = CORPUS_PATH.stat().st_mtime
    df = pl.read_parquet(CORPUS_PATH)
    other = df.filter(pl.col("primary_intent") == OTHER)
    n_other_before = other.height

    recovered_counts = Counter()
    recovered_examples: dict[str, list[dict]] = {}
    still_other = 0

    for row in other.iter_rows(named=True):
        _, exp = classify_experimental(row["customer_message"])
        if exp is None:
            still_other += 1
            continue
        intent, reason = exp
        recovered_counts[reason] += 1
        bucket = recovered_examples.setdefault(reason, [])
        if len(bucket) < 15:
            bucket.append({
                "resolution_id": row["resolution_id"],
                "customer_message": row["customer_message"],
                "proposed_intent": intent,
            })

    assert CORPUS_PATH.stat().st_mtime == before_mtime, "Intent corpus must not be modified by experiment!"

    n_recovered = sum(recovered_counts.values())

    # Seeded audit sub-sample per experimental rule for a precision estimate.
    import random
    rng = random.Random(SEED)
    audit_sample = {}
    for reason, examples in recovered_examples.items():
        k = min(AUDIT_SAMPLE_SIZE, len(examples))
        audit_sample[reason] = rng.sample(examples, k) if k < len(examples) else examples

    report = {
        "seed": SEED,
        "note": (
            "EXPERIMENTAL ONLY. Production src/intent/deterministic_classifier.py "
            "and data/processed/twitter/spotifycares_intent_corpus.parquet were "
            "NOT modified. This measures what a small set of proposed, narrowly-"
            "scoped rule additions (see module docstring for evidence) would "
            "recover from the existing OTHER/UNKNOWN bucket, for human review."
        ),
        "other_unknown_before": n_other_before,
        "other_unknown_after_experimental_rules": still_other,
        "total_recovered": n_recovered,
        "recovered_fraction_of_other_bucket": round(n_recovered / n_other_before, 4),
        "recovered_fraction_of_full_corpus": round(n_recovered / df.height, 4),
        "recovered_counts_by_rule": dict(recovered_counts),
        "examples_for_manual_precision_audit": recovered_examples,
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"OTHER before: {n_other_before}")
    print(f"Recovered by experimental rules: {n_recovered} ({n_recovered / n_other_before:.2%} of OTHER bucket, "
          f"{n_recovered / df.height:.2%} of full corpus)")
    print("By rule:")
    for reason, count in recovered_counts.most_common():
        print(f"  {reason}: {count}")
    print(f"\nWrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
