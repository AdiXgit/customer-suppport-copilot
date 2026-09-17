"""
Phase 7A production entry point: reconstruct SpotifyCares conversations
from the full raw TWCS dataset and write the processed Parquet + a JSON
data-quality report.

Usage:
    .venv/Scripts/python.exe scripts/reconstruct_spotifycares.py

Reads (read-only):  data/raw/twitter/twcs.csv
Writes:              data/processed/twitter/spotifycares_conversations.parquet
                      data/processed/twitter/spotifycares_quality_report.json
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from data.reconstruction import run_full_reconstruction  # noqa: E402

INPUT_PATH = REPO_ROOT / "data" / "raw" / "twitter" / "twcs.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_conversations.parquet"
QUALITY_REPORT_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_quality_report.json"
BRAND_AUTHORS = {"SpotifyCares"}


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"Raw dataset not found at {INPUT_PATH}")

    print(f"Reading (read-only): {INPUT_PATH}")
    t0 = time.time()
    report = run_full_reconstruction(
        input_path=INPUT_PATH,
        output_path=OUTPUT_PATH,
        quality_report_path=QUALITY_REPORT_PATH,
        brand_authors=BRAND_AUTHORS,
    )
    elapsed = time.time() - t0

    print(f"Done in {elapsed:.1f}s")
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"Wrote: {QUALITY_REPORT_PATH}")
    print()
    print("Quality report:")
    for k, v in report.to_dict().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
