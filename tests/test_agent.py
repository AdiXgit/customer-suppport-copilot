"""
Unit tests for src/agent.py using injected fake Retriever/Generator --
never the real 41k-row index and never a live LLM. Golden data is not
touched at all in this file.
"""

from dataclasses import dataclass

from agent import SupportAgent
from generation.generator import GenerationResult


class FakeRetriever:
    def __init__(self, results):
        self._results = results
        self.last_call = None

    def search(self, query, k=5, intent=None, exclude_retrieval_ids=None):
        self.last_call = {"query": query, "k": k, "intent": intent}
        return self._results[:k]


class FakeGenerator:
    def __init__(self, result: GenerationResult):
        self._result = result
        self.last_call = None

    def generate(self, customer_message, intent, retrieved_cases, evidence_sufficient):
        self.last_call = {
            "customer_message": customer_message, "intent": intent,
            "retrieved_cases": retrieved_cases, "evidence_sufficient": evidence_sufficient,
        }
        return self._result


def _make_result(rid="RES-1-1", conv_id=1, intent="Premium Subscription & Billing",
                  response_type="substantive_response", score=0.85):
    return {
        "rank": 1, "similarity_score": score, "retrieval_id": rid, "conversation_id": conv_id,
        "customer_tweet_id": 1, "customer_message": "I was charged twice",
        "context_root_message": None, "historical_brand_response": "We'll issue a refund.",
        "response_type": response_type, "primary_intent": intent, "customer_timestamp": "2020-01-01",
    }


def _agent(results, gen_result):
    return SupportAgent(retriever=FakeRetriever(results), generator=FakeGenerator(gen_result))


def _success_result(reply="Thanks, we'll look into the duplicate charge.", evidence_sufficient=True):
    return GenerationResult(reply=reply, evidence_sufficient=evidence_sufficient,
                             generation_status="success", generation_reason="ok")


# ---------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------

def test_end_to_end_output_schema_complete():
    agent = _agent([_make_result()], _success_result())
    result = agent.handle("I was charged twice for my subscription")
    d = result.to_dict()

    for key in ("customer_message", "intent", "intent_confidence", "secondary_issue",
                "retrieved_cases", "evidence_sufficient", "reply", "escalate",
                "escalation_reason", "trace"):
        assert key in d

    import json
    json.dumps(d, default=str)  # must be JSON-serializable

    assert d["retrieved_cases"][0]["resolution_id"] == "RES-1-1"
    assert d["retrieved_cases"][0]["conversation_id"] == 1
    assert d["retrieved_cases"][0]["rank"] == 1
    assert "similarity" in d["retrieved_cases"][0]


def test_source_ids_preserved_through_pipeline():
    agent = _agent([_make_result(rid="RES-99-98", conv_id=42)], _success_result())
    result = agent.handle("I was charged twice for my subscription")
    assert result.retrieved_cases[0]["resolution_id"] == "RES-99-98"
    assert result.retrieved_cases[0]["conversation_id"] == 42


# ---------------------------------------------------------------------
# Global retrieval is the default
# ---------------------------------------------------------------------

def test_global_retrieval_is_default():
    retriever = FakeRetriever([_make_result()])
    agent = SupportAgent(retriever=retriever, generator=FakeGenerator(_success_result()))
    agent.handle("I was charged twice for my subscription")
    assert retriever.last_call["intent"] is None


def test_intent_filter_opt_in_passes_classified_intent():
    retriever = FakeRetriever([_make_result()])
    agent = SupportAgent(retriever=retriever, generator=FakeGenerator(_success_result()))
    agent.handle("I was charged twice for my subscription", use_intent_filter=True)
    assert retriever.last_call["intent"] == "Premium Subscription & Billing"


def test_intent_filter_opt_in_stays_global_for_other_intent():
    retriever = FakeRetriever([_make_result()])
    agent = SupportAgent(retriever=retriever, generator=FakeGenerator(_success_result()))
    agent.handle("thanks", use_intent_filter=True)
    assert retriever.last_call["intent"] is None


# ---------------------------------------------------------------------
# Component failure does not corrupt output
# ---------------------------------------------------------------------

def test_no_retrieval_results_still_produces_valid_output():
    agent = _agent([], GenerationResult(reply="not enough info", evidence_sufficient=False,
                                         generation_status="llm_unavailable", generation_reason="none"))
    result = agent.handle("some totally novel message")
    assert result.retrieved_cases == []
    assert result.evidence_sufficient is False
    assert result.escalate is True
    assert result.escalation_reason == "INSUFFICIENT_EVIDENCE"
    assert isinstance(result.reply, str) and result.reply


def test_generation_failure_falls_back_without_crashing():
    gen_result = GenerationResult(reply="I'm sorry you're having trouble with this. This issue may need further assistance from Spotify Support.",
                                   evidence_sufficient=True, generation_status="llm_unavailable",
                                   generation_reason="llm_unavailable: connection refused")
    agent = _agent([_make_result()], gen_result)
    result = agent.handle("I was charged twice for my subscription")
    assert result.trace["generation_status"] == "llm_unavailable"
    assert result.reply  # non-empty, did not crash


def test_unsupported_action_reply_is_overridden_before_reaching_output():
    agent = _agent([_make_result()], _success_result(reply="I've issued a refund for the duplicate charge."))
    result = agent.handle("I was charged twice for my subscription")
    assert result.escalate is True
    assert result.escalation_reason == "UNSUPPORTED_ACTION"
    assert "issued a refund" not in result.reply


# ---------------------------------------------------------------------
# Security handling
# ---------------------------------------------------------------------

def test_security_intent_escalates_without_strong_evidence():
    agent = _agent(
        [_make_result(intent="Account Security", response_type="dm_redirect")],
        _success_result(reply="This looks like an account-security issue that needs further assistance."),
    )
    result = agent.handle("my account was hacked and someone changed my email")
    assert result.intent == "Account Security"
    assert result.escalate is True
    assert result.escalation_reason == "SECURITY_RISK"


# ---------------------------------------------------------------------
# OTHER / ambiguity preservation
# ---------------------------------------------------------------------

def test_other_intent_preserved_when_classifier_has_no_match():
    agent = _agent([_make_result()], _success_result())
    result = agent.handle("ok cool thanks for that info I guess")
    assert result.intent == "OTHER / UNKNOWN"


def test_ambiguous_secondary_issue_preserved():
    agent = _agent([_make_result()], _success_result())
    result = agent.handle("my account was hacked and now I'm being charged for a subscription I didn't want")
    assert result.intent == "Account Security"
    assert result.secondary_issue == "Premium Subscription & Billing"
