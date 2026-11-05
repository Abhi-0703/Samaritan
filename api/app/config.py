"""Settings, read from api/.env and the process environment. Secrets are SecretStr and never logged."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Gnani
    gnani_api_key: SecretStr = SecretStr("")
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_model: str = "prisma-v3.0"
    gnani_lang_hinglish: str = "hi-IN,en-IN"
    gnani_lang_marathi: str = "mr-IN,en-IN"
    gnani_format: str = "transcribe"
    gnani_with_denoise: bool = False
    gnani_poll_seconds: float = 10.0
    gnani_max_concurrent: int = 1

    # LLM
    llm_provider: Literal["groq", "gemini"] = "groq"
    llm_fallback_provider: Literal["groq", "gemini", ""] = "gemini"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    llm_rpm_limit: int = 30
    llm_tpm_limit: int = 8000
    llm_cache: bool = True

    # Storage and database
    storage_backend: Literal["local", "supabase"] = "local"
    database_url: str = "sqlite:///./local.db"
    local_audio_dir: str = "./.data/audio"
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_bucket: str = "call-audio"

    # Limits and safety
    max_upload_mb: int = 25
    max_call_minutes: int = 8
    demo_mode: bool = False
    upload_passcode: SecretStr = SecretStr("")
    admin_token: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:3000"
    worker_enabled: bool = True  # tests turn the background thread off and drain the queue themselves

    @field_validator("llm_cache", mode="before")
    @classmethod
    def _on_off(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in {"on", "off"}:
            return v.strip().lower() == "on"
        return v

    @field_validator("llm_fallback_provider", mode="before")
    @classmethod
    def _blank_fallback(cls, v: object) -> object:
        return "" if v is None else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def secret_values(self) -> list[str]:
        """Every non-empty secret, so logging can redact them."""
        values = [
            self.gnani_api_key,
            self.groq_api_key,
            self.gemini_api_key,
            self.supabase_service_role_key,
            self.upload_passcode,
            self.admin_token,
        ]
        return [v.get_secret_value() for v in values if v.get_secret_value()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_yaml(name: str) -> dict:
    with (CONFIG_DIR / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
