"""
Phase 9, Step 4 (+ Phase 14: Groq provider migration): minimal LLM
abstraction.

    class LLMClient:
        def generate(prompt: str) -> LLMResponse

Two concrete providers are implemented behind this same interface:
LocalLLMClient (Ollama) and GroqLLMClient (hosted, via the official
`groq` SDK). src/generation/generator.py and src/agent.py's
orchestration logic did not change to support this -- get_llm_client()
below is the only new thing agent.py depends on, and it just picks
which concrete LLMClient to hand to the existing Generator.

Ollama status (recorded, not re-debugged): the local
`gemma2:9b-instruct-q4_0` model has flipped between working and
failing across Phases 7D, 7E, 9, and now 10 with the same
`llama runner process has terminated` error. Observed directly at the
start of Phase 10: a cold call failed, and an identical call retried a
few seconds later succeeded -- consistent with a transient crash on
model (re)load rather than a permanent outage. Per instructions ("Do
NOT spend significant time debugging Ollama... If it fails again,
record the failure clearly"), this client makes ONE bounded retry
(single retry, short fixed delay) purely to absorb that observed
cold-start flakiness -- not a debugging effort, not a retry loop, and
not a change in behavior once the model is actually down (two
consecutive failures still raise LLMUnavailableError immediately, and
the caller, src/generation/generator.py, is responsible for falling
back safely from there).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

try:
    # Optional: picks up GROQ_API_KEY / LLM_PROVIDER / GROQ_MODEL from a
    # local .env file if one exists (python-dotenv is already a hard
    # requirement -- see requirements.txt). Never overrides an env var
    # that's already set by the real shell/deployment environment.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover -- degrade gracefully if absent
    pass

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = "gemma2:9b-instruct-q4_0"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 3


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM backend cannot be reached or errors out.
    Never raised to the customer-facing caller -- src/generation/generator.py
    catches this and falls back to the deterministic template. Messages
    raised as this error must never contain a raw API key (see
    GroqLLMClient's _safe_error_message)."""


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: dict | None = None


class LLMClient:
    """Abstract interface. Do not instantiate directly."""

    provider_name: str = "unknown"

    def generate(self, prompt: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> LLMResponse:
        raise NotImplementedError


class LocalLLMClient(LLMClient):
    """Ollama-backed local LLM client. No API key -- purely local HTTP."""

    provider_name = "ollama"

    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.host = host

    def generate(self, prompt: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> LLMResponse:
        last_error: Exception | None = None
        for attempt in range(2):  # one real attempt + one bounded retry
            try:
                return self._generate_once(prompt, timeout)
            except LLMUnavailableError as e:
                last_error = e
                if attempt == 0:
                    time.sleep(RETRY_DELAY_SECONDS)
        raise last_error

    def _generate_once(self, prompt: str, timeout: float) -> LLMResponse:
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=timeout,
            )
        except requests.RequestException as e:
            raise LLMUnavailableError(f"Could not reach Ollama at {self.host}: {e}") from e

        try:
            data = resp.json()
        except ValueError as e:
            raise LLMUnavailableError(f"Ollama returned non-JSON response: {resp.text[:200]}") from e

        if "error" in data:
            raise LLMUnavailableError(f"Ollama error: {data['error']}")

        text = data.get("response")
        if not text:
            raise LLMUnavailableError(f"Ollama returned no 'response' field: {data}")

        return LLMResponse(text=text, model=self.model, raw=data)


class GroqLLMClient(LLMClient):
    """Groq-hosted LLM client, via the official `groq` SDK (OpenAI-compatible
    chat-completions API). Reads GROQ_API_KEY / GROQ_MODEL from the
    environment by default -- never accepts a real key as a hard-coded
    default, never logs the key, and never lets it appear in a raised
    LLMUnavailableError message (see _safe_error_message)."""

    provider_name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self._client = None  # built lazily -- constructing GroqLLMClient with no key must not crash

    def _safe_error_message(self, prefix: str, exc: Exception) -> str:
        """Renders an error message for an LLMUnavailableError, scrubbing
        any occurrence of the raw API key first. Groq SDK exceptions
        don't normally embed the key (it's sent as an Authorization
        header, not echoed back), but this is a hard safety net against
        ever leaking it into a UI warning or a log line regardless."""
        text = f"{prefix}: {exc}"
        if self.api_key:
            text = text.replace(self.api_key, "***REDACTED***")
        return text

    def _get_client(self):
        if self._client is None:
            from groq import Groq  # imported lazily so `groq` stays optional for Ollama-only use

            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> LLMResponse:
        if not self.api_key:
            raise LLMUnavailableError("GROQ_API_KEY is not set")

        from groq import GroqError

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
        except GroqError as e:
            raise LLMUnavailableError(self._safe_error_message("Groq API error", e)) from e
        except Exception as e:  # noqa: BLE001 -- any other transport-level failure (DNS, TLS, etc.)
            raise LLMUnavailableError(self._safe_error_message("Could not reach Groq", e)) from e

        text = None
        if response.choices:
            text = response.choices[0].message.content
        if not text:
            raise LLMUnavailableError("Groq returned no content")

        # raw is intentionally None (not the SDK response object) -- keeps
        # LLMResponse.raw's contract simple and avoids ever holding a
        # reference to the full request/response object longer than needed.
        return LLMResponse(text=text, model=self.model, raw=None)


def get_llm_client() -> LLMClient:
    """Provider-selection factory: reads LLM_PROVIDER from the
    environment ('groq' or 'ollama', case-insensitive). Defaults to
    'ollama' when LLM_PROVIDER is unset, preserving this project's
    original behavior for anyone who hasn't opted into Groq. This is the
    only thing src/agent.py depends on to pick a provider -- adding a
    third provider later means adding one more branch here, not touching
    SupportAgent's constructor."""
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "groq":
        return GroqLLMClient()
    if provider == "ollama":
        return LocalLLMClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'groq' or 'ollama')")
