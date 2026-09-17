"""
Unit tests for evaluation/baselines.py. Uses a fake LLM client for the
simple-LLM-baseline path -- never a live Ollama call, never golden data.
"""

from evaluation.baselines import (
    INTENT_DEFINITIONS,
    _match_to_canonical,
    majority_class_baseline,
    predict_majority_baseline,
    simple_llm_intent_classifier,
)
from generation.llm_client import LLMClient, LLMResponse, LLMUnavailableError
from intent.deterministic_classifier import CANONICAL_INTENTS, OTHER


class FakeLLMClient(LLMClient):
    def __init__(self, text=None, raises=None):
        self.text = text
        self.raises = raises

    def generate(self, prompt, timeout=30):
        if self.raises:
            raise self.raises
        return LLMResponse(text=self.text, model="fake")


def test_majority_baseline_reads_from_intent_corpus_not_golden():
    result = majority_class_baseline()
    assert result["majority_intent"] in CANONICAL_INTENTS
    assert "spotifycares_intent_corpus.parquet" in result["source"]
    assert result["source_row_count"] > 0


def test_predict_majority_baseline_repeats_same_label():
    preds = predict_majority_baseline(["msg1", "msg2", "msg3"], "Premium Subscription & Billing")
    assert preds == ["Premium Subscription & Billing"] * 3


def test_match_to_canonical_exact_label():
    assert _match_to_canonical("Premium Subscription & Billing") == "Premium Subscription & Billing"


def test_match_to_canonical_with_extra_text():
    assert _match_to_canonical("The category is: App & Playback Technical Issues.") == "App & Playback Technical Issues"


def test_match_to_canonical_loose_keyword_fallback():
    assert _match_to_canonical("this is a billing issue") == "Premium Subscription & Billing"


def test_match_to_canonical_unrecognized_falls_back_to_other():
    assert _match_to_canonical("banana") == OTHER


def test_simple_llm_baseline_success():
    client = FakeLLMClient(text="Account Security")
    result = simple_llm_intent_classifier(client, "my account was hacked")
    assert result["status"] == "success"
    assert result["predicted_intent"] == "Account Security"


def test_simple_llm_baseline_llm_unavailable():
    client = FakeLLMClient(raises=LLMUnavailableError("down"))
    result = simple_llm_intent_classifier(client, "my account was hacked")
    assert result["status"] == "llm_unavailable"
    assert result["predicted_intent"] is None


def test_intent_definitions_cover_all_nine_canonical_intents():
    assert set(INTENT_DEFINITIONS.keys()) == CANONICAL_INTENTS
