"""LLM response cache, keyed by sha256(provider, model, prompt_version, system, user). Hits cost nothing."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.models import LlmCache


def cache_key(provider: str, model: str, prompt_version: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    for part in (provider, model, prompt_version, system, user):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")  # separator so ("ab","c") and ("a","bc") differ
    return h.hexdigest()


class DbLlmCache:
    def __init__(self, scope: Callable[[], AbstractContextManager[Session]], enabled: bool = True) -> None:
        self._scope = scope
        self.enabled = enabled

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        with self._scope() as session:
            row = session.get(LlmCache, key)
            return row.response if row else None

    def put(self, key: str, response: dict) -> None:
        if not self.enabled:
            return
        with self._scope() as session:
            row = session.get(LlmCache, key)
            if row:
                row.response = response
            else:
                session.add(LlmCache(key=key, response=response))
