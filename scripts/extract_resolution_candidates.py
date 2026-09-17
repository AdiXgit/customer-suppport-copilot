"""
Phase 7B production entry point: extract resolution candidates from the
Phase 7A reconstructed SpotifyCares conversations.

Usage:
    .venv/Scripts/python.exe scripts/extract_resolution_candidates.py

Reads (read-only):  data/processed/twitter/spotifycares_conversations.parquet
Writes:              data/processed/twitter/spotifycares_resolution_candidates.parquet
                      data/processed/twitter/spotifycares_resolution_quality.json
                      data/processed/twitter/spotifycares_resolution_exclusions.json
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from data.resolution_extraction import run_full_extraction  # noqa: E402

INPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_conversations.parquet"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_candidates.parquet"
QUALITY_REPORT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_quality.json"
EXCLUSION_REPORT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_resolution_exclusions.json"


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"Phase 7A output not found at {INPUT_PATH} -- run scripts/reconstruct_spotifycares.py first")

    before_mtime = INPUT_PATH.stat().st_mtime

    print(f"Reading (read-only): {INPUT_PATH}")
    t0 = time.time()
    quality_report, exclusion_report = run_full_extraction(
        input_path=INPUT_PATH,
        output_path=OUTPUT_PATH,
        quality_report_path=QUALITY_REPORT_PATH,
        exclusion_report_path=EXCLUSION_REPORT_PATH,
    )
    elapsed = time.time() - t0

    assert INPUT_PATH.stat().st_mtime == before_mtime, "Phase 7A input must not be modified!"

    print(f"Done in {elapsed:.1f}s")
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"Wrote: {QUALITY_REPORT_PATH}")
    print(f"Wrote: {EXCLUSION_REPORT_PATH}")
    print()
    print("Quality report:")
    for k, v in quality_report.to_dict().items():
        print(f"  {k}: {v}")
    print()
    print("Exclusion report summary:")
    for entry in exclusion_report.entries:
        print(f"  {entry.exclusion_reason} | conv={entry.conversation_id} author={entry.author_id} "
              f"messages={entry.affected_message_count} candidates={entry.affected_candidate_count}")


if __name__ == "__main__":
    main()
