"""
Phase 9: the first complete SpotifyCares support-agent pipeline.

customer message -> intent (Phase 7D) -> retrieval (Phase 8) ->
evidence assessment -> generation -> escalation policy -> structured result.

This module only orchestrates; each step's actual logic lives in its
own module (src/intent/, src/retrieval/, src/evidence.py,
src/generation/, src/escalation/) so components stay independently
testable and swappable, per CLAUDE.md's "simple, modular" principle.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from escalation.policy import decide_escalation
from evidence import assess_evidence
from generation.generator import FALLBACK_REPLY, Generator
from generation.llm_client import get_llm_client
from intent.deterministic_classifier import OTHER, classify_candidate
from retrieval.retriever import Retriever

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_INDEX_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares.index"
DEFAULT_METADATA_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_metadata.parquet"
DEFAULT_VECTORS_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_vectors.npy"

DEFAULT_TOP_K = 5


@dataclass
class AgentResult:
    customer_message: str
    intent: str
    intent_confidence: str
    secondary_issue: str | None
    retrieved_cases: list[dict]
    evidence_sufficient: bool
    reply: str
    escalate: bool
    escalation_reason: str
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _retrieved_case_to_public_dict(rank: int, case: dict) -> dict:
    """Public/output shape (Step 9's output contract) -- deliberately
    smaller than the retriever's internal result dict (drops
    customer_tweet_id/context_root_message, which are provenance
    details useful for the trace but not part of the stable contract)."""
    return {
        "rank": rank,
        "similarity": round(case["similarity_score"], 4),
        "conversation_id": case["conversation_id"],
        "resolution_id": case["retrieval_id"],
        "customer_message": case["customer_message"],
        "historical_response": case["historical_brand_response"],
        "intent": case["primary_intent"],
    }


class SupportAgent:
    def __init__(self, retriever: Retriever | None = None, generator: Generator | None = None):
        """Both dependencies are injectable so tests never need the
        real 41k-row index or a live LLM. If omitted, the real Phase 8
        index is used, and the LLM client is chosen by
        generation.llm_client.get_llm_client() based on the
        LLM_PROVIDER environment variable ('ollama' by default, or
        'groq')."""
        self.retriever = retriever if retriever is not None else Retriever(
            DEFAULT_INDEX_PATH, DEFAULT_METADATA_PATH, DEFAULT_VECTORS_PATH,
        )
        self.generator = generator if generator is not None else Generator(get_llm_client())

    def handle(self, customer_message: str, context_messages_json: str | None = None,
               k: int = DEFAULT_TOP_K, use_intent_filter: bool = False) -> AgentResult:
        classification = classify_candidate(customer_message, context_messages_json)

        # Step 2: global retrieval by default. Intent filtering is an
        # explicit opt-in, never automatic, and only applies for a
        # non-OTHER intent (see src/retrieval/retriever.py's own
        # OTHER-fallback for the same principle at the retriever level).
        retrieval_intent = classification.primary_intent if (use_intent_filter and classification.primary_intent != OTHER) else None
        raw_results = self.retriever.search(customer_message, k=k, intent=retrieval_intent)

        evidence_input = [
            {
                "similarity": r["similarity_score"],
                "intent": r["primary_intent"],
                "response_type": r["response_type"],
            }
            for r in raw_results
        ]
        evidence = assess_evidence(customer_message, evidence_input)

        generation_cases = [
            {
                "customer_message": r["customer_message"],
                "historical_response": r["historical_brand_response"],
                "similarity": r["similarity_score"],
            }
            for r in raw_results
        ]
        generation = self.generator.generate(
            customer_message, classification.primary_intent, generation_cases, evidence.sufficient,
        )

        public_cases = [_retrieved_case_to_public_dict(i + 1, r) for i, r in enumerate(raw_results)]

        decision = decide_escalation(
            intent=classification.primary_intent,
            intent_confidence=classification.labeling_confidence,
            evidence=evidence,
            customer_message=customer_message,
            reply_text=generation.reply,
            retrieved_cases=public_cases,
        )

        reply = generation.reply
        if decision.reason == "UNSUPPORTED_ACTION":
            # Never let a claim we flagged as unsupported reach the customer,
            # even though we already decided to escalate because of it.
            reply = FALLBACK_REPLY

        return AgentResult(
            customer_message=customer_message,
            intent=classification.primary_intent,
            intent_confidence=classification.labeling_confidence,
            secondary_issue=classification.secondary_issue,
            retrieved_cases=public_cases,
            evidence_sufficient=evidence.sufficient,
            reply=reply,
            escalate=decision.escalate,
            escalation_reason=decision.reason,
            trace={
                "intent_reason": classification.labeling_reason,
                "intent_labeling_method": classification.labeling_method,
                "ambiguous": classification.ambiguous,
                "non_english": classification.non_english,
                "retrieval_mode": "intent_filtered" if retrieval_intent else "global",
                "evidence_reasons": evidence.reasons,
                "evidence_top_similarity": evidence.top_similarity,
                "evidence_distinct_intents": evidence.distinct_intents,
                "evidence_weak_response_fraction": round(evidence.weak_response_fraction, 4),
                "generation_status": generation.generation_status,
                "generation_reason": generation.generation_reason,
            },
        )
