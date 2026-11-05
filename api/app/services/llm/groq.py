"""Groq via its OpenAI-compatible chat completions endpoint."""

from __future__ import annotations

import contextlib
import re

import httpx

from app.services.llm.base import (
    LLMAuthError,
    LLMBadRequest,
    LLMRateLimit,
    LLMResponse,
    LLMTransientError,
)

URL = "https://api.groq.com/openai/v1/chat/completions"


def _retry_after(resp: httpx.Response) -> float | None:
    header = resp.headers.get("retry-after")
    try:
        return float(header) if header else None
    except ValueError:
        return None


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str, *, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self._key = api_key
        self.model = model
        self._http = http or httpx.Client(timeout=timeout)
        # Optional parameters Groq may reject for a given model; each is dropped once if the API says so.
        # reasoning_effort=low keeps gpt-oss from spending most of its tokens on hidden reasoning (measured in Phase 2).
        self._optional: dict[str, object] = {"response_format": {"type": "json_object"}, "reasoning_effort": "low"}

    def _payload(self, system: str, user: str) -> dict:
        return {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            **self._optional,
        }

    def complete_json(self, system: str, user: str) -> LLMResponse:
        for _ in range(len(self._optional) + 1):
            try:
                resp = self._http.post(
                    URL, headers={"Authorization": f"Bearer {self._key}"}, json=self._payload(system, user)
                )
            except httpx.TransportError as e:
                raise LLMTransientError(f"Groq connection error ({type(e).__name__})") from e
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage") or {}
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
                return LLMResponse(content, usage.get("prompt_tokens"), usage.get("completion_tokens"))
            if resp.status_code == 429:
                raise LLMRateLimit("Groq rate limit", _retry_after(resp))
            if resp.status_code in (401, 403):
                raise LLMAuthError(f"Groq rejected the key (HTTP {resp.status_code})")
            if resp.status_code >= 500:
                raise LLMTransientError(f"Groq server error (HTTP {resp.status_code})")
            message = ""
            with contextlib.suppress(ValueError):
                message = str(resp.json().get("error", {}).get("message", ""))
            dropped = next((k for k in self._optional if re.search(k.replace("_", "[ _]"), message, re.I)), None)
            if resp.status_code == 400 and dropped:
                del self._optional[dropped]  # the model does not support this option: carry on without it
                continue
            raise LLMBadRequest(f"Groq rejected the request (HTTP {resp.status_code}): {message[:200]}")
        raise LLMBadRequest("Groq rejected the request.")
