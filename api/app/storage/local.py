from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.config import API_DIR


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        root = Path(root)
        self.root = root if root.is_absolute() else (API_DIR / root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, call_id: str, source: Path, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".wav"
        key = f"{call_id}{suffix}"
        shutil.copyfile(source, self.root / key)
        return key

    def local_path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Storage key escapes the audio folder")
        return path

    def url(self, call_id: str, key: str) -> tuple[str, datetime | None]:
        # Served by the API itself; the web app prefixes its own API base URL.
        return f"/calls/{call_id}/audio/file", None

    def delete(self, key: str) -> None:
        self.local_path(key).unlink(missing_ok=True)
