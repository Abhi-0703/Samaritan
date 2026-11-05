from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.storage.base import AudioStorage
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> AudioStorage:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_audio_dir)
    raise RuntimeError("The Supabase storage backend is added in Phase 3.")
