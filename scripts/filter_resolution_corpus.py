"""
Phase 7C production entry point: quality-filter the Phase 7B resolution
candidates into the canonical historical evidence corpus.

Usage:
    .venv/Scripts/python.exe scripts/filter_resolution_corpus.py

Reads (read-only): data/processed/twitter/spotifycares_conversations.parquet
                    data/processed/twitter/spotifycares_resolution_candidates.parquet
                    data/golden/golden_set_annotations.jsonl
                    data/golden/golden_set_candidates.jsonl
Writes:             data/processed/twitter/spotifycares_resolution_corpus.parquet
                    data/processed/twitter/spotifycares_corpus_quality.json
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from data.corpus_filtering import run_full_filtering  # noqa: E402

RECON_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_conversations.parquet"
CAND_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_candidates.parquet"
GOLDEN_ANN_PATH = REPO_ROOT / "data" / "golden" / "golden_set_annotations.jsonl"
GOLDEN_CAND_PATH = REPO_ROOT / "data" / "golden" / "golden_set_candidates.jsonl"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_corpus.parquet"
QUALITY_REPORT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_corpus_quality.json"


def main() -> None:
    for p in (RECON_PATH, CAND_PATH, GOLDEN_ANN_PATH, GOLDEN_CAND_PATH):
        if not p.exists():
            raise SystemExit(f"Required input not found: {p}")

    before_mtimes = {p: p.stat().st_mtime for p in (RECON_PATH, CAND_PATH, GOLDEN_ANN_PATH, GOLDEN_CAND_PATH)}

    print("Reading (read-only) Phase 7A/7B outputs and golden set...")
    t0 = time.time()
    report = run_full_filtering(
        candidates_path=CAND_PATH,
        reconstruction_path=RECON_PATH,
        golden_annotations_path=GOLDEN_ANN_PATH,
        golden_candidates_path=GOLDEN_CAND_PATH,
        output_path=OUTPUT_PATH,
        quality_report_path=QUALITY_REPORT_PATH,
    )
    elapsed = time.time() - t0

    for p, before in before_mtimes.items():
        assert p.stat().st_mtime == before, f"{p} must not be modified!"

    print(f"Done in {elapsed:.1f}s")
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"Wrote: {QUALITY_REPORT_PATH}")
    print()
    print(f"Input candidates:  {report.input_candidate_count}")
    print(f"Output corpus:     {report.output_corpus_count}")
    print(f"Retention:         {report.output_corpus_count / report.input_candidate_count:.1%}")
    print()
    print("Exclusion reason counts:")
    for reason, count in report.exclusion_reason_counts.items():
        print(f"  {reason}: {count}")
    print()
    print("Broadcast investigation:", report.broadcast_investigation)
    print()
    print("Golden-set leakage:", report.golden_set_leakage)


if __name__ == "__main__":
    main()
