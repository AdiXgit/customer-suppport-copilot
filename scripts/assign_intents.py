"""
Phase 7D production entry point: assign deterministic intent labels to
the Phase 7C historical resolution corpus.

Usage:
    .venv/Scripts/python.exe scripts/assign_intents.py

Reads (read-only): data/processed/twitter/spotifycares_resolution_corpus.parquet
Writes:             data/processed/twitter/spotifycares_intent_corpus.parquet
                     data/processed/twitter/spotifycares_intent_quality.json

Does NOT touch data/golden/ in any way. No LLM, no embeddings.
"""

import sys
import time
from collections import Counter
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from intent.deterministic_classifier import (  # noqa: E402
    CANONICAL_INTENTS,
    OTHER,
    PRIORITY_ORDER,
    classify_candidate,
)

CORPUS_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_corpus.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_corpus.parquet"
QUALITY_REPORT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_quality.json"


def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(f"Phase 7C corpus not found at {CORPUS_PATH}")

    before_mtime = CORPUS_PATH.stat().st_mtime

    print(f"Reading (read-only): {CORPUS_PATH}")
    t0 = time.time()
    df = pl.read_parquet(CORPUS_PATH)

    primary_intents = []
    secondary_issues = []
    labeling_methods = []
    labeling_reasons = []
    labeling_confidences = []
    ambiguous_flags = []
    non_english_flags = []

    for row in df.iter_rows(named=True):
        r = classify_candidate(row["customer_message"], row["context_messages_json"])
        primary_intents.append(r.primary_intent)
        secondary_issues.append(r.secondary_issue)
        labeling_methods.append(r.labeling_method)
        labeling_reasons.append(r.labeling_reason)
        labeling_confidences.append(r.labeling_confidence)
        ambiguous_flags.append(r.ambiguous)
        non_english_flags.append(r.non_english)

    out = df.with_columns([
        pl.Series("primary_intent", primary_intents),
        pl.Series("secondary_issue", secondary_issues),
        pl.Series("labeling_method", labeling_methods),
        pl.Series("labeling_reason", labeling_reasons),
        pl.Series("labeling_confidence", labeling_confidences),
        pl.Series("ambiguous", ambiguous_flags),
        pl.Series("non_english", non_english_flags),
    ])

    elapsed = time.time() - t0

    assert CORPUS_PATH.stat().st_mtime == before_mtime, "Phase 7C corpus must not be modified!"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.write_parquet(OUTPUT_PATH)

    n_total = out.height
    n_other = int((out.get_column("primary_intent") == OTHER).sum())
    n_ambiguous = int(out.get_column("ambiguous").sum())
    n_non_english = int(out.get_column("non_english").sum())

    intent_counts = Counter(primary_intents)
    method_counts = Counter(labeling_methods)
    reason_counts = Counter(labeling_reasons)

    quality_report = {
        "total_examples": n_total,
        "labeled_count": n_total - n_other,
        "other_unknown_count": n_other,
        "ambiguous_count": n_ambiguous,
        "non_english_count": n_non_english,
        "per_intent_counts": dict(intent_counts),
        "per_intent_percentages": {k: round(v / n_total, 4) for k, v in intent_counts.items()},
        "labeling_method_distribution": dict(method_counts),
        "reason_code_distribution": dict(reason_counts),
        "deterministic_coverage": round((n_total - n_other) / n_total, 4),
        "model_assisted_coverage": 0,
        "model_assisted_used": False,
        "model_assisted_attempt": {
            "attempted": True,
            "tool": "Ollama (local), model gemma2:9b-instruct-q4_0",
            "outcome": "FAILED -- local Ollama runtime crashed reproducibly "
                       "('Error: 500 Internal Server Error: llama runner process "
                       "has terminated') on two separate invocations, including "
                       "a minimal single-word prompt with no classification task "
                       "involved. This is an infrastructure/runtime failure, not "
                       "a taxonomy-following or prompting issue.",
            "decision": "Did not proceed with model-assisted labeling this phase. "
                        "Per instructions, a hosted-model fallback requires "
                        "explicit approval and was not attempted. The corpus is "
                        "labeled using the deterministic classifier only; the "
                        "68.5% OTHER/UNKNOWN bucket remains unlabeled pending a "
                        "decision on fixing the local Ollama runtime or "
                        "approving a hosted alternative (see docs/TODO.md).",
        },
        "examples_requiring_review": {
            "ambiguous_examples_sample": (
                out.filter(pl.col("ambiguous")).head(10).select(
                    "resolution_id", "primary_intent", "secondary_issue"
                ).to_dicts()
            ),
        },
        "known_limitations": [
            "Deterministic coverage is intentionally low (~31%) by design: "
            "rules require explicit, high-precision textual evidence "
            "(named entities, specific keywords, technical identifiers) "
            "rather than being tuned to maximize coverage, per this "
            "phase's explicit instruction not to optimize for coverage.",
            "The non_english flag reuses the Phase 1/5 ASCII-ratio "
            "heuristic, which reliably catches non-Latin scripts but "
            "under-counts mostly-Latin European-language text (a "
            "documented lower bound, not a bug).",
            "The root-context fallback (labeling_method="
            "'deterministic_root_context') assumes a conversation's "
            "root message determines the intent of later follow-up "
            "messages in the same thread; this is a reasonable but "
            "unverified assumption for a minority of rows.",
            "ambiguous=True conflates two distinct real phenomena (a "
            "message with two genuinely separate issues, vs. one issue "
            "that is genuinely hard to classify) -- both are surfaced "
            "identically via the secondary_issue field for human review, "
            "since a rule-based system cannot reliably distinguish them.",
            "This classifier was NOT validated against the golden set "
            "(by design -- see Golden-Set Isolation below) so its true "
            "precision on this specific taxonomy is not independently "
            "measured, only manually spot-checked by the author.",
        ],
    }

    QUALITY_REPORT_PATH.write_text(
        __import__("json").dumps(quality_report, indent=2, default=str), encoding="utf-8"
    )

    print(f"Done in {elapsed:.1f}s")
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"Wrote: {QUALITY_REPORT_PATH}")
    print()
    print(f"Total: {n_total}  Labeled: {n_total - n_other}  OTHER/UNKNOWN: {n_other}  "
          f"Coverage: {(n_total - n_other) / n_total:.1%}")
    print()
    print("Per-intent counts:")
    for intent in PRIORITY_ORDER + [OTHER]:
        print(f"  {intent}: {intent_counts.get(intent, 0)}")


if __name__ == "__main__":
    main()
