from __future__ import annotations

from app.config import Settings
from app.db import session_scope
from app.services.llm.base import LLMProvider
from app.services.llm.cache import DbLlmCache
from app.services.llm.limiter import TokenLimiter
from app.services.llm.service import LLMService

# The env limits describe the primary provider (Groq's free tier). The fallback gets Gemini free-tier-sized defaults.
FALLBACK_RPM, FALLBACK_TPM = 10, 200_000


def make_provider(name: str, settings: Settings) -> LLMProvider:
    if name == "groq":
        from app.services.llm.groq import GroqProvider

        return GroqProvider(settings.groq_api_key.get_secret_value(), settings.groq_model)
    if name == "gemini":
        from app.services.llm.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
    raise ValueError(f"Unknown LLM provider {name!r}")


def build_llm_service(settings: Settings, prompt_version: str) -> LLMService:
    primary = make_provider(settings.llm_provider, settings)
    fallback_name = settings.llm_fallback_provider
    fallback = (
        make_provider(fallback_name, settings) if fallback_name and fallback_name != settings.llm_provider else None
    )
    limiters = {primary.name: TokenLimiter(settings.llm_rpm_limit, settings.llm_tpm_limit)}
    if fallback:
        limiters[fallback.name] = TokenLimiter(FALLBACK_RPM, FALLBACK_TPM)
    return LLMService(primary, fallback, limiters, DbLlmCache(session_scope, settings.llm_cache), prompt_version)
