"""
Phase 9, Step 12: real-data smoke test.

Runs the full agent against the REAL Phase 8 retrieval index with a
forced-unavailable LLM client (never a live Ollama call in the test
suite -- keeps this deterministic and fast), across representative
queries spanning every canonical intent plus OTHER/UNKNOWN. This is
NOT the final evaluation (Phase 10) -- just a sanity check that the
wired-together pipeline behaves and doesn't crash on real data.
"""

from pathlib import Path

import pytest

from agent import SupportAgent
from generation.generator import Generator
from generation.llm_client import LLMClient, LLMUnavailableError

REPO_ROOT = Path(__file__).parent.parent
INDEX_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares.index"
METADATA_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_metadata.parquet"
VECTORS_PATH = REPO_ROOT / "data" / "retrieval" / "spotifycares_vectors.npy"

_ALL_PRESENT = INDEX_PATH.exists() and METADATA_PATH.exists() and VECTORS_PATH.exists()
pytestmark = pytest.mark.skipif(not _ALL_PRESENT, reason="Retrieval index not built in this environment")


class AlwaysUnavailableLLMClient(LLMClient):
    """Forces the deterministic fallback path without requiring a live
    Ollama server -- this test suite must be runnable offline."""
    def generate(self, prompt, timeout=30):
        raise LLMUnavailableError("forced unavailable for smoke test")


@pytest.fixture(scope="module")
def agent():
    from retrieval.retriever import Retriever
    retriever = Retriever(INDEX_PATH, METADATA_PATH, VECTORS_PATH)
    generator = Generator(AlwaysUnavailableLLMClient())
    return SupportAgent(retriever=retriever, generator=generator)


REPRESENTATIVE_MESSAGES = [
    ("Account Access", "I can't log in, it keeps saying my password is wrong"),
    ("Account Security", "my account was hacked and someone changed my email"),
    ("Billing", "I was charged twice for my premium subscription this month"),
    ("Technical", "the app keeps crashing every time I try to play a song"),
    ("Content", "why isn't the new album available on Spotify"),
    ("Feature", "please add a dark mode option to the app"),
    ("Complaint", "this is the worst customer service I've ever experienced"),
    ("Market", "when will Spotify be available in my country"),
    ("OTHER", "ok thanks"),
]


@pytest.mark.parametrize("label,message", REPRESENTATIVE_MESSAGES)
def test_agent_produces_valid_output_for_representative_message(agent, label, message):
    result = agent.handle(message)
    d = result.to_dict()

    import json
    json.dumps(d, default=str)

    assert d["customer_message"] == message
    assert isinstance(d["reply"], str) and d["reply"]
    assert isinstance(d["escalate"], bool)
    assert d["escalation_reason"] in {
        "SECURITY_RISK", "EXPLICIT_HUMAN_REQUEST", "INSUFFICIENT_EVIDENCE",
        "UNSUPPORTED_ACTION", "CONFLICTING_EVIDENCE", "LOW_CONFIDENCE", "NONE",
    }
    # LLM is forced unavailable -- fallback reply must be used, never a
    # fabricated "historically grounded" answer.
    assert d["trace"]["generation_status"] == "llm_unavailable"
    for c in d["retrieved_cases"]:
        assert c["resolution_id"]
        assert c["conversation_id"] is not None


def test_security_message_escalates_on_real_index(agent):
    result = agent.handle("my account was hacked and someone changed my email")
    assert result.intent == "Account Security"
    assert result.escalate is True
    assert result.escalation_reason in {"SECURITY_RISK", "EXPLICIT_HUMAN_REQUEST"}


def test_other_message_does_not_crash_and_uses_global_retrieval(agent):
    result = agent.handle("ok thanks")
    assert result.intent == "OTHER / UNKNOWN"
    assert result.trace["retrieval_mode"] == "global"


def test_fallback_reply_used_when_llm_unavailable(agent):
    from generation.generator import FALLBACK_REPLY
    result = agent.handle("I was charged twice for my premium subscription this month")
    assert result.trace["generation_status"] == "llm_unavailable"
    assert result.reply == FALLBACK_REPLY
