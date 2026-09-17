"""
Unit tests for evaluation/runner.py and evaluation/human_calibration.py.
Uses fake agents/LLM clients throughout -- no real retrieval index and
no live model call. Verifies the golden set is used only as an input
message + a recorded gold label, never passed into the fake agent's
own decision logic.
"""

from agent import AgentResult
from evaluation.human_calibration import build_calibration_template, select_calibration_example_ids
from evaluation.runner import run_agent_predictions
from generation.llm_client import LLMClient, LLMResponse


class SpyAgent:
    """Records exactly what it was called with, so tests can assert no
    gold_intent/gold_secondary_issue/annotator fields ever reach it."""
    def __init__(self):
        self.calls = []

    def handle(self, customer_message, context_messages_json=None, k=5, use_intent_filter=False):
        self.calls.append({"customer_message": customer_message, "k": k, "use_intent_filter": use_intent_filter})
        return AgentResult(
            customer_message=customer_message,
            intent="Premium Subscription & Billing",
            intent_confidence="high",
            secondary_issue=None,
            retrieved_cases=[{
                "rank": 1, "similarity": 0.8, "conversation_id": 1, "resolution_id": "RES-1-1",
                "customer_message": "hist msg", "historical_response": "hist resp",
                "intent": "Premium Subscription & Billing",
            }],
            evidence_sufficient=True,
            reply="Thanks, we'll look into it.",
            escalate=False,
            escalation_reason="NONE",
            trace={
                "intent_reason": "billing_action_keyword", "intent_labeling_method": "deterministic",
                "ambiguous": False, "non_english": False, "retrieval_mode": "global",
                "evidence_reasons": [], "evidence_top_similarity": 0.8, "evidence_distinct_intents": 1,
                "evidence_weak_response_fraction": 0.0, "generation_status": "success", "generation_reason": "ok",
            },
        )


class FakeLLMClient(LLMClient):
    def generate(self, prompt, timeout=30):
        return LLMResponse(text="Premium Subscription & Billing", model="fake")


GOLDEN_ROWS = [
    {"example_id": "GOLD-0001", "customer_message": "I was charged twice", "primary_intent": "Premium Subscription & Billing",
     "secondary_issue": None, "ambiguous": False, "non_english": False, "excluded": False, "exclusion_reason": None,
     "annotator_notes": "some internal note that must never reach the agent"},
    {"example_id": "GOLD-0002", "customer_message": "please add dark mode", "primary_intent": "Feature Request & Product Feedback",
     "secondary_issue": None, "ambiguous": False, "non_english": False, "excluded": False, "exclusion_reason": None,
     "annotator_notes": None},
]


def test_prediction_ids_align_with_golden_ids_in_order():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient())
    assert [r["example_id"] for r in records] == ["GOLD-0001", "GOLD-0002"]


def test_no_duplicate_example_ids():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient())
    ids = [r["example_id"] for r in records]
    assert len(ids) == len(set(ids))


def test_gold_labels_never_passed_into_agent():
    spy = SpyAgent()
    run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient())
    for call in spy.calls:
        assert call["customer_message"] in {"I was charged twice", "please add dark mode"}
        # The agent call signature only carries a raw message string --
        # there is no field in `call` for gold_intent/annotator_notes at
        # all, which is itself the guarantee; this loop also defends
        # against a future signature change that might smuggle one in.
        assert "gold" not in str(call).lower()
        assert "annotator" not in str(call).lower()


def test_gold_fields_are_still_recorded_for_scoring():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient())
    assert records[0]["gold_intent"] == "Premium Subscription & Billing"
    assert records[1]["gold_intent"] == "Feature Request & Product Feedback"


def test_majority_baseline_present_on_every_record():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient())
    assert all(r["majority_baseline_intent"] for r in records)


def test_limit_truncates_examples():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient(), limit=1)
    assert len(records) == 1


def test_llm_baseline_skipped_when_requested():
    spy = SpyAgent()
    records = run_agent_predictions(GOLDEN_ROWS, {"global": spy}, FakeLLMClient(), run_llm_baseline=False)
    assert all(r["llm_baseline_status"] == "skipped" for r in records)


# ---------------------------------------------------------------------
# Human calibration selection reproducibility
# ---------------------------------------------------------------------

def test_calibration_selection_is_reproducible_with_same_seed():
    ids = [f"GOLD-{i:04d}" for i in range(200)]
    a = select_calibration_example_ids(ids, seed=42, n=50)
    b = select_calibration_example_ids(ids, seed=42, n=50)
    assert a == b
    assert len(a) == 50


def test_calibration_selection_differs_with_different_seed():
    ids = [f"GOLD-{i:04d}" for i in range(200)]
    a = select_calibration_example_ids(ids, seed=42, n=50)
    b = select_calibration_example_ids(ids, seed=99, n=50)
    assert a != b


def test_calibration_template_has_null_human_fields():
    records = [{
        "example_id": "GOLD-0001", "customer_message": "msg",
        "global": {"retrieved_cases": [], "reply": "reply text", "escalate": False, "escalation_reason": "NONE"},
    }]
    rows = build_calibration_template(records, {"GOLD-0001"})
    assert len(rows) == 1
    row = rows[0]
    for field in ("human_correctness_1_5", "human_groundedness_1_5", "human_helpfulness_1_5",
                  "human_actionability_1_5", "human_brand_consistency_1_5", "human_hallucination",
                  "human_should_escalate"):
        assert row[field] is None
    assert row["generated_reply"] == "reply text"
