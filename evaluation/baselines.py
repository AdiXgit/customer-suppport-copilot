"""
Phase 10, Steps 3-4: two intent-classification baselines.

Baseline 1 (majority class) uses the Phase 7D deterministic-corpus
intent distribution (data/processed/twitter/spotifycares_intent_corpus.parquet)
-- NOT the golden set -- to pick the single most frequent label, per
the explicit instruction that the majority class must come from an
already-available non-golden source.

Baseline 2 (simple LLM classifier) sends ONLY the customer message and
the canonical taxonomy to the currently-working local Ollama model --
no retrieved evidence, no Phase 8/9 machinery, no golden examples in
the prompt.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from generation.llm_client import LLMClient, LLMUnavailableError
from intent.deterministic_classifier import CANONICAL_INTENTS, OTHER

REPO_ROOT = Path(__file__).parent.parent
INTENT_CORPUS_PATH = REPO_ROOT / "data" / "processed" / "twitter" / "spotifycares_intent_corpus.parquet"

# Short, human-written paraphrases of docs/INTENTS.md's definitions --
# concise on purpose (Step 4: "concise intent definitions"), not copied
# verbatim from the full taxonomy doc.
INTENT_DEFINITIONS = {
    "Account Access & Login": "Customer cannot log in, register, or manage basic account access (password reset, linked email, username) with no sign of a third party involved.",
    "Account Security": "Customer reports their account was hacked, compromised, or used without authorization by someone else.",
    "Premium Subscription & Billing": "Questions or complaints about payment, charges, refunds, subscription plans, or billing.",
    "App & Playback Technical Issues": "The app or playback is malfunctioning: crashes, errors, buffering, skipping, broken UI elements.",
    "Content Availability & Catalog Accuracy": "A specific song, album, artist, or podcast is missing, removed, region-locked, or mislabeled.",
    "Feature Request & Product Feedback": "Customer is requesting a new feature or suggesting a product improvement.",
    "General Complaint / Service Dissatisfaction": "General dissatisfaction or venting about the service, not tied to one specific actionable problem.",
    "Country/Market Availability Inquiry": "Asking when/whether the whole Spotify service will be available in their country or region.",
    "OTHER / UNKNOWN": "Praise, off-topic content, or anything that doesn't fit the other 8 categories.",
}

BASELINE_SYSTEM_PROMPT = """You are classifying a customer support message into exactly ONE of the following categories.

Categories:
{definitions}

Respond with ONLY the exact category name from the list above, nothing else.

Customer message:
{message}

Category:"""


def majority_class_baseline(corpus_path: Path = INTENT_CORPUS_PATH) -> dict:
    """Returns {"majority_intent": ..., "source": ..., "distribution": ...}."""
    df = pl.read_parquet(corpus_path)
    counts = df["primary_intent"].value_counts().sort("count", descending=True)
    majority_intent = counts["primary_intent"][0]
    distribution = dict(zip(counts["primary_intent"].to_list(), counts["count"].to_list()))
    return {
        "majority_intent": majority_intent,
        "source": str(corpus_path.relative_to(REPO_ROOT)),
        "source_row_count": df.height,
        "source_distribution": distribution,
    }


def predict_majority_baseline(messages: list[str], majority_intent: str) -> list[str]:
    return [majority_intent] * len(messages)


def _normalize_for_matching(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _match_to_canonical(raw_text: str) -> str:
    """Robust parsing: the model may add punctuation/quotes/extra
    words. Match by normalized substring against the 9 canonical
    labels; fall back to OTHER if nothing matches confidently."""
    normalized_raw = _normalize_for_matching(raw_text or "")
    for intent in CANONICAL_INTENTS:
        if _normalize_for_matching(intent) in normalized_raw:
            return intent
    # Try a looser keyword match on a few distinctive words per intent.
    loose_hints = {
        "Account Access & Login": ["login", "log in", "password", "access"],
        "Account Security": ["hack", "security", "compromis", "unauthoriz"],
        "Premium Subscription & Billing": ["billing", "subscription", "charge", "payment", "refund"],
        "App & Playback Technical Issues": ["technical", "playback", "crash", "bug"],
        "Content Availability & Catalog Accuracy": ["content", "catalog", "availability"],
        "Feature Request & Product Feedback": ["feature", "feedback", "request"],
        "General Complaint / Service Dissatisfaction": ["complaint", "dissatisf"],
        "Country/Market Availability Inquiry": ["country", "market", "region"],
    }
    lowered = (raw_text or "").lower()
    for intent, hints in loose_hints.items():
        if any(h in lowered for h in hints):
            return intent
    return OTHER


def simple_llm_intent_classifier(llm_client: LLMClient, customer_message: str) -> dict:
    """Returns {"predicted_intent": ..., "raw_output": ..., "status": "success"|"llm_unavailable"}."""
    definitions_block = "\n".join(f"- {name}: {desc}" for name, desc in INTENT_DEFINITIONS.items())
    prompt = BASELINE_SYSTEM_PROMPT.format(definitions=definitions_block, message=customer_message)
    try:
        response = llm_client.generate(prompt)
    except LLMUnavailableError as e:
        return {"predicted_intent": None, "raw_output": None, "status": "llm_unavailable", "error": str(e)}
    predicted = _match_to_canonical(response.text)
    return {"predicted_intent": predicted, "raw_output": response.text.strip(), "status": "success"}
