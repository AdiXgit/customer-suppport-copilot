"""
Phase 13 (+ Phase 15: presentation polish): Streamlit frontend for the
SpotifyCares support agent.

Thin UI only. All intent classification, historical retrieval, evidence
assessment, grounded generation, and escalation-policy logic lives in
src/ and is reused unchanged via SupportAgent.handle() -- this file never
re-implements any of it, and this polish pass changed presentation only
(layout, cards, copy) with zero backend/agent-logic changes. See
ui/helpers.py for the small amount of pure, unit-tested
display-formatting logic that *is* new here.

Run:
    .venv/Scripts/streamlit.exe run app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from agent import SupportAgent  # noqa: E402
from generation.llm_client import DEFAULT_GROQ_MODEL, DEFAULT_OLLAMA_MODEL  # noqa: E402
from retrieval.embeddings import MODEL_NAME as EMBEDDING_MODEL_NAME  # noqa: E402

from ui.helpers import (  # noqa: E402
    describe_agent_error,
    format_case_count,
    format_similarity,
    missing_provider_key_warning,
    pipeline_stage_icon,
    validate_message,
)

st.set_page_config(page_title="SpotifyCares Support Agent", page_icon="🎧", layout="wide")

# Minimal, theme-aware styling only -- no hard-coded light/dark colors
# (Streamlit's own CSS variables already track the viewer's theme), no
# gradients, no animation. Just consistent card/section spacing.
st.markdown(
    """
    <style>
    .stat-card {
        border: 1px solid var(--secondary-background-color);
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
        background-color: var(--secondary-background-color);
        margin-bottom: 0.6rem;
    }
    .status-dot {
        height: 0.6rem;
        width: 0.6rem;
        border-radius: 50%;
        display: inline-block;
        margin-right: 0.4rem;
    }
    .status-dot-on { background-color: #2ecc71; }
    .status-dot-off { background-color: #95a5a6; }
    .pipeline-stage {
        text-align: center;
        padding: 0.5rem 0.25rem;
        border-radius: 6px;
        background-color: var(--secondary-background-color);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _configured_provider() -> str:
    """Reads which provider is configured, without ever touching the
    actual API key value -- only its presence/absence."""
    return os.environ.get("LLM_PROVIDER", "ollama").strip().lower()


def _configured_model(provider: str) -> str:
    if provider == "groq":
        return os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL
    return DEFAULT_OLLAMA_MODEL


@st.cache_resource(show_spinner="Loading retrieval index and agent...")
def load_agent() -> SupportAgent:
    return SupportAgent()


def render_header(provider: str, model: str, has_key: bool) -> None:
    title_col, status_col = st.columns([3, 1])
    with title_col:
        st.title("🎧 SpotifyCares Support Agent")
        st.caption("AI support copilot grounded in historical SpotifyCares resolutions")
    with status_col:
        connected = has_key if provider == "groq" else True
        dot_class = "status-dot-on" if connected else "status-dot-off"
        provider_label = provider.capitalize()
        status_text = "Connected" if connected else "Not connected (no API key)"
        st.markdown(
            f'<div class="stat-card">'
            f'<span class="status-dot {dot_class}"></span>'
            f"<strong>{provider_label} {status_text}</strong><br/>"
            f'<span style="font-size:0.85em;opacity:0.75;">Model: {model}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render_sidebar(provider: str, model: str, has_key: bool, agent: SupportAgent | None) -> tuple[int, bool]:
    with st.sidebar:
        key_warning = missing_provider_key_warning(provider, has_key)
        if key_warning:
            st.warning(key_warning)

        st.header("Retrieval")
        k = st.slider("Historical cases (k)", min_value=1, max_value=10, value=5)
        mode_label = st.radio(
            "Retrieval mode",
            options=["Global retrieval", "Intent-filtered retrieval"],
            help=(
                "Global searches the full historical index. Intent-filtered "
                "restricts the search to cases sharing the predicted intent."
            ),
        )
        use_intent_filter = mode_label == "Intent-filtered retrieval"

        st.divider()
        st.header("Knowledge base")
        if agent is not None:
            n_cases = agent.retriever.index.ntotal
            st.markdown(
                f'<div class="stat-card">'
                f"{format_case_count(n_cases)} historical resolution candidates<br/>"
                f"FAISS semantic retrieval<br/>"
                f"{EMBEDDING_MODEL_NAME.split('/')[-1]} embeddings"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("Knowledge base stats unavailable until the index loads.")

        st.divider()
        st.caption(
            "This is a take-home evaluation demo, not a production deployment. "
            "No UI-side agent logic -- every result comes straight from "
            "`SupportAgent.handle()` in `src/agent.py`."
        )

    return k, use_intent_filter


def render_pipeline_summary(result) -> None:
    gen_status = result.trace.get("generation_status")
    stages = [
        ("Intent", "ok"),
        ("Retrieval", "ok" if result.retrieved_cases else "warn"),
        ("Evidence", "ok" if result.evidence_sufficient else "warn"),
        ("Generation", "ok" if gen_status == "success" else ("warn" if gen_status == "llm_unavailable" else "error")),
        ("Escalation", "ok"),
    ]
    cols = st.columns(len(stages))
    for col, (label, status) in zip(cols, stages):
        with col:
            st.markdown(
                f'<div class="pipeline-stage">{label}<br/><strong>{pipeline_stage_icon(status)}</strong></div>',
                unsafe_allow_html=True,
            )


def render_escalation_card(result) -> None:
    if result.escalate:
        st.error(f"**ESCALATE TO HUMAN**\n\nReason: {result.escalation_reason}")
    else:
        st.success(f"**AUTO-HANDLE**\n\nReason: {result.escalation_reason}")


def render_intent_row(result) -> None:
    intent_col, conf_col, secondary_col = st.columns(3)
    intent_col.metric("Predicted intent", result.intent)
    conf_col.metric("Confidence", result.intent_confidence)
    secondary_col.metric("Secondary issue", result.secondary_issue or "None")


def render_reply_card(result, provider: str) -> None:
    st.subheader("Drafted reply")
    st.markdown(f'<div class="stat-card">{result.reply}</div>', unsafe_allow_html=True)

    gen_status = result.trace.get("generation_status")
    provider_label = "Groq" if provider == "groq" else "Ollama"
    if gen_status == "llm_unavailable":
        st.warning(
            f"{provider_label} was unavailable, so this reply is the fixed, "
            "safe fallback template, not an LLM-generated response. "
            f"Reason: {result.trace.get('generation_reason')}"
        )
    elif gen_status == "generation_error":
        st.warning(
            f"Generation error from {provider_label}, fallback reply used instead: "
            f"{result.trace.get('generation_reason')}"
        )
    elif gen_status == "success":
        st.caption(f"Generated by: {provider_label}")


def render_evidence_section(result) -> None:
    st.subheader("Historical evidence used")
    if not result.retrieved_cases:
        st.write("No historical evidence was retrieved for this message.")
        return

    for case in result.retrieved_cases:
        title = f"#{case['rank']} · Similarity: {format_similarity(case['similarity'])} · Intent: {case['intent']}"
        with st.expander(title, expanded=(case["rank"] == 1)):
            st.markdown("**Customer:**")
            st.write(case["customer_message"])
            st.markdown("**SpotifyCares response:**")
            st.write(case["historical_response"])

    with st.expander("Evidence assessment"):
        reasons = result.trace.get("evidence_reasons") or []
        st.markdown(f"- **Top similarity:** {format_similarity(result.trace.get('evidence_top_similarity'))}")
        st.markdown(f"- **Distinct intents in evidence:** {result.trace.get('evidence_distinct_intents')}")
        st.markdown(f"- **Weak-response fraction:** {result.trace.get('evidence_weak_response_fraction')}")
        st.markdown(f"- **Retrieval mode used:** {result.trace.get('retrieval_mode')}")
        st.markdown(f"- **Reasons:** {', '.join(reasons) if reasons else '(none -- evidence was sufficient)'}")


def render_result(result, provider: str) -> None:
    render_pipeline_summary(result)
    st.divider()
    render_escalation_card(result)
    render_intent_row(result)
    render_reply_card(result, provider)
    render_evidence_section(result)

    with st.expander("Full trace (debug)"):
        st.json(result.to_dict())


def main() -> None:
    provider = _configured_provider()
    model = _configured_model(provider)
    has_key = bool(os.environ.get("GROQ_API_KEY"))

    render_header(provider, model, has_key)
    st.divider()

    try:
        agent = load_agent()
        agent_error = None
    except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not swallowed
        agent = None
        agent_error = exc

    k, use_intent_filter = render_sidebar(provider, model, has_key, agent)

    st.subheader("Analyze a customer issue")
    message = st.text_area(
        "Customer message",
        height=120,
        placeholder="Describe the customer's problem...",
        label_visibility="collapsed",
    )
    analyze = st.button("Analyze", type="primary", use_container_width=True)

    if not analyze:
        return

    error = validate_message(message)
    if error:
        st.warning(error)
        return

    if agent_error is not None:
        st.error(describe_agent_error(agent_error))
        return

    with st.spinner("Running the agent pipeline..."):
        try:
            result = agent.handle(message, k=k, use_intent_filter=use_intent_filter)
        except Exception as exc:  # noqa: BLE001
            st.error(describe_agent_error(exc))
            return

    render_result(result, provider)


if __name__ == "__main__":
    main()
