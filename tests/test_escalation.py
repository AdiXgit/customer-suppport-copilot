"""
Unit tests for src/escalation/policy.py. All synthetic fixtures --
never the golden set (golden data may only be used for leakage
checks, per instructions, never escalation-policy tuning).
"""

from escalation.policy import (
    REASON_CONFLICTING_EVIDENCE,
    REASON_EXPLICIT_HUMAN_REQUEST,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_LOW_CONFIDENCE,
    REASON_NONE,
    REASON_SECURITY_RISK,
    REASON_UNSUPPORTED_ACTION,
    decide_escalation,
)
from evidence import EvidenceAssessment

GOOD_EVIDENCE = EvidenceAssessment(sufficient=True, reasons=[], top_similarity=0.8, distinct_intents=1)
BAD_EVIDENCE = EvidenceAssessment(sufficient=False, reasons=["LOW_SIMILARITY"], top_similarity=0.3, distinct_intents=1)
CONFLICTING_EVIDENCE = EvidenceAssessment(sufficient=False, reasons=["CONFLICTING_INTENTS"], top_similarity=0.8, distinct_intents=4)

STRONG_SECURITY_CASE = [{"intent": "Account Security", "response_type": "substantive_response", "similarity": 0.9}]
WEAK_SECURITY_CASE = [{"intent": "Account Security", "response_type": "dm_redirect", "similarity": 0.9}]
BILLING_CASE = [{"intent": "Premium Subscription & Billing", "response_type": "substantive_response", "similarity": 0.8}]


def test_security_intent_without_strong_evidence_escalates():
    decision = decide_escalation(
        intent="Account Security", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="my account was hacked and someone changed my email",
        reply_text="This looks like an account-security issue that needs further assistance.",
        retrieved_cases=WEAK_SECURITY_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_SECURITY_RISK


def test_security_intent_with_strong_evidence_does_not_force_security_escalation():
    decision = decide_escalation(
        intent="Account Security", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="my account was hacked",
        reply_text="We understand this is concerning; here is how similar cases were handled.",
        retrieved_cases=STRONG_SECURITY_CASE,
    )
    assert decision.reason != REASON_SECURITY_RISK
    assert decision.escalate is False
    assert decision.reason == REASON_NONE


def test_explicit_human_request_always_escalates():
    decision = decide_escalation(
        intent="Premium Subscription & Billing", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="I want to speak to a real human, not a bot",
        reply_text="Sure, happy to help with your billing question.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_EXPLICIT_HUMAN_REQUEST


def test_explicit_human_request_overrides_good_evidence():
    decision = decide_escalation(
        intent="OTHER / UNKNOWN", intent_confidence="low", evidence=GOOD_EVIDENCE,
        customer_message="can I talk to a human agent please",
        reply_text="Sure!",
        retrieved_cases=[],
    )
    assert decision.reason == REASON_EXPLICIT_HUMAN_REQUEST


def test_insufficient_evidence_escalates():
    decision = decide_escalation(
        intent="Premium Subscription & Billing", intent_confidence="high", evidence=BAD_EVIDENCE,
        customer_message="I have a weird billing thing going on",
        reply_text="This may need further review.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_INSUFFICIENT_EVIDENCE


def test_unsupported_action_in_reply_escalates():
    decision = decide_escalation(
        intent="Premium Subscription & Billing", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="I was charged twice",
        reply_text="I've issued a refund for the duplicate charge.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_UNSUPPORTED_ACTION


def test_conflicting_evidence_escalates():
    decision = decide_escalation(
        intent="App & Playback Technical Issues", intent_confidence="medium", evidence=CONFLICTING_EVIDENCE,
        customer_message="the app is doing something weird",
        reply_text="We're looking into it.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_CONFLICTING_EVIDENCE


def test_low_confidence_escalates_when_otherwise_clean():
    decision = decide_escalation(
        intent="Feature Request & Product Feedback", intent_confidence="low", evidence=GOOD_EVIDENCE,
        customer_message="please add a feature",
        reply_text="Thanks for the suggestion!",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is True
    assert decision.reason == REASON_LOW_CONFIDENCE


def test_safe_case_does_not_escalate():
    decision = decide_escalation(
        intent="Premium Subscription & Billing", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="I was charged twice for my subscription",
        reply_text="Thanks for flagging this -- similar cases were resolved as a billing correction.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is False
    assert decision.reason == REASON_NONE


def test_other_intent_alone_does_not_force_escalation():
    decision = decide_escalation(
        intent="OTHER / UNKNOWN", intent_confidence="high", evidence=GOOD_EVIDENCE,
        customer_message="thanks for the info",
        reply_text="You're welcome!",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is False
    assert decision.reason == REASON_NONE


def test_low_similarity_alone_does_not_force_escalation_without_evidence_flagging_it():
    # An EvidenceAssessment that IS sufficient (e.g. similarity passed the
    # floor and other checks passed) should not escalate just because a
    # human might subjectively call 0.5 "low" -- only the evidence
    # module's own documented thresholds matter here.
    borderline_evidence = EvidenceAssessment(sufficient=True, reasons=[], top_similarity=0.5, distinct_intents=1)
    decision = decide_escalation(
        intent="Premium Subscription & Billing", intent_confidence="high", evidence=borderline_evidence,
        customer_message="I was charged twice for my subscription",
        reply_text="Thanks for flagging this.",
        retrieved_cases=BILLING_CASE,
    )
    assert decision.escalate is False
