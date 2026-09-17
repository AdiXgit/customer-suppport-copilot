"""
Phase 14: unit tests for GroqLLMClient and the LLM_PROVIDER selection
factory in src/generation/llm_client.py. Every test here mocks the `groq`
SDK -- none of them make a real network call or require a real
GROQ_API_KEY. LocalLLMClient's own HTTP behavior is already covered
indirectly via test_generation.py's FakeLLMClient-based tests and is not
re-tested here since it wasn't changed except for its DEFAULT_MODEL ->
DEFAULT_OLLAMA_MODEL rename.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from generation.llm_client import (
    DEFAULT_GROQ_MODEL,
    GroqLLMClient,
    LLMUnavailableError,
    LocalLLMClient,
    get_llm_client,
)


def _fake_chat_completion(text: str):
    """Mimics the shape of a groq ChatCompletion response far enough for
    GroqLLMClient.generate() to extract .choices[0].message.content."""
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class FakeGroqSDKClient:
    """Stands in for `groq.Groq(...)`. `chat.completions.create` is a
    plain attribute set per-test to either return a fake response or
    raise, so tests never touch the real SDK's network code."""

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._create_impl = None

    def _create(self, **kwargs):
        return self._create_impl(**kwargs)


# ---------------------------------------------------------------------
# Successful structured generation
# ---------------------------------------------------------------------

def test_groq_successful_generation_returns_reply_text(monkeypatch):
    fake_sdk_client = FakeGroqSDKClient()
    fake_sdk_client._create_impl = lambda **kw: _fake_chat_completion(
        '{"reply": "Sorry about the duplicate charge.", "evidence_sufficient": true, "generation_reason": "close match"}'
    )
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key", model="openai/gpt-oss-20b")
    response = client.generate("some prompt")

    assert "duplicate charge" in response.text
    assert response.model == "openai/gpt-oss-20b"
    assert response.raw is None


def test_groq_passes_model_and_prompt_to_sdk(monkeypatch):
    captured = {}

    fake_sdk_client = FakeGroqSDKClient()

    def _create(**kwargs):
        captured.update(kwargs)
        return _fake_chat_completion("ok")

    fake_sdk_client._create_impl = _create
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key", model="some-model")
    client.generate("the actual prompt text", timeout=15)

    assert captured["model"] == "some-model"
    assert captured["messages"] == [{"role": "user", "content": "the actual prompt text"}]
    assert captured["timeout"] == 15


def test_groq_uses_default_model_when_none_configured(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    client = GroqLLMClient(api_key="fake-test-key")
    assert client.model == DEFAULT_GROQ_MODEL


def test_groq_reads_model_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "some/other-model")
    client = GroqLLMClient(api_key="fake-test-key")
    assert client.model == "some/other-model"


# ---------------------------------------------------------------------
# Malformed / empty API output
# ---------------------------------------------------------------------

def test_groq_empty_choices_raises_unavailable(monkeypatch):
    fake_sdk_client = FakeGroqSDKClient()
    fake_sdk_client._create_impl = lambda **kw: SimpleNamespace(choices=[])
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key")
    with pytest.raises(LLMUnavailableError, match="no content"):
        client.generate("prompt")


def test_groq_empty_message_content_raises_unavailable(monkeypatch):
    fake_sdk_client = FakeGroqSDKClient()
    fake_sdk_client._create_impl = lambda **kw: _fake_chat_completion("")
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key")
    with pytest.raises(LLMUnavailableError, match="no content"):
        client.generate("prompt")


# ---------------------------------------------------------------------
# API failure
# ---------------------------------------------------------------------

def test_groq_api_error_raises_llm_unavailable(monkeypatch):
    import groq

    fake_sdk_client = FakeGroqSDKClient()

    def _raise(**kw):
        raise groq.APIConnectionError(request=SimpleNamespace())

    fake_sdk_client._create_impl = _raise
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key")
    with pytest.raises(LLMUnavailableError):
        client.generate("prompt")


def test_groq_unexpected_exception_still_raises_llm_unavailable(monkeypatch):
    fake_sdk_client = FakeGroqSDKClient()

    def _raise(**kw):
        raise TimeoutError("connection timed out")

    fake_sdk_client._create_impl = _raise
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key="fake-test-key")
    with pytest.raises(LLMUnavailableError):
        client.generate("prompt")


# ---------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------

def test_groq_missing_api_key_raises_without_calling_sdk(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    sdk_was_called = []
    monkeypatch.setattr("groq.Groq", lambda api_key=None: sdk_was_called.append(True))

    client = GroqLLMClient(api_key=None)
    with pytest.raises(LLMUnavailableError, match="GROQ_API_KEY is not set"):
        client.generate("prompt")

    assert sdk_was_called == []  # never even attempted to construct the SDK client


def test_groq_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-provided-key")
    client = GroqLLMClient()
    assert client.api_key == "env-provided-key"


# ---------------------------------------------------------------------
# Secrets must never be exposed
# ---------------------------------------------------------------------

def test_api_key_never_appears_in_raised_error_message(monkeypatch):
    secret = "sk-super-secret-value-12345"
    fake_sdk_client = FakeGroqSDKClient()

    def _raise(**kw):
        # Simulate a worst-case leaky exception that embeds the key in its
        # own message -- the client must still scrub it before raising.
        raise RuntimeError(f"request failed, Authorization: Bearer {secret}")

    fake_sdk_client._create_impl = _raise
    monkeypatch.setattr("groq.Groq", lambda api_key=None: fake_sdk_client)

    client = GroqLLMClient(api_key=secret)
    with pytest.raises(LLMUnavailableError) as exc_info:
        client.generate("prompt")

    assert secret not in str(exc_info.value)


def test_missing_key_error_message_contains_no_key_material(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = GroqLLMClient(api_key=None)
    with pytest.raises(LLMUnavailableError) as exc_info:
        client.generate("prompt")
    # There's no key to leak in this path, but assert the message is the
    # exact, safe, expected string rather than anything provider-internal.
    assert str(exc_info.value) == "GROQ_API_KEY is not set"


# ---------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------

def test_get_llm_client_defaults_to_ollama_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    client = get_llm_client()
    assert isinstance(client, LocalLLMClient)
    assert client.provider_name == "ollama"


def test_get_llm_client_selects_groq(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    client = get_llm_client()
    assert isinstance(client, GroqLLMClient)
    assert client.provider_name == "groq"


def test_get_llm_client_selects_ollama_explicitly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    client = get_llm_client()
    assert isinstance(client, LocalLLMClient)


def test_get_llm_client_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "GROQ")
    client = get_llm_client()
    assert isinstance(client, GroqLLMClient)


def test_get_llm_client_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "some-other-provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_client()
