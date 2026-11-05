"""Google Gemini via the google-genai SDK."""

from __future__ import annotations

from typing import Any

from app.services.llm.base import (
    LLMAuthError,
    LLMBadRequest,
    LLMRateLimit,
    LLMResponse,
    LLMTransientError,
)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, *, client: Any | None = None) -> None:
        if not model:
            raise ValueError("GEMINI_MODEL is empty. Set it in api/.env (for example gemini-2.5-flash).")
        self.model = model
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client

    def complete_json(self, system: str, user: str) -> LLMResponse:
        from google.genai import errors, types

        kwargs: dict[str, Any] = {
            "system_instruction": system,
            "temperature": 0,
            "response_mime_type": "application/json",
        }
        if "flash" in self.model:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)  # no hidden reasoning tokens
        try:
            resp = self._client.models.generate_content(
                model=self.model, contents=user, config=types.GenerateContentConfig(**kwargs)
            )
        except errors.APIError as e:
            code = getattr(e, "code", None)
            if code == 429:
                raise LLMRateLimit("Gemini rate limit") from e
            if code in (401, 403):
                raise LLMAuthError(f"Gemini rejected the key (HTTP {code})") from e
            if isinstance(code, int) and code >= 500:
                raise LLMTransientError(f"Gemini server error (HTTP {code})") from e
            raise LLMBadRequest(f"Gemini rejected the request (HTTP {code})") from e
        except (OSError, TimeoutError) as e:
            raise LLMTransientError(f"Gemini connection error ({type(e).__name__})") from e
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            resp.text or "",
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )
