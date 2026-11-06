from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.storage.base import AudioStorage
from app.storage.local import LocalStorage
from app.storage.supabase import SupabaseStorage


@lru_cache
def get_storage() -> AudioStorage:
    settings = get_settings()
    if settings.storage_backend == "supabase":
        return SupabaseStorage(
            settings.supabase_url, settings.supabase_service_role_key.get_secret_value(), settings.supabase_bucket
        )
    return LocalStorage(settings.local_audio_dir)
