"""
Phase 13: unit tests for ui/helpers.py -- the only new non-UI logic
introduced for the Streamlit frontend. No streamlit import, no agent
construction; these are pure functions.
"""

from ui.helpers import (
    MAX_MESSAGE_LENGTH,
    describe_agent_error,
    format_similarity,
    missing_provider_key_warning,
    validate_message,
)


def test_validate_message_rejects_none():
    assert validate_message(None) is not None


def test_validate_message_rejects_empty_string():
    assert validate_message("") is not None


def test_validate_message_rejects_whitespace_only():
    assert validate_message("   \n\t  ") is not None


def test_validate_message_accepts_normal_text():
    assert validate_message("I was charged twice for Premium") is None


def test_validate_message_rejects_overly_long_input():
    long_message = "a" * (MAX_MESSAGE_LENGTH + 1)
    error = validate_message(long_message)
    assert error is not None
    assert str(MAX_MESSAGE_LENGTH) in error


def test_validate_message_accepts_exactly_max_length():
    assert validate_message("a" * MAX_MESSAGE_LENGTH) is None


def test_format_similarity_none_is_na():
    assert format_similarity(None) == "N/A"


def test_format_similarity_formats_to_three_decimals():
    assert format_similarity(0.8267123) == "0.827"


def test_format_similarity_handles_zero():
    assert format_similarity(0.0) == "0.000"


def test_describe_agent_error_missing_index_file():
    msg = describe_agent_error(FileNotFoundError("data/retrieval/spotifycares.index not found"))
    assert "build_retrieval_index.py" in msg


def test_describe_agent_error_corrupt_index():
    msg = describe_agent_error(ValueError("Vector/metadata row-count mismatch: 100 vs 99"))
    assert "build_retrieval_index.py" in msg


def test_describe_agent_error_ollama_unreachable():
    msg = describe_agent_error(RuntimeError("Could not reach Ollama at http://localhost:11434"))
    assert "Ollama" in msg
    assert "fallback" in msg.lower()


def test_describe_agent_error_generic_fallback_includes_original_text():
    msg = describe_agent_error(RuntimeError("something entirely unexpected happened"))
    assert "something entirely unexpected happened" in msg


def test_describe_agent_error_groq_unreachable():
    msg = describe_agent_error(RuntimeError("Could not reach Groq: connection refused"))
    assert "Groq" in msg
    assert "fallback" in msg.lower()


def test_missing_provider_key_warning_groq_without_key():
    warning = missing_provider_key_warning("groq", has_key=False)
    assert warning is not None
    assert "GROQ_API_KEY" in warning


def test_missing_provider_key_warning_groq_with_key():
    assert missing_provider_key_warning("groq", has_key=True) is None


def test_missing_provider_key_warning_ollama_never_warns():
    assert missing_provider_key_warning("ollama", has_key=False) is None
    assert missing_provider_key_warning("ollama", has_key=True) is None
