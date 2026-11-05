"""Structured logging that never prints a secret."""

from __future__ import annotations

import json
import logging
import sys

from app.config import Settings


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        # Longest first so a secret that contains another is fully replaced.
        self._secrets = sorted({s for s in secrets if len(s) >= 6}, key=len, reverse=True)

    def _clean(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "[REDACTED]")
        return text

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": self._clean(record.getMessage()),
        }
        for key in ("call_id", "request_id", "job_id", "event"):
            if hasattr(record, key):
                payload[key] = self._clean(str(getattr(record, key)))
        if record.exc_info:
            payload["exc"] = self._clean(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter(settings.secret_values))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # httpx logs full URLs at INFO; keep it quiet so pre-signed transcript URLs are not logged.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
