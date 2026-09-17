"""
Phase 9, Step 13: minimal CLI demo for the SpotifyCares support agent.

Usage:
    .venv/Scripts/python.exe scripts/run_agent.py --message "I was charged twice for Premium"
    .venv/Scripts/python.exe scripts/run_agent.py --message "..." --intent-filter --k 3 --json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agent import SupportAgent  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SpotifyCares support agent on one message.")
    parser.add_argument("--message", required=True, help="Customer message text")
    parser.add_argument("--k", type=int, default=5, help="Number of historical cases to retrieve")
    parser.add_argument("--intent-filter", action="store_true", help="Opt in to intent-filtered retrieval")
    parser.add_argument("--json", action="store_true", help="Print the full JSON result instead of the readable view")
    args = parser.parse_args()

    agent = SupportAgent()
    result = agent.handle(args.message, k=args.k, use_intent_filter=args.intent_filter)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return

    print(f"Intent:\n{result.intent} (confidence: {result.intent_confidence})")
    if result.secondary_issue:
        print(f"Secondary issue: {result.secondary_issue}")
    print()
    print("Retrieved evidence:")
    if result.retrieved_cases:
        for c in result.retrieved_cases:
            print(f"{c['rank']}. [{c['similarity']:.3f}] ({c['intent']}) {c['customer_message']!r}")
            print(f"   -> {c['historical_response']!r}")
    else:
        print("(none)")
    print()
    print(f"Evidence sufficient: {result.evidence_sufficient}")
    print()
    print(f"Reply:\n{result.reply}")
    print()
    print(f"Escalate: {result.escalate}")
    print(f"Reason: {result.escalation_reason}")


if __name__ == "__main__":
    main()
