"""Token-aware rate limiter (plan.md Section 6.5): LLM_RPM_LIMIT requests and LLM_TPM_LIMIT tokens per minute.

Tokens are estimated from characters before a request (Devanagari is token-heavy) and corrected with the provider's
reported usage afterwards.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

WINDOW_S = 60.0
CHARS_PER_TOKEN_LATIN = 3.5
CHARS_PER_TOKEN_DEVANAGARI = 1.5  # conservative; the real ratio is measured in the Phase 2 smoke test


def estimate_tokens(text: str) -> int:
    dev = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    other = len(text) - dev
    return int(dev / CHARS_PER_TOKEN_DEVANAGARI + other / CHARS_PER_TOKEN_LATIN) + 1


class TokenLimiter:
    def __init__(
        self,
        rpm: int,
        tpm: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.rpm, self.tpm = rpm, tpm
        self._clock, self._sleep = clock, sleep
        self._events: deque[list[float]] = deque()  # [timestamp, tokens]; tokens is corrected by record()

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= WINDOW_S:
            self._events.popleft()

    def wait_time(self, tokens: int) -> float:
        """Seconds to wait before a request of `tokens` fits in both budgets (0 if it fits now)."""
        now = self._clock()
        self._prune(now)
        wait = 0.0
        if len(self._events) >= self.rpm:
            wait = max(wait, self._events[len(self._events) - self.rpm][0] + WINDOW_S - now)
        used = sum(e[1] for e in self._events)
        if used + tokens > self.tpm and self._events:
            # An oversized request that could never fit still goes through once the window is empty.
            running, need = used, used + tokens - self.tpm
            for ts, tk in self._events:
                running -= tk
                need -= tk
                if need <= 0:
                    wait = max(wait, ts + WINDOW_S - now)
                    break
            else:
                wait = max(wait, self._events[-1][0] + WINDOW_S - now)
        return max(wait, 0.0)

    def acquire(self, tokens: int) -> list[float]:
        """Block until the request fits, then reserve it. Returns the entry so record() can correct it."""
        while (w := self.wait_time(tokens)) > 0:
            self._sleep(w)
        entry = [self._clock(), float(tokens)]
        self._events.append(entry)
        return entry

    @staticmethod
    def record(entry: list[float], actual_tokens: int | None) -> None:
        if actual_tokens is not None:
            entry[1] = float(actual_tokens)
