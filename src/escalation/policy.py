"""
Phase 9, Steps 7-8: transparent, deterministic escalation policy.

Escalation is decided by this module alone -- never by asking the LLM
whether it thinks the case should escalate (Step 7: "Escalation must
NOT be purely an LLM opinion"). The one place LLM-generated text is
consulted at all is the UNSUPPORTED_ACTION safety-net check, which
scans the final reply text for language claiming an action the system
cannot actually perform (refunds, account changes, "I've contacted the
team", etc.) -- a content check, not an opinion.

Checks run in a fixed priority order and the FIRST matching reason
wins (mirrors the same "deterministic priority order" pattern already
used by src/intent/deterministic_classifier.py):

  1. EXPLICIT_HUMAN_REQUEST -- customer directly asked for a human
  2. SECURITY_RISK          -- Account Security intent without a
                               clearly-supported safe historical pattern
  3. UNSUPPORTED_ACTION     -- the reply text itself claims an action
                               the system cannot perform
  4. CONFLICTING_EVIDENCE   -- retrieved cases span too many intents
  5. INSUFFICIENT_EVIDENCE  -- evidence assessment found it insufficient
                               (for any other reason: low similarity,
                               mostly weak response types, no results,
                               or a bare/low-information query)
  6. LOW_CONFIDENCE         -- deterministic classifier's own confidence
                               was "low" (even though intent may be non-OTHER)
  7. NONE                   -- no escalation trigger fired

Per instructions: OTHER/UNKNOWN intent alone does NOT trigger
escalation, and low similarity alone does NOT trigger escalation --
both only matter through the evidence assessment above.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from evidence import (  # noqa: E402
    EvidenceAssessment,
    REASON_CONFLICTING_INTENTS,
)

ACCOUNT_SECURITY_INTENT = "Account Security"

REASON_SECURITY_RISK = "SECURITY_RISK"
REASON_EXPLICIT_HUMAN_REQUEST = "EXPLICIT_HUMAN_REQUEST"
REASON_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
REASON_UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
REASON_CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_NONE = "NONE"

_HUMAN_REQUEST_RE = re.compile(
    r"\b(speak (to|with) a (real )?(human|person|agent)|"
    r"talk to a (real )?(human|person|agent)|"
    r"human (agent|support|representative)|"
    r"real (person|human)|"
    r"customer service rep(resentative)?|"
    r"connect me (to|with) (a )?(human|person|agent)|"
    r"let me talk to (someone|a person))\b",
    re.IGNORECASE,
)

# Safety-net only: language in the REPLY TEXT claiming a performed
# action the system cannot actually take. Not a general profanity/
# quality filter.
_UNSUPPORTED_ACTION_RE = re.compile(
    r"\b(I(’|')?ve|I have) (issued|processed|refunded|cancelled|canceled|upgraded|"
    r"secured|verified|reset your|changed your|removed the|contacted)\b|"
    r"your (refund|account) (has been|is now) (issued|processed|secured|safe|fixed)|"
    r"we(’|')?ve (contacted|escalated to|notified) (the|our) (team|engineers|specialists)\b",
    re.IGNORECASE,
)


@dataclass
class EscalationDecision:
    escalate: bool
    reason: str


def _mentions_explicit_human_request(customer_message: str) -> bool:
    return bool(_HUMAN_REQUEST_RE.search(customer_message or ""))


def _reply_claims_unsupported_action(reply_text: str) -> bool:
    return bool(_UNSUPPORTED_ACTION_RE.search(reply_text or ""))


def _has_strong_security_evidence(retrieved_cases: list[dict], evidence: EvidenceAssessment) -> bool:
    """Step 8: security cases should escalate UNLESS the retrieved
    evidence provides a "clearly supported safe handling pattern".
    Deliberately strict -- top result must itself be Account Security,
    a substantive (non-DM-redirect, non-acknowledgement) response, high
    similarity, and the overall evidence assessment must be sufficient."""
    if not evidence.sufficient or not retrieved_cases:
        return False
    top = retrieved_cases[0]
    return (
        top.get("intent") == ACCOUNT_SECURITY_INTENT
        and top.get("response_type") == "substantive_response"
        and top.get("similarity", 0) >= 0.75
    )


def decide_escalation(
    intent: str,
    intent_confidence: str,
    evidence: EvidenceAssessment,
    customer_message: str,
    reply_text: str,
    retrieved_cases: list[dict],
) -> EscalationDecision:
    if _mentions_explicit_human_request(customer_message):
        return EscalationDecision(True, REASON_EXPLICIT_HUMAN_REQUEST)

    if intent == ACCOUNT_SECURITY_INTENT and not _has_strong_security_evidence(retrieved_cases, evidence):
        return EscalationDecision(True, REASON_SECURITY_RISK)

    if _reply_claims_unsupported_action(reply_text):
        return EscalationDecision(True, REASON_UNSUPPORTED_ACTION)

    if REASON_CONFLICTING_INTENTS in evidence.reasons:
        return EscalationDecision(True, REASON_CONFLICTING_EVIDENCE)

    if not evidence.sufficient:
        return EscalationDecision(True, REASON_INSUFFICIENT_EVIDENCE)

    if intent_confidence == "low":
        return EscalationDecision(True, REASON_LOW_CONFIDENCE)

    return EscalationDecision(False, REASON_NONE)
