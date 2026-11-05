"""Demo-mode protection for the actions that spend credits (plan.md Section 8.4)."""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import ApiError


class RateLimiter:
    """Sliding window per client. In memory, which is enough for one small instance."""

    def __init__(self, limit: int = 10, window_s: float = 3600.0) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")  # set by Render and Vercel; the first entry is the client
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def demo_guard(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Applied to upload, retry, swap-roles and eval run. A no-op unless DEMO_MODE is on."""
    if not settings.demo_mode:
        return
    expected = settings.upload_passcode.get_secret_value()
    given = request.headers.get("x-upload-passcode", "")
    if not expected or not secrets.compare_digest(given.encode(), expected.encode()):
        raise ApiError(403, "forbidden", "The passcode is missing or incorrect.")
    limiter: RateLimiter = request.app.state.rate_limiter
    if not limiter.check(client_ip(request)):
        raise ApiError(429, "rate_limited", "Too many requests from this address. Try again later.")
