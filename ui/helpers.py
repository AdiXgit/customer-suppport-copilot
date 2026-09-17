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


def format_case_count(n: int) -> str:
    """Renders an integer count with thousands separators for display,
    e.g. 41092 -> '41,092'. Pure formatting only -- the count itself
    always comes from the real, live retrieval index (agent.retriever),
    never a hard-coded number."""
    return f"{n:,}"


def pipeline_stage_icon(status: str) -> str:
    """Maps a pipeline stage's status to a small presentation glyph. Used
    for the post-analysis stage summary row -- purely presentational,
    derived from fields already present on AgentResult/its trace, never
    a new judgment about correctness."""
    return {"ok": "✓", "warn": "⚠", "error": "✗"}.get(status, "✓")


def missing_provider_key_warning(provider: str, has_key: bool) -> str | None:
    """Returns a proactive warning to show before the agent even runs, if
    the configured provider needs a key that isn't set. Never touches the
    key itself -- only a bool of whether it's present. Returns None when
    there's nothing to warn about (Ollama needs no key)."""
    if provider == "groq" and not has_key:
        return (
            "GROQ_API_KEY is not set. Generation will use the safe fallback "
            "reply until it's configured (see .env.example)."
        )
    return None


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
    if "ollama" in lowered:
        return (
            "The local LLM (Ollama) could not be reached. The agent will still "
            "run using its deterministic fallback reply -- start Ollama "
            "(`ollama pull gemma2:9b-instruct-q4_0` then relaunch it) for "
            "LLM-generated replies."
        )
    if "groq" in lowered or "groq_api_key" in lowered:
        return (
            "Groq could not be reached (or GROQ_API_KEY is not set). The agent "
            "will still run using its deterministic fallback reply -- check "
            "your .env and network connectivity for LLM-generated replies."
        )
    return f"The agent could not process this message: {text}"
