"""
Phase 7E, Step 1: characterize the 28,163-row OTHER/UNKNOWN bucket
produced by Phase 7D's deterministic classifier.

This script does NOT change any production label. It draws a
reproducible seeded sample from the OTHER/UNKNOWN rows of
spotifycares_intent_corpus.parquet and buckets each sampled row into
one of the 13 analysis categories (A-M) using *loose, exploratory*
keyword heuristics that are intentionally separate from (and broader
than) the production regexes in src/intent/deterministic_classifier.py.

These loose heuristics exist ONLY to estimate how much of OTHER might
be recoverable and where -- they are never written back as labels and
never touch data/processed/twitter/spotifycares_intent_corpus.parquet
or the golden set.

Usage:
    .venv/Scripts/python.exe scripts/analyze_other_bucket.py

Writes: data/processed/twitter/spotifycares_other_analysis.json
Reads (read-only): data/processed/twitter/spotifycares_intent_corpus.parquet
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from intent.deterministic_classifier import is_likely_non_english  # noqa: E402

CORPUS_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_corpus.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_other_analysis.json"

SEED = 42
SAMPLE_SIZE = 2000

# ---------------------------------------------------------------------
# Loose, exploratory signal detectors (NOT the production regexes).
# Deliberately broader/simpler -- used only to estimate a ceiling on
# recoverable signal, never as classification rules.
# ---------------------------------------------------------------------

_LOOSE_PATTERNS = {
    "B_access": re.compile(
        r"\b(log ?in|login|log ?out|sign ?in|sign ?up|password|username|credential|"
        r"can'?t access|verify (my )?account|reset (my )?password)\b", re.IGNORECASE),
    "C_security": re.compile(
        r"\b(hack(ed|ing)?|compromised|unauthori[sz]ed|stolen|hijack|"
        r"someone else|without my (permission|consent)|took over|fraud)\b", re.IGNORECASE),
    "D_billing": re.compile(
        r"\b(charg(e|ed|ing)|bill(ed|ing)?|payment|paypal|credit card|debit card|"
        r"refund|invoice|subscri(be|bed|bing|ption)|renew(al|ed|ing)?|cancel(l)?(ed|ing)?|"
        r"discount|promo(tion)?|coupon|gift card|price|cost|money|paid|premium)\b", re.IGNORECASE),
    "E_technical": re.compile(
        r"\b(crash(ed|ing|es)?|freez(e|es|ing)|buffer(ing)?|glitch(y|ing)?|lag(gy|ging)?|"
        r"skip(s|ping)?|error|bug\b|broken|not working|won'?t (play|load|open|work)|"
        r"slow|loading|stopped working|blank screen|disconnect)\b", re.IGNORECASE),
    "F_content": re.compile(
        r"\b(song|album|track|artist|podcast|playlist|discography|single|ep\b)\b.{0,40}"
        r"\b(missing|not (on|available)|remove(d)?|wrong|mislabel|duplicate)\b|"
        r"\bwhere('?s| is)\b.{0,40}\b(song|album|track|artist|podcast)\b", re.IGNORECASE),
    "G_feature": re.compile(
        r"\b(wish|please add|pls add|feature request|suggestion|would be (nice|great|awesome)|"
        r"add (a|an|the)?\s*(option|feature|button|dark mode)|any (chance|plans) (of|for))\b", re.IGNORECASE),
    "H_complaint": re.compile(
        r"\b(worst|terrible|horrible|disappointed|frustrat(ed|ing)|annoy(ed|ing)|awful|"
        r"hate (this|spotify|it)|sucks|angry|ridiculous|unacceptable|fed up)\b", re.IGNORECASE),
    "I_market": re.compile(
        r"\b(country|region|available in|launch in|come to|when.{0,15}available)\b", re.IGNORECASE),
}

_GREETING_ACK_RE = re.compile(
    r"^(@\w+[\s,]*)*(ok|okay|k|kk|sure|cool|nice|great|got it|will do|done|yes|yep|yup|no|nope|"
    r"same|me too|thanks|thank you|thx|ty|hi|hey|hello)[!. ]*$",
    re.IGNORECASE,
)

_LOW_INFO_SHAPE_RE = re.compile(
    r"^(@\w+[\s,]*)*([\w.+-]+@[\w.-]+|\d{6,}|[a-z0-9]{6,})[!. ]*$",
    re.IGNORECASE,
)


def strip_mentions(text: str) -> str:
    return re.sub(r"@\w+", "", text or "").strip()


def word_count(text: str) -> int:
    return len(strip_mentions(text).split())


def categorize(row: dict) -> tuple[str, list[str]]:
    """Returns (primary_category, all_loose_signal_hits)."""
    msg = row["customer_message"] or ""
    wc = word_count(msg)

    hits = [name for name, pat in _LOOSE_PATTERNS.items() if pat.search(msg)]

    # L: bare follow-up / metadata-like content, no substantive text
    if row["low_info_customer_message"]:
        return "L_bare_or_metadata", hits
    if wc <= 3 and not hits:
        return "L_bare_or_metadata", hits
    if _GREETING_ACK_RE.match(msg.strip()) or _LOW_INFO_SHAPE_RE.match(strip_mentions(msg)):
        return "L_bare_or_metadata", hits

    # K: non-English / insufficiently interpretable
    if is_likely_non_english(msg) and not hits:
        return "K_non_english", hits

    if len(hits) == 0:
        return "A_genuinely_other", hits
    if len(hits) == 1:
        return hits[0], hits
    return "J_ambiguous_multi_intent", hits


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(f"Intent corpus not found at {CORPUS_PATH}")

    before_mtime = CORPUS_PATH.stat().st_mtime
    df = pl.read_parquet(CORPUS_PATH)

    other = df.filter(pl.col("primary_intent") == "OTHER / UNKNOWN")
    n_other_total = other.height

    sample = other.sample(n=min(SAMPLE_SIZE, n_other_total), seed=SEED)

    category_counts: Counter = Counter()
    examples_by_category: dict[str, list[dict]] = {}
    response_type_by_category: dict[str, Counter] = {}
    length_stats: list[int] = []

    for row in sample.iter_rows(named=True):
        cat, hits = categorize(row)
        category_counts[cat] += 1
        length_stats.append(word_count(row["customer_message"]))

        response_type_by_category.setdefault(cat, Counter())[row["response_type"]] += 1

        bucket = examples_by_category.setdefault(cat, [])
        if len(bucket) < 8:
            bucket.append({
                "resolution_id": row["resolution_id"],
                "conversation_id": row["conversation_id"],
                "customer_message": row["customer_message"],
                "response_type": row["response_type"],
                "non_english": row["non_english"],
                "low_info_customer_message": row["low_info_customer_message"],
                "loose_signal_hits": hits,
                "number_of_context_messages": row["number_of_context_messages"],
            })

    assert CORPUS_PATH.stat().st_mtime == before_mtime, "Intent corpus must not be modified by analysis!"

    n_sample = sample.height
    report = {
        "methodology": (
            "Reproducible seeded sample drawn from the OTHER/UNKNOWN rows of "
            "spotifycares_intent_corpus.parquet (Polars .sample(seed=...)). "
            "Each sampled row is bucketed using LOOSE, exploratory keyword "
            "heuristics (src defined inline in scripts/analyze_other_bucket.py, "
            "intentionally separate from and broader than the production "
            "regexes in src/intent/deterministic_classifier.py). These "
            "heuristics estimate a CEILING on potentially recoverable signal "
            "-- they are exploratory only and are never written back as "
            "production labels. Categories with a single loose-signal hit "
            "are labeled by that candidate intent letter; two or more hits "
            "are 'J_ambiguous_multi_intent'; bare/short/metadata-like "
            "messages are 'L_bare_or_metadata'; non-English text with no "
            "signal is 'K_non_english'; everything else with zero signal is "
            "'A_genuinely_other'. No golden-set data was read or used."
        ),
        "seed": SEED,
        "sampling_method": "polars.DataFrame.sample(n=sample_size, seed=seed), sampled from primary_intent == 'OTHER / UNKNOWN'",
        "other_unknown_bucket_total": n_other_total,
        "sample_size": n_sample,
        "sample_fraction_of_bucket": round(n_sample / n_other_total, 4),
        "category_legend": {
            "A_genuinely_other": "No loose signal for any of the 8 substantive intents; likely genuinely OTHER/UNKNOWN",
            "B_access": "Likely Account Access & Login",
            "C_security": "Likely Account Security",
            "D_billing": "Likely Premium Subscription & Billing",
            "E_technical": "Likely App & Playback Technical Issues",
            "F_content": "Likely Content Availability & Catalog Accuracy",
            "G_feature": "Likely Feature Request & Product Feedback",
            "H_complaint": "Likely General Complaint / Service Dissatisfaction",
            "I_market": "Likely Country/Market Availability Inquiry",
            "J_ambiguous_multi_intent": "Two or more loose signals fired -- ambiguous between multiple canonical intents",
            "K_non_english": "Non-English / insufficiently interpretable, no signal",
            "L_bare_or_metadata": "Bare follow-up, greeting/ack, or metadata-like content (email, order id, etc.) with no independent intent",
            "M_other_unsuitable": "Reserved -- not populated by this heuristic; no additional 'unsuitable pair' cases were distinguishable from A/L in this pass",
        },
        "category_counts": dict(category_counts),
        "category_percentages": {k: round(v / n_sample, 4) for k, v in category_counts.items()},
        "response_type_distribution_by_category": {
            k: dict(v) for k, v in response_type_by_category.items()
        },
        "message_length_words": {
            "mean": round(sum(length_stats) / len(length_stats), 2),
            "min": min(length_stats),
            "max": max(length_stats),
        },
        "representative_examples_by_category": examples_by_category,
    }

    OUTPUT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"OTHER/UNKNOWN bucket total: {n_other_total}")
    print(f"Sample size: {n_sample} (seed={SEED})")
    print()
    print("Category distribution:")
    for cat, count in category_counts.most_common():
        print(f"  {cat}: {count} ({count / n_sample:.1%})")
    print()
    print(f"Wrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
