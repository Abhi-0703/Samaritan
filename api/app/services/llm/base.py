"""LLM provider interface (plan.md Section 6.5). One call shape for Groq and Gemini."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """Base class. `retryable` errors are retried with backoff on the same provider."""

    retryable = False


class LLMRateLimit(LLMError):
    retryable = True

    def __init__(self, message: str = "rate limited", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMTransientError(LLMError):
    retryable = True


class LLMAuthError(LLMError):
    """A bad key or no access: this provider cannot work, so move to the fallback straight away."""


class LLMBadRequest(LLMError):
    """The provider rejected the request itself; retrying the same request will not help."""


class LLMUnavailable(Exception):
    """Every configured provider failed. The pipeline then keeps the Layer 1 results and flags the call."""


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class LLMProvider(Protocol):
    name: str  # "groq" | "gemini" | "fake"
    model: str

    def complete_json(self, system: str, user: str) -> LLMResponse:
        """Temperature 0. Ask for JSON; the caller validates and parses `text`."""
