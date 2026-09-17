"""
Phase 9, Step 4: minimal LLM abstraction.

    class LLMClient:
        def generate(prompt: str) -> LLMResponse

Only a LocalLLMClient (Ollama) is implemented in this phase, per
instructions not to switch to a hosted provider automatically. A
GroqLLMClient or similar could be added later behind the same
interface without touching src/generation/generator.py or src/agent.py.

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

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "gemma2:9b-instruct-q4_0"
DEFAULT_TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 3


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM backend cannot be reached or errors out.
    Never raised to the customer-facing caller -- src/generation/generator.py
    catches this and falls back to the deterministic template."""


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: dict | None = None


class LLMClient:
    """Abstract interface. Do not instantiate directly."""

    def generate(self, prompt: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> LLMResponse:
        raise NotImplementedError


class LocalLLMClient(LLMClient):
    """Ollama-backed local LLM client. No API key -- purely local HTTP."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = OLLAMA_HOST):
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
