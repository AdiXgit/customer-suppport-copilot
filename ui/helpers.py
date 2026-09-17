"""
Phase 13: pure, UI-independent helper functions for the Streamlit
frontend (app.py). Kept separate and side-effect-free -- no `streamlit`
import, no `SupportAgent` construction -- so they're unit-testable in
isolation. All actual agent logic (intent, retrieval, evidence,
generation, escalation) lives in src/ and is never duplicated here.
"""

from __future__ import annotations

MAX_MESSAGE_LENGTH = 2000


def validate_message(message: str | None) -> str | None:
    """Returns a user-facing error string if `message` isn't a valid
    agent input, or None if it's fine to submit."""
    if message is None or not message.strip():
        return "Please enter a customer message before analyzing."
    if len(message) > MAX_MESSAGE_LENGTH:
        return f"Message is too long ({len(message)} chars) -- keep it under {MAX_MESSAGE_LENGTH}."
    return None


def format_similarity(value: float | None) -> str:
    """Renders a similarity score for display, handling the None case
    (e.g. no retrieved evidence, or a trace field that wasn't set)
    without crashing on an f-string format spec."""
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def describe_agent_error(exc: Exception) -> str:
    """Turns an exception raised while constructing or running the agent
    into a short, actionable, user-facing explanation -- never a raw
    traceback. Covers the failure modes a fresh clone of this repo will
    actually hit (missing retrieval index, unavailable local LLM)."""
    text = str(exc)
    lowered = text.lower()

    if isinstance(exc, FileNotFoundError) or "no such file" in lowered:
        return (
            "Retrieval index files are missing. Run "
            "`scripts/build_retrieval_index.py` to generate "
            "data/retrieval/spotifycares.index and related files, then restart the app."
        )
    if "row-count mismatch" in lowered or "index is corrupt" in lowered:
        return (
            "The retrieval index looks corrupted or stale. Re-run "
            "scripts/build_retrieval_index.py to regenerate it."
        )
    if "could not reach ollama" in lowered or "ollama" in lowered:
        return (
            "The local LLM (Ollama) could not be reached. The agent will still "
            "run using its deterministic fallback reply -- start Ollama "
            "(`ollama pull gemma2:9b-instruct-q4_0` then relaunch it) for "
            "LLM-generated replies."
        )
    return f"The agent could not process this message: {text}"
