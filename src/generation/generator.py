"""
Phase 9, Steps 4-6 & 10: generation orchestration.

Generator.generate(...) always attempts an LLM call (the prompt itself
tells the model to behave conservatively when evidence is weak -- see
prompts.py) but NEVER trusts the LLM's own evidence_sufficient opinion
for the escalation decision; that is the escalation policy's job
(src/escalation/policy.py), which is independent of generation output
per Step 7 ("Escalation must NOT be purely an LLM opinion").

If the LLM is unavailable or its output can't be recovered into a
reply at all, a fixed, safe, deterministic fallback reply is used
instead -- never a hallucinated "historically grounded" answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .llm_client import LLMClient, LLMUnavailableError
from .prompts import build_prompt, parse_structured_response

FALLBACK_REPLY = (
    "I'm sorry you're having trouble with this. This issue may need "
    "further assistance from Spotify Support."
)

GENERATION_STATUS_SUCCESS = "success"
GENERATION_STATUS_LLM_UNAVAILABLE = "llm_unavailable"
GENERATION_STATUS_GENERATION_ERROR = "generation_error"


@dataclass
class GenerationResult:
    reply: str
    evidence_sufficient: bool
    generation_status: str
    generation_reason: str


class Generator:
    def __init__(self, llm_client: LLMClient | None):
        """llm_client may be None to force deterministic-fallback-only
        operation (used by tests and by callers that explicitly don't
        want to attempt a live LLM call)."""
        self.llm_client = llm_client

    def generate(self, customer_message: str, intent: str, retrieved_cases: list[dict],
                 evidence_sufficient: bool) -> GenerationResult:
        if self.llm_client is None:
            return GenerationResult(
                reply=FALLBACK_REPLY,
                evidence_sufficient=evidence_sufficient,
                generation_status=GENERATION_STATUS_LLM_UNAVAILABLE,
                generation_reason="no_llm_client_configured",
            )

        prompt = build_prompt(customer_message, intent, retrieved_cases)

        try:
            response = self.llm_client.generate(prompt)
        except LLMUnavailableError as e:
            return GenerationResult(
                reply=FALLBACK_REPLY,
                evidence_sufficient=evidence_sufficient,
                generation_status=GENERATION_STATUS_LLM_UNAVAILABLE,
                generation_reason=f"llm_unavailable: {e}",
            )

        parsed = parse_structured_response(response.text)
        if parsed is not None:
            return GenerationResult(
                reply=parsed["reply"].strip() or FALLBACK_REPLY,
                evidence_sufficient=parsed["evidence_sufficient"] and evidence_sufficient,
                generation_status=GENERATION_STATUS_SUCCESS,
                generation_reason=parsed["generation_reason"] or "structured_output_parsed",
            )

        raw_text = (response.text or "").strip()
        if raw_text:
            return GenerationResult(
                reply=raw_text,
                evidence_sufficient=evidence_sufficient,
                generation_status=GENERATION_STATUS_SUCCESS,
                generation_reason="unstructured_output_used_as_reply",
            )

        return GenerationResult(
            reply=FALLBACK_REPLY,
            evidence_sufficient=evidence_sufficient,
            generation_status=GENERATION_STATUS_GENERATION_ERROR,
            generation_reason="llm_returned_empty_response",
        )
