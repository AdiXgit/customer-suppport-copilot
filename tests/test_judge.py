"""
Unit tests for evaluation/judge.py. Fake LLM client only.
"""

from evaluation.judge import build_judge_prompt, parse_judge_response, run_judge
from generation.llm_client import LLMClient, LLMResponse, LLMUnavailableError


class FakeLLMClient(LLMClient):
    def __init__(self, text=None, raises=None):
        self.text = text
        self.raises = raises

    def generate(self, prompt, timeout=30):
        if self.raises:
            raise self.raises
        return LLMResponse(text=self.text, model="fake")


VALID_JUDGE_JSON = (
    '{"correctness": 4, "groundedness": 4, "helpfulness": 3, "actionability": 3, '
    '"brand_consistency": 5, "hallucination": false, "overall_evidence_supported": true, '
    '"reasons": {"correctness": "matches evidence"}}'
)


def test_build_judge_prompt_excludes_gold_fields_and_includes_evidence():
    cases = [{"customer_message": "I was charged twice", "historical_response": "We'll refund it", "similarity": 0.8}]
    prompt = build_judge_prompt("I was charged twice", cases, "Sorry, we'll look into the double charge.")
    assert "I was charged twice" in prompt
    assert "We'll refund it" in prompt
    assert "gold" not in prompt.lower()
    assert "annotator" not in prompt.lower()


def test_parse_judge_response_valid_json():
    parsed = parse_judge_response(VALID_JUDGE_JSON)
    assert parsed["correctness"] == 4
    assert parsed["hallucination"] is False
    assert parsed["overall_evidence_supported"] is True


def test_parse_judge_response_handles_surrounding_text():
    raw = "Here is my evaluation: " + VALID_JUDGE_JSON + " Done."
    parsed = parse_judge_response(raw)
    assert parsed is not None
    assert parsed["groundedness"] == 4


def test_parse_judge_response_rejects_out_of_range_scores():
    bad = '{"correctness": 9, "groundedness": 4, "helpfulness": 3, "actionability": 3, "brand_consistency": 5, "hallucination": false}'
    assert parse_judge_response(bad) is None


def test_parse_judge_response_rejects_missing_fields():
    bad = '{"correctness": 4, "hallucination": false}'
    assert parse_judge_response(bad) is None


def test_parse_judge_response_empty_returns_none():
    assert parse_judge_response("") is None
    assert parse_judge_response(None) is None


def test_run_judge_success():
    client = FakeLLMClient(text=VALID_JUDGE_JSON)
    result = run_judge(client, "I was charged twice", [], "Sorry about that.")
    assert result["status"] == "success"
    assert result["verdict"]["correctness"] == 4


def test_run_judge_llm_unavailable():
    client = FakeLLMClient(raises=LLMUnavailableError("down"))
    result = run_judge(client, "msg", [], "reply")
    assert result["status"] == "llm_unavailable"
    assert result["verdict"] is None


def test_run_judge_unparseable_output():
    client = FakeLLMClient(text="I refuse to answer in JSON.")
    result = run_judge(client, "msg", [], "reply")
    assert result["status"] == "unparseable_output"
    assert result["verdict"] is None
