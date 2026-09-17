"""
Phase 9, Step 5: the strict grounding prompt.

The model is given the customer's message, the deterministic intent,
and up to a handful of historical SpotifyCares cases retrieved by
Phase 8 -- nothing else. It is instructed to treat those historical
responses as evidence of past behavior, not current policy, and is
explicitly told not to invent anything the historical evidence doesn't
support.
"""

from __future__ import annotations

import json

SYSTEM_INSTRUCTIONS = """You are drafting a reply on behalf of SpotifyCares customer support.

Instructions:
- Answer the customer's issue using the historical evidence below.
- Treat historical responses as evidence of how SpotifyCares handled similar cases in the past, not as universal policy or a guarantee of the same outcome now.
- Do not invent refunds, timelines, eligibility rules, product capabilities, or actions.
- Do not claim an action was performed when you cannot perform it (you cannot access accounts, issue refunds, change subscriptions, or contact other teams).
- Do not fabricate links or support procedures that are not present in the historical evidence.
- If the evidence is insufficient to answer confidently, say so internally (set evidence_sufficient to false) and keep the reply to a brief, safe acknowledgement rather than a confident solution.
- Keep the reply concise and support-oriented.
- Do not mention the retrieval system, embeddings, similarity scores, or the internal intent classifier.
- Do not copy a historical response verbatim -- adapt it to the customer's specific message.
- If the historical cases conflict with each other, preserve that uncertainty rather than picking one arbitrarily.

Respond with ONLY a JSON object of this exact shape, no other text:
{"reply": "<the customer-facing reply text>", "evidence_sufficient": true|false, "generation_reason": "<one short phrase explaining your evidence_sufficient judgment>"}
"""


def build_prompt(customer_message: str, intent: str, retrieved_cases: list[dict]) -> str:
    """retrieved_cases: list of dicts with at least 'customer_message',
    'historical_response' (or 'historical_brand_response'), and
    'similarity' keys -- as produced by src/agent.py's evidence list,
    already stripped of anything not meant for the model (no raw
    resolution_id/conversation_id needed by the LLM itself)."""
    lines = [SYSTEM_INSTRUCTIONS, "", f"CUSTOMER MESSAGE:\n{customer_message}", "", f"INTENT:\n{intent}", ""]

    if retrieved_cases:
        lines.append("HISTORICAL SUPPORT CASES:")
        for i, case in enumerate(retrieved_cases, start=1):
            historical_response = case.get("historical_response") or case.get("historical_brand_response") or ""
            lines.append(f"{i}. Customer: {case.get('customer_message', '')}")
            lines.append(f"   SpotifyCares: {historical_response}")
            lines.append(f"   Similarity: {case.get('similarity', 0):.2f}")
    else:
        lines.append("HISTORICAL SUPPORT CASES:\n(none retrieved)")

    lines.append("")
    lines.append("JSON response:")
    return "\n".join(lines)


def parse_structured_response(raw_text: str) -> dict | None:
    """Robust parsing (Step 5's 'if structured generation is unreliable,
    implement robust parsing/fallback behavior'). Tries a direct
    json.loads first, then falls back to extracting the first {...}
    block from the text. Returns None if no usable JSON object with a
    'reply' key can be recovered."""
    if not raw_text or not raw_text.strip():
        return None

    candidates = [raw_text.strip()]
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(raw_text[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict) and "reply" in parsed and isinstance(parsed["reply"], str):
            return {
                "reply": parsed["reply"],
                "evidence_sufficient": bool(parsed.get("evidence_sufficient", True)),
                "generation_reason": parsed.get("generation_reason", ""),
            }
    return None
