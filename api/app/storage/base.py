"""Audio storage interface. Local folder now, Supabase Storage in Phase 3."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol


class AudioStorage(Protocol):
    def save(self, call_id: str, source: Path, filename: str) -> str:
        """Copy the file into storage and return the key kept in calls.audio_path."""

    def local_path(self, key: str) -> Path:
        """A readable file path for the key (downloaded to a temp file by remote backends)."""

    def url(self, call_id: str, key: str) -> tuple[str, datetime | None]:
        """A URL the browser can play, and when it stops working (None if it never does)."""

    def delete(self, key: str) -> None: ...
