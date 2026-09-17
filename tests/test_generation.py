"""
Unit tests for src/generation/*. Uses a fake LLMClient -- never a live
Ollama call and never the golden set.
"""

import pytest

from generation.generator import (
    FALLBACK_REPLY,
    GENERATION_STATUS_GENERATION_ERROR,
    GENERATION_STATUS_LLM_UNAVAILABLE,
    GENERATION_STATUS_SUCCESS,
    Generator,
)
from generation.llm_client import LLMClient, LLMResponse, LLMUnavailableError
from generation.prompts import build_prompt, parse_structured_response
from escalation.policy import _reply_claims_unsupported_action


class FakeLLMClient(LLMClient):
    def __init__(self, response_text=None, raises=None):
        self.response_text = response_text
        self.raises = raises
        self.last_prompt = None

    def generate(self, prompt, timeout=30):
        self.last_prompt = prompt
        if self.raises:
            raise self.raises
        return LLMResponse(text=self.response_text, model="fake-model")


RETRIEVED_CASES = [
    {"customer_message": "I was charged twice", "historical_response": "We'll issue a refund.", "similarity": 0.85},
]


def test_valid_structured_response_returns_success():
    client = FakeLLMClient(response_text='{"reply": "Sorry about that, we can look into the duplicate charge.", "evidence_sufficient": true, "generation_reason": "close match found"}')
    gen = Generator(client)
    result = gen.generate("I was charged twice", "Premium Subscription & Billing", RETRIEVED_CASES, True)
    assert result.generation_status == GENERATION_STATUS_SUCCESS
    assert "duplicate charge" in result.reply
    assert result.evidence_sufficient is True


def test_malformed_llm_output_falls_back_to_raw_text():
    client = FakeLLMClient(response_text="Sure, here's a reply: sorry about the trouble, we'll look into it.")
    gen = Generator(client)
    result = gen.generate("issue", "OTHER / UNKNOWN", [], True)
    assert result.generation_status == GENERATION_STATUS_SUCCESS
    assert result.generation_reason == "unstructured_output_used_as_reply"
    assert "sorry about the trouble" in result.reply.lower()


def test_llm_returns_empty_response_is_generation_error():
    client = FakeLLMClient(response_text="   ")
    gen = Generator(client)
    result = gen.generate("issue", "OTHER / UNKNOWN", [], True)
    assert result.generation_status == GENERATION_STATUS_GENERATION_ERROR
    assert result.reply == FALLBACK_REPLY


def test_llm_unavailable_uses_fallback_reply():
    client = FakeLLMClient(raises=LLMUnavailableError("connection refused"))
    gen = Generator(client)
    result = gen.generate("issue", "OTHER / UNKNOWN", [], False)
    assert result.generation_status == GENERATION_STATUS_LLM_UNAVAILABLE
    assert result.reply == FALLBACK_REPLY
    assert result.evidence_sufficient is False


def test_no_llm_client_configured_uses_fallback():
    gen = Generator(None)
    result = gen.generate("issue", "OTHER / UNKNOWN", [], True)
    assert result.generation_status == GENERATION_STATUS_LLM_UNAVAILABLE
    assert result.reply == FALLBACK_REPLY


def test_fallback_reply_contains_no_unsupported_claims():
    assert not _reply_claims_unsupported_action(FALLBACK_REPLY)


def test_build_prompt_includes_customer_message_intent_and_cases():
    prompt = build_prompt("I was charged twice", "Premium Subscription & Billing", RETRIEVED_CASES)
    assert "I was charged twice" in prompt
    assert "Premium Subscription & Billing" in prompt
    assert "We'll issue a refund." in prompt
    assert "0.85" in prompt


def test_build_prompt_handles_no_retrieved_cases():
    prompt = build_prompt("something", "OTHER / UNKNOWN", [])
    assert "none retrieved" in prompt


def test_parse_structured_response_handles_extra_surrounding_text():
    raw = 'Sure! Here is the JSON: {"reply": "ok", "evidence_sufficient": false, "generation_reason": "weak"} Thanks.'
    parsed = parse_structured_response(raw)
    assert parsed == {"reply": "ok", "evidence_sufficient": False, "generation_reason": "weak"}


def test_parse_structured_response_returns_none_for_no_json():
    assert parse_structured_response("just plain text with no json at all") is None
    assert parse_structured_response("") is None
