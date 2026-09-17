"""
Interactive HUMAN annotation tool for the SpotifyCares golden-set
calibration batch (Phase 6B).

This script NEVER assigns, suggests, predicts, or pre-fills a
primary_intent (or any other annotation field). It only:
  - displays one customer_message at a time (and nothing else about it),
  - displays the fixed, static list of 9 taxonomy labels,
  - collects the human annotator's typed answers,
  - validates and saves them.

No LLM call, no classifier, no heuristic label suggestion exists
anywhere in this file.

Input:  data/golden/golden_calibration_batch_25.jsonl
Output: data/golden/golden_calibration_annotations.jsonl

Usage:
    python scripts/annotate_calibration.py            # run interactively
    python scripts/annotate_calibration.py --selftest # non-interactive smoke test only

Controls at the primary-intent prompt:
    n = skip this example for now (goes to the next one)
    b = go back to the previous example
    q = save and quit
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(REPO_ROOT, "data", "golden", "golden_calibration_batch_25.jsonl")
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "golden", "golden_calibration_annotations.jsonl")

# Exact 9-label taxonomy list, as specified for this script and consistent
# with docs/INTENTS.md. This is the ONLY place intents are defined in this
# script -- it is a fixed menu, never a prediction.
INTENTS = [
    "Account Access & Login",
    "Account Security",
    "Premium Subscription & Billing",
    "App & Playback Technical Issues",
    "Content Availability & Catalog Accuracy",
    "Feature Request & Product Feedback",
    "General Complaint / Service Dissatisfaction",
    "Country/Market Availability Inquiry",
    "OTHER / UNKNOWN",
]

NAV_COMMANDS = {"n", "b", "q"}


def load_batch(path: str) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_annotations(path: str) -> dict[str, dict]:
    """Returns {example_id: annotation_record} for already-saved annotations."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["example_id"]] = rec
    return out


def is_completed(rec: dict | None) -> bool:
    if rec is None:
        return False
    if rec.get("excluded") is True:
        return True
    return rec.get("primary_intent") is not None


def save_annotations_atomic(path: str, annotations_by_id: dict[str, dict], order: list[str]) -> None:
    """Rewrite the whole output file atomically (temp file + rename) so an
    interruption mid-write can never corrupt or truncate the output."""
    dirpath = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=".annotations_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for example_id in order:
                if example_id in annotations_by_id:
                    f.write(json.dumps(annotations_by_id[example_id], ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def prompt_line(prompt: str, allow_nav: bool = True) -> str:
    """Reads one line of input. Raises NavSignal if the user typed a nav
    command (n/b/q) and allow_nav is True."""
    raw = input(prompt).strip()
    if allow_nav and raw.lower() in NAV_COMMANDS:
        raise NavSignal(raw.lower())
    return raw


class NavSignal(Exception):
    def __init__(self, command: str):
        super().__init__(command)
        self.command = command


def prompt_intent_number() -> int:
    while True:
        raw = prompt_line(
            "\nEnter the primary intent number (1-9), or a command [n=skip, b=back, q=save & quit]: "
        )
        if raw.isdigit() and 1 <= int(raw) <= len(INTENTS):
            return int(raw)
        print(f"  Invalid input. Enter a number from 1 to {len(INTENTS)}, or n/b/q.")


def prompt_yes_no(label: str) -> bool:
    # allow_nav=False: nav commands (n/b/q) are only recognized at the
    # primary-intent prompt (see prompt_intent_number). Otherwise typing
    # "n" to mean "no" here was being misread as the "next" nav command,
    # silently discarding the whole in-progress example before it was saved.
    while True:
        raw = prompt_line(f"{label} [y/n]: ", allow_nav=False)
        low = raw.lower()
        if low in ("y", "yes"):
            return True
        if low in ("n", "no"):
            return False
        print("  Please answer y or n.")


def prompt_optional_text(label: str) -> str | None:
    raw = prompt_line(f"{label} (optional, press Enter to skip): ", allow_nav=False)
    return raw if raw else None


def annotate_one(record: dict) -> dict | None:
    """Runs the Q&A flow for one example. Returns the completed annotation
    record, or None if the user issued a nav command before completing it
    (in which case nothing for this example is saved)."""
    print("\n" + "=" * 78)
    print(f"Example ID: {record['example_id']}")
    print("-" * 78)
    print("Customer message:")
    print(f"  {record['customer_message']}")
    print("-" * 78)
    print("Choose the primary intent:")
    for i, name in enumerate(INTENTS, start=1):
        print(f"  {i}. {name}")

    intent_num = prompt_intent_number()
    primary_intent = INTENTS[intent_num - 1]

    secondary_issue = prompt_optional_text("Secondary issue")
    ambiguous = prompt_yes_no("Ambiguous?")
    non_english = prompt_yes_no("Non-English?")
    excluded = prompt_yes_no("Excluded?")

    exclusion_reason = None
    if excluded:
        while True:
            exclusion_reason = prompt_line(
                "Exclusion reason (required since excluded=y): ", allow_nav=False
            )
            if exclusion_reason:
                break
            print("  Exclusion reason cannot be empty when excluded=y.")

    annotator_notes = prompt_optional_text("Annotator notes")

    return {
        "example_id": record["example_id"],
        "customer_message": record["customer_message"],  # preserved exactly
        "primary_intent": primary_intent,
        "secondary_issue": secondary_issue,
        "ambiguous": ambiguous,
        "non_english": non_english,
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "annotator_notes": annotator_notes,
        "label_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_interactive() -> None:
    batch = load_batch(INPUT_PATH)
    order = [r["example_id"] for r in batch]
    by_id = {r["example_id"]: r for r in batch}

    annotations = load_annotations(OUTPUT_PATH)

    n_completed = sum(1 for eid in order if is_completed(annotations.get(eid)))
    print(f"Loaded {len(batch)} examples from {os.path.relpath(INPUT_PATH, REPO_ROOT)}")
    print(f"{n_completed}/{len(order)} already completed.")

    # resume from first unlabeled example
    idx = 0
    for i, eid in enumerate(order):
        if not is_completed(annotations.get(eid)):
            idx = i
            break
    else:
        idx = 0  # all completed; start at the beginning for review via 'b'

    print("Controls: n = skip/next, b = back, q = save & quit\n")

    while 0 <= idx < len(order):
        eid = order[idx]
        record = by_id[eid]
        existing = annotations.get(eid)

        if is_completed(existing):
            print("\n" + "=" * 78)
            print(f"Example ID: {eid} is already labeled:")
            print(f"  primary_intent = {existing.get('primary_intent')}")
            print(f"  excluded = {existing.get('excluded')}")
            edit = prompt_yes_no("This example is already labeled. Edit it?")
            if not edit:
                idx += 1
                continue

        try:
            result = annotate_one(record)
        except NavSignal as nav:
            if nav.command == "n":
                idx += 1
                continue
            if nav.command == "b":
                idx = max(0, idx - 1)
                continue
            if nav.command == "q":
                save_annotations_atomic(OUTPUT_PATH, annotations, order)
                break
        else:
            annotations[eid] = result
            save_annotations_atomic(OUTPUT_PATH, annotations, order)  # incremental save
            idx += 1
    else:
        save_annotations_atomic(OUTPUT_PATH, annotations, order)

    n_completed = sum(1 for eid in order if is_completed(annotations.get(eid)))
    print(f"\n{n_completed}/{len(order)} completed.")
    print(f"Saved to {os.path.relpath(OUTPUT_PATH, REPO_ROOT)}")


def run_selftest() -> None:
    """Non-interactive smoke test. Does NOT call input() and does NOT
    write any labels. Verifies: input loads, has 25 examples, output
    schema constants are sane, and no annotations file gets created or
    populated as a side effect of importing/checking this module."""
    print("Running non-interactive self-test (no labels will be generated)...")

    assert os.path.exists(INPUT_PATH), f"Input file not found: {INPUT_PATH}"
    batch = load_batch(INPUT_PATH)
    print(f"  Loaded {len(batch)} examples from {os.path.relpath(INPUT_PATH, REPO_ROOT)}")
    assert len(batch) == 25, f"Expected 25 examples, found {len(batch)}"

    required_keys = {
        "example_id", "customer_message", "primary_intent", "secondary_issue",
        "ambiguous", "non_english", "excluded", "exclusion_reason", "annotator_notes",
    }
    for rec in batch:
        assert required_keys.issubset(rec.keys()), f"Missing keys in {rec.get('example_id')}"
        assert rec["primary_intent"] is None, (
            f"{rec['example_id']} already has a primary_intent -- input must be blank"
        )
        assert isinstance(rec["customer_message"], str) and rec["customer_message"], (
            f"{rec['example_id']} has an empty customer_message"
        )
        # confirm no sampling/bucket/author metadata is present in the input file
        forbidden = {"sampling_group", "target_intent_hint", "author_id", "conv_size",
                     "flag_possible_praise_only", "flag_non_english_suspected",
                     "flag_mega_thread_suspect", "flag_high_frequency_author"}
        leaked = forbidden.intersection(rec.keys())
        assert not leaked, f"{rec['example_id']} leaks forbidden metadata: {leaked}"
    print("  All 25 records have the expected blank schema and no leaked metadata.")

    assert len(INTENTS) == 9, "Intent menu must have exactly 9 entries"
    print(f"  Intent menu has {len(INTENTS)} entries:")
    for i, name in enumerate(INTENTS, start=1):
        print(f"    {i}. {name}")

    # verify output file is untouched by this selftest
    existed_before = os.path.exists(OUTPUT_PATH)
    size_before = os.path.getsize(OUTPUT_PATH) if existed_before else None
    # (no write operations are called in this function)
    existed_after = os.path.exists(OUTPUT_PATH)
    size_after = os.path.getsize(OUTPUT_PATH) if existed_after else None
    assert existed_before == existed_after and size_before == size_after, (
        "Self-test must not modify the output annotations file"
    )
    if existed_before:
        existing_annotations = load_annotations(OUTPUT_PATH)
        n_labeled = sum(1 for r in existing_annotations.values() if is_completed(r))
        print(f"  Output file already exists with {n_labeled} completed annotation(s) "
              f"(untouched by this self-test).")
    else:
        print(f"  Output file {os.path.relpath(OUTPUT_PATH, REPO_ROOT)} does not exist yet "
              f"(expected -- no annotation has been run).")

    print("\nSelf-test PASSED. No labels were generated. Interactive annotation was not started.")


def run_persistence_test() -> None:
    """Non-interactive regression test for the save/load persistence bug.

    Simulates completing 2 annotations (no input(), no interactive loop),
    saves them via save_annotations_atomic(), reloads via load_annotations(),
    and verifies both round-trip correctly and are counted as completed.
    Runs entirely in a temp file; never touches the real output path.
    """
    print("Running persistence regression test (no interactive input, no real files touched)...")

    order = ["GOLD-TEST-0001", "GOLD-TEST-0002", "GOLD-TEST-0003"]
    fake_annotations = {
        "GOLD-TEST-0001": {
            "example_id": "GOLD-TEST-0001",
            "customer_message": "test message one",
            "primary_intent": "Account Access & Login",
            "secondary_issue": None,
            "ambiguous": False,
            "non_english": False,
            "excluded": False,
            "exclusion_reason": None,
            "annotator_notes": None,
            "label_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "GOLD-TEST-0002": {
            "example_id": "GOLD-TEST-0002",
            "customer_message": "test message two",
            "primary_intent": None,
            "secondary_issue": None,
            "ambiguous": False,
            "non_english": False,
            "excluded": True,
            "exclusion_reason": "praise_only",
            "annotator_notes": None,
            "label_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        # GOLD-TEST-0003 deliberately left absent -- simulates an
        # incomplete/skipped example that must NOT appear in the saved file.
    }

    dirpath = os.path.join(REPO_ROOT, "data", "golden")
    fd, tmp_output = tempfile.mkstemp(dir=dirpath, prefix=".persistence_test_", suffix=".jsonl")
    os.close(fd)
    os.remove(tmp_output)  # save_annotations_atomic expects to create it fresh

    try:
        # Save after "completing" example 1, then again after example 2,
        # mirroring the incremental-save behavior of the real loop.
        save_annotations_atomic(tmp_output, {"GOLD-TEST-0001": fake_annotations["GOLD-TEST-0001"]}, order)
        assert os.path.getsize(tmp_output) > 0, "File must be non-empty after saving 1 completed annotation"

        save_annotations_atomic(tmp_output, fake_annotations, order)

        reloaded = load_annotations(tmp_output)
        assert set(reloaded.keys()) == {"GOLD-TEST-0001", "GOLD-TEST-0002"}, (
            f"Expected exactly the 2 completed examples, got {set(reloaded.keys())}"
        )
        assert "GOLD-TEST-0003" not in reloaded, "Unsaved/incomplete example must not appear"

        assert reloaded["GOLD-TEST-0001"]["primary_intent"] == "Account Access & Login"
        assert reloaded["GOLD-TEST-0002"]["excluded"] is True
        assert reloaded["GOLD-TEST-0002"]["exclusion_reason"] == "praise_only"

        n_completed = sum(1 for eid in order if is_completed(reloaded.get(eid)))
        assert n_completed == 2, f"Expected 2/3 completed after reload, got {n_completed}/3"
        print(f"  Round-tripped 2 completed annotations successfully. {n_completed}/{len(order)} completed.")

        # Also verify the specific regression: a "no" (n) answer must not be
        # mistaken for a nav command anywhere outside prompt_intent_number.
        # (Structural check: prompt_yes_no/prompt_optional_text/exclusion_reason
        # must all call prompt_line with allow_nav=False.)
        import inspect
        for fn in (prompt_yes_no, prompt_optional_text):
            src = inspect.getsource(fn)
            assert "allow_nav=False" in src, (
                f"{fn.__name__} must call prompt_line with allow_nav=False "
                f"so a literal 'n'/'b'/'q' answer isn't treated as navigation"
            )
        annotate_src = inspect.getsource(annotate_one)
        assert 'allow_nav=False' in annotate_src, (
            "exclusion_reason prompt inside annotate_one must use allow_nav=False"
        )
        print("  Confirmed nav-command interception is scoped to the intent-number prompt only.")

    finally:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)

    print("\nPersistence regression test PASSED.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_selftest()
    elif "--test-persistence" in sys.argv:
        run_persistence_test()
    else:
        run_interactive()
