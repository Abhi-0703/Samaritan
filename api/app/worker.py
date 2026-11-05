"""In-process worker: one call at a time, so Gnani sees a single active request (plan.md Section 6.6).

A failing call never stops the queue. A fatal Gnani error (credits, key, scope) pauses it, because no call could
succeed; the calls stay queued and a retry resumes the worker. On start-up, unfinished calls are re-enqueued, since
free hosting tiers sleep and restart.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.services.pipeline import QueueHalt, queued_call_ids

log = logging.getLogger("worker")

ProcessFn = Callable[[Session, uuid.UUID], None]


class Worker:
    def __init__(self, session_factory: Callable[[], Session], process: ProcessFn) -> None:
        self._session_factory = session_factory
        self._process = process
        self._queue: queue.Queue[uuid.UUID] = queue.Queue()
        self._queued: set[uuid.UUID] = set()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.paused = False
        self.pause_reason: str | None = None

    # -- queue ---------------------------------------------------------------------------------------------------

    def enqueue(self, call_id: uuid.UUID) -> bool:
        with self._lock:
            if call_id in self._queued:
                return False
            self._queued.add(call_id)
        self._queue.put(call_id)
        return True

    def resume(self) -> None:
        """Called when the user retries a call after fixing credits or the key."""
        self.paused, self.pause_reason = False, None

    def resume_unfinished(self) -> int:
        """Start-up recovery: re-enqueue calls left in queued, transcribing or analysing."""
        with self._session_factory() as session:
            ids = queued_call_ids(session)
        return sum(self.enqueue(i) for i in ids)

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    # -- running -------------------------------------------------------------------------------------------------

    def run_one(self, call_id: uuid.UUID) -> None:
        with self._lock:
            self._queued.discard(call_id)
        try:
            with self._session_factory() as session:
                self._process(session, call_id)
        except QueueHalt as e:
            self.paused, self.pause_reason = True, str(e)
            log.error("queue paused: %s", e)
        except Exception:  # a failing call must never stop the queue
            log.exception("unexpected error while processing a call", extra={"call_id": str(call_id)})

    def drain(self) -> int:
        """Process everything queued on the calling thread. Used by tests and one-off scripts."""
        done = 0
        while not self.paused:
            try:
                call_id = self._queue.get_nowait()
            except queue.Empty:
                break
            self.run_one(call_id)
            done += 1
        return done

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self.paused:
                self._stop.wait(1.0)
                continue
            try:
                call_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self.run_one(call_id)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="call-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
