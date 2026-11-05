"""Calls an LLM with caching, rate limiting, retries and fallback (plan.md Sections 6.3 and 6.5)."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import ValidationError

from app.services.llm.base import (
    LLMAuthError,
    LLMBadRequest,
    LLMError,
    LLMProvider,
    LLMRateLimit,
    LLMUnavailable,
)
from app.services.llm.cache import DbLlmCache, cache_key
from app.services.llm.limiter import TokenLimiter, estimate_tokens

log = logging.getLogger("llm")

T = TypeVar("T")
BACKOFF_SECONDS = (1.0, 2.0, 4.0)
MAX_FAILURES = 3  # rate-limit or server errors before moving to the fallback
MAX_INVALID_JSON = 2
EXPECTED_OUTPUT_TOKENS = 900  # reserved in the limiter before the real usage is known

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, stripping a markdown code fence or stray prose around it."""
    text = text.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        value = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("The model returned JSON, but not an object.")
    return value


@dataclass
class LLMOutcome(Generic[T]):
    value: T
    provider: str
    model: str
    cached: bool
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    fallback_used: bool = False


class LLMService:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None,
        limiters: dict[str, TokenLimiter],
        cache: DbLlmCache | None,
        prompt_version: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.primary, self.fallback = primary, fallback
        self.limiters, self.cache = limiters, cache
        self.prompt_version = prompt_version
        self._sleep = sleep

    def complete(self, system: str, user: str, validate: Callable[[dict[str, Any]], T]) -> LLMOutcome[T]:
        errors: list[str] = []
        for provider, is_fallback in [(self.primary, False), (self.fallback, True)]:
            if provider is None:
                continue
            outcome = self._try(provider, system, user, validate, errors)
            if outcome:
                outcome.fallback_used = is_fallback
                return outcome
        raise LLMUnavailable("; ".join(errors) or "No LLM provider is configured.")

    def _try(
        self, provider: LLMProvider, system: str, user: str, validate: Callable[[dict[str, Any]], T], errors: list[str]
    ) -> LLMOutcome[T] | None:
        key = cache_key(provider.name, provider.model, self.prompt_version, system, user)
        if self.cache:
            hit = self.cache.get(key)
            if hit is not None:
                try:
                    return LLMOutcome(validate(hit), provider.name, provider.model, cached=True)
                except (ValidationError, ValueError):
                    log.warning("ignoring an invalid cache entry", extra={"event": "llm_cache_invalid"})
        limiter = self.limiters.get(provider.name)
        failures = invalid = 0
        while True:
            entry = limiter.acquire(estimate_tokens(system + user) + EXPECTED_OUTPUT_TOKENS) if limiter else None
            try:
                resp = provider.complete_json(system, user)
            except LLMAuthError as e:
                errors.append(f"{provider.name}: {e}")
                return None
            except LLMBadRequest as e:
                errors.append(f"{provider.name}: {e}")
                return None
            except LLMError as e:
                failures += 1
                errors.append(f"{provider.name}: {type(e).__name__}")
                if failures >= MAX_FAILURES:
                    return None
                wait = e.retry_after if isinstance(e, LLMRateLimit) and e.retry_after else BACKOFF_SECONDS[failures - 1]
                self._sleep(wait)
                continue
            if limiter and entry is not None:
                limiter.record(entry, resp.total_tokens)
            try:
                data = parse_json_object(resp.text)
                value = validate(data)
            except (ValueError, ValidationError):
                invalid += 1
                errors.append(f"{provider.name}: invalid JSON")
                if invalid >= MAX_INVALID_JSON:
                    return None
                continue  # one retry straight away
            if self.cache:
                self.cache.put(key, data)
            return LLMOutcome(value, provider.name, provider.model, False, resp.prompt_tokens, resp.completion_tokens)
