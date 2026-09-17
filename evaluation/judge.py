"""
Phase 10, Steps 7-8: LLM-as-judge for generated replies.

The judge sees ONLY the customer message, the retrieved historical
evidence, and the generated reply -- never the gold intent, gold
annotation, or annotator notes (Step 7's explicit "should NOT see"
list), and never a golden example used as a few-shot prompt.
"""

from __future__ import annotations

import json
import re

from generation.llm_client import LLMClient, LLMUnavailableError

JUDGE_PROMPT_VERSION = "v1"

JUDGE_SYSTEM_PROMPT = """You are evaluating a customer-support response for quality and safety.

Judge ONLY what is supported by the supplied customer message and historical evidence below.
Do not reward a response merely for sounding professional or fluent.
A response is grounded only when its substantive claims are supported by the historical evidence or directly follow from the customer message.
Penalize invented policies, timelines, refunds, account actions, capabilities, or procedures, and any claim that an action was performed.
If the historical evidence was insufficient, a cautious escalation or brief acknowledgement may be a BETTER response than a confident invented solution -- do not penalize appropriate caution.

CUSTOMER MESSAGE:
{customer_message}

HISTORICAL EVIDENCE (how similar past cases were handled):
{evidence_block}

GENERATED REPLY:
{reply}

Score each dimension from 1 (very poor) to 5 (excellent):
1. correctness -- is the reply factually consistent with the evidence and message?
2. groundedness -- are its substantive claims actually supported by the historical evidence, not invented?
3. helpfulness -- does it move the customer's problem forward?
4. actionability -- is there a concrete, appropriate next step (or an appropriate acknowledgement/escalation if evidence is weak)?
5. brand_consistency -- does it sound like a real SpotifyCares support reply?

Also determine:
6. hallucination -- true if the reply invents a policy, timeline, refund, capability, or claims an action was performed that is not supported by the evidence; false otherwise.
7. overall_evidence_supported -- true if the reply's core claims are backed by the historical evidence or the message itself; false if it is a plausible-sounding but unsupported answer.

Respond with ONLY a JSON object of this exact shape, no other text:
{{"correctness": <1-5>, "groundedness": <1-5>, "helpfulness": <1-5>, "actionability": <1-5>, "brand_consistency": <1-5>, "hallucination": true|false, "overall_evidence_supported": true|false, "reasons": {{"correctness": "<short reason>", "groundedness": "<short reason>", "helpfulness": "<short reason>", "actionability": "<short reason>", "brand_consistency": "<short reason>", "hallucination": "<short reason>"}}}}
"""

_SCORE_FIELDS = ["correctness", "groundedness", "helpfulness", "actionability", "brand_consistency"]


def build_judge_prompt(customer_message: str, retrieved_cases: list[dict], reply: str) -> str:
    if retrieved_cases:
        evidence_block = "\n".join(
            f"{i}. Customer: {c.get('customer_message', '')}\n   SpotifyCares: {c.get('historical_response', '')}\n   Similarity: {c.get('similarity', 0):.2f}"
            for i, c in enumerate(retrieved_cases, start=1)
        )
    else:
        evidence_block = "(none retrieved)"
    return JUDGE_SYSTEM_PROMPT.format(customer_message=customer_message, evidence_block=evidence_block, reply=reply)


def parse_judge_response(raw_text: str) -> dict | None:
    """Robust parsing mirroring generation/prompts.py's approach.
    Returns None if the response can't be recovered into a valid
    judge verdict (all 5 scores in range, hallucination present)."""
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
        if not isinstance(parsed, dict):
            continue
        if not all(f in parsed for f in _SCORE_FIELDS) or "hallucination" not in parsed:
            continue
        try:
            scores = {f: int(parsed[f]) for f in _SCORE_FIELDS}
        except (TypeError, ValueError):
            continue
        if not all(1 <= v <= 5 for v in scores.values()):
            continue
        result = dict(scores)
        result["hallucination"] = bool(parsed["hallucination"])
        result["overall_evidence_supported"] = bool(parsed.get("overall_evidence_supported", not result["hallucination"]))
        result["reasons"] = parsed.get("reasons", {}) if isinstance(parsed.get("reasons"), dict) else {}
        return result
    return None


def run_judge(llm_client: LLMClient, customer_message: str, retrieved_cases: list[dict], reply: str) -> dict:
    prompt = build_judge_prompt(customer_message, retrieved_cases, reply)
    try:
        response = llm_client.generate(prompt)
    except LLMUnavailableError as e:
        return {"status": "llm_unavailable", "error": str(e), "verdict": None}

    parsed = parse_judge_response(response.text)
    if parsed is None:
        return {"status": "unparseable_output", "raw_output": response.text[:500], "verdict": None}

    return {"status": "success", "verdict": parsed}
