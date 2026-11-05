"""Gnani Prisma Batch STT client (plan.md Section 7), written against docs.gnani.ai as re-read on 2026-11-05.

One job per call. Flow: create -> start -> poll (no faster than every 10 s) -> list files -> download transcript.
The pre-signed transcript URL needs no API key, so the key header is never sent to it.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger("gnani")

BACKOFF_SECONDS = (0.5, 1.0, 2.0)  # three retries after the first attempt
RETRYABLE_STATUS = {429, 500, 503, 504}
TERMINAL_STATUSES = {"COMPLETED", "PARTIAL_FAILURE", "FAILED", "START_FAILED", "CANCELLED"}
CREDITS_MESSAGE = "Gnani credits exhausted or key not permitted."


class GnaniError(Exception):
    """One error type for the three shapes Gnani uses (batch, auth/rate-limit, validation)."""

    def __init__(
        self, code: str, message: str, http_status: int | None = None, retryable: bool = False, fatal: bool = False
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        # Fatal errors (credits, key, scope) mean no further call can succeed: stop the whole queue.
        self.fatal = fatal

    @property
    def user_message(self) -> str:
        return CREDITS_MESSAGE if self.fatal else self.message


_CREDIT_WORDS = re.compile(r"credit|organi[sz]ation|forbidden|not allowed|scope", re.I)


def parse_error(resp: httpx.Response) -> GnaniError:
    status = resp.status_code
    code, message = f"HTTP_{status}", resp.reason_phrase or "Request failed"
    try:
        body = resp.json()
    except ValueError:
        body = None
        text = resp.text.strip()
        if text:
            message = text[:300]

    if isinstance(body, dict):
        detail = body.get("detail")
        err = body.get("error")
        if isinstance(detail, dict):  # {"detail": {"error_code", "message", "status_code"}}
            code = str(detail.get("error_code") or code)
            message = str(detail.get("message") or message)
        elif isinstance(detail, list):  # 422 validation: {"detail": [...]}
            code = "VALIDATION_ERROR"
            parts = []
            for item in detail[:3]:
                if isinstance(item, dict):
                    loc = ".".join(str(p) for p in item.get("loc", []) if p != "body")
                    parts.append(f"{loc}: {item.get('msg', '')}".strip(": "))
            message = "; ".join(parts) or message
        elif isinstance(err, str):  # batch: {"error": "JOB_NOT_FOUND", "message": "..."}
            code = err
            message = str(body.get("message") or message)
        elif isinstance(err, dict):  # sync STT: {"error": {"type": ..., "message": ...}}
            code = str(err.get("type") or err.get("code") or code)
            message = str(err.get("message") or message)
        elif "message" in body:
            message = str(body["message"])

    fatal = status in (401, 402) or (status == 403 and bool(_CREDIT_WORDS.search(f"{code} {message}")))
    return GnaniError(code, message, status, retryable=status in RETRYABLE_STATUS, fatal=fatal)


@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str
    speaker_id: int | None


@dataclass
class Transcript:
    segments: list[TranscriptSegment]
    duration_s: float | None
    language_code: str | None
    model: str | None
    raw: dict[str, Any] = field(repr=False)


def parse_transcript(raw: dict[str, Any]) -> Transcript:
    """Validate Gnani's transcript JSON. Times are seconds (inferred from the docs; confirmed in the spike)."""
    segs = raw.get("segments")
    if not isinstance(segs, list):
        raise GnaniError("BAD_TRANSCRIPT", "The transcript has no segments list.")
    out: list[TranscriptSegment] = []
    for s in segs:
        text = str(s.get("text") or "").strip()
        if not text:
            continue
        try:
            start, end = float(s["start_time"]), float(s["end_time"])
        except (KeyError, TypeError, ValueError) as e:
            raise GnaniError("BAD_TRANSCRIPT", "A transcript segment has no usable start or end time.") from e
        sid = s.get("speaker_id")
        out.append(TranscriptSegment(start, end, text, int(sid) if sid is not None else None))
    out.sort(key=lambda x: (x.start_s, x.end_s))
    dur = raw.get("duration_seconds")
    return Transcript(
        segments=out,
        duration_s=float(dur) if dur not in (None, "") else None,
        language_code=raw.get("language_code"),
        model=raw.get("model"),
        raw=raw,
    )


@dataclass
class JobStatus:
    job_id: str
    status: str
    progress: dict[str, Any]
    cancel_reason: str | None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass
class FileInfo:
    file_id: str
    original_path: str
    status: str
    duration_seconds: float | None
    transcript_url: str | None
    error_message: str | None


def build_config(language: str, settings: Settings, **overrides: Any) -> dict[str, Any]:
    """The `config` JSON for one call. Chosen by the Phase 2 spike; defaults come from the env vars."""
    model = overrides.pop("model", settings.gnani_model)
    v3 = model.lower().endswith("v3.0")
    if language == "marathi":
        language_code = settings.gnani_lang_marathi if v3 else "mr-IN"
    else:
        language_code = settings.gnani_lang_hinglish if v3 else "en-IN"
    config: dict[str, Any] = {
        "model": model,
        "language_code": language_code,
        "mode": "transcribe",
        "with_diarization": True,
        "num_speakers": 2,  # the API default is 5; two people are on every call
        "is_multi_channel": False,
        "with_denoise": settings.gnani_with_denoise,
    }
    if v3 and settings.gnani_format:
        config["format"] = settings.gnani_format  # v3.0 only: v2.5 answers 400 INVALID_CONFIG
    config.update(overrides)
    return config


class GnaniBatchClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._http = http or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True)
        self._sleep = sleep

    # -- low level ---------------------------------------------------------------------------------

    def _request(self, method: str, path: str, *, timeout: float | None = None, **kwargs: Any) -> httpx.Response:
        url = f"{self._base}{path}"
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            rid = str(uuid.uuid4())
            headers = {"X-API-Key-ID": self._key, "X-API-Request-ID": rid}
            err: GnaniError
            try:
                extra = {"timeout": timeout} if timeout else {}
                resp = self._http.request(method, url, headers=headers, **extra, **kwargs)
            except httpx.TransportError as e:
                err = GnaniError("CONNECTION_ERROR", f"Could not reach Gnani ({type(e).__name__}).", retryable=True)
            else:
                if resp.status_code < 400:
                    log.info(
                        "gnani %s %s -> %s", method, path.split("?")[0], resp.status_code, extra={"request_id": rid}
                    )
                    return resp
                err = parse_error(resp)
            log.warning(
                "gnani %s %s failed: %s (attempt %d)",
                method,
                path.split("?")[0],
                err.code,
                attempt + 1,
                extra={"request_id": rid},
            )
            if not err.retryable or attempt == len(BACKOFF_SECONDS):
                raise err
            self._sleep(BACKOFF_SECONDS[attempt])
        raise AssertionError("unreachable")

    # -- endpoints ---------------------------------------------------------------------------------

    def create_job(self, audio_path: Path, config: dict[str, Any], filename: str | None = None) -> tuple[str, dict]:
        """Returns (job_id, config_actually_sent). Retries once with the `gnani-` model name if Gnani rejects it."""
        name = filename or audio_path.name
        if Path(name).suffix.lower() not in {".wav", ".flac"}:
            raise GnaniError("BAD_FILE_EXTENSION", "Send a .wav or .flac file; the batch API checks the extension.")
        audio = audio_path.read_bytes()  # at most ~10 MB, and reusable across retries
        content_type = "audio/flac" if name.lower().endswith(".flac") else "audio/wav"

        def attempt(cfg: dict[str, Any]) -> httpx.Response:
            files = [
                ("config", (None, json.dumps(cfg), "application/json")),  # always json.dumps: bad JSON is a 500
                ("files", (name, audio, content_type)),
            ]
            return self._request("POST", "/stt/v3/batch/jobs", files=files, timeout=120.0)

        try:
            resp, sent = attempt(config), config
        except GnaniError as e:
            model = str(config.get("model", ""))
            if e.http_status == 400 and model == "prisma-v2.5" and re.search(r"model|config", e.message, re.I):
                sent = {**config, "model": "gnani-prisma-v2.5"}
                log.info("retrying with the gnani- model name form")
                resp = attempt(sent)
            else:
                raise
        job_id = resp.json().get("job_id")
        if not job_id:
            raise GnaniError("BAD_RESPONSE", "Gnani did not return a job id.")
        return str(job_id), sent

    def start_job(self, job_id: str) -> str:
        try:
            return str(self._request("POST", f"/stt/v3/batch/jobs/{job_id}/start").json().get("status", "STARTING"))
        except GnaniError as e:
            if e.code == "JOB_ALREADY_STARTED":  # a resumed job that was started before the restart
                return "STARTING"
            raise

    def get_job(self, job_id: str) -> JobStatus:
        d = self._request("GET", f"/stt/v3/batch/jobs/{job_id}").json()
        return JobStatus(
            str(d.get("job_id", job_id)), str(d.get("status", "")), d.get("progress") or {}, d.get("cancel_reason")
        )

    def list_files(self, job_id: str, status: str | None = None) -> list[FileInfo]:
        files: list[FileInfo] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 100}
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            d = self._request("GET", f"/stt/v3/batch/jobs/{job_id}/files", params=params).json()
            for f in d.get("data", []):
                dur = f.get("duration_seconds")
                files.append(
                    FileInfo(
                        str(f.get("file_id", "")),
                        str(f.get("original_path", "")),
                        str(f.get("status", "")),
                        float(dur) if dur not in (None, "") else None,
                        f.get("transcript_url"),
                        f.get("error_message"),
                    )
                )
            page = d.get("pagination") or {}
            cursor = page.get("next_cursor")
            if not page.get("has_more") or not cursor:
                return files

    def download_transcript(self, url: str) -> dict[str, Any]:
        """The URL is pre-signed and needs no API key, so none is sent."""
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            try:
                resp = self._http.get(url)
                if resp.status_code < 400:
                    return resp.json()
                err = GnaniError(
                    f"TRANSCRIPT_HTTP_{resp.status_code}",
                    "Could not download the transcript.",
                    resp.status_code,
                    retryable=resp.status_code in RETRYABLE_STATUS,
                )
            except httpx.TransportError as e:
                err = GnaniError(
                    "CONNECTION_ERROR", f"Could not download the transcript ({type(e).__name__}).", retryable=True
                )
            except ValueError as e:
                raise GnaniError("BAD_TRANSCRIPT", "The transcript file is not valid JSON.") from e
            if not err.retryable or attempt == len(BACKOFF_SECONDS):
                raise err
            self._sleep(BACKOFF_SECONDS[attempt])
        raise AssertionError("unreachable")

    # -- whole flow --------------------------------------------------------------------------------

    def wait_for_job(
        self,
        job_id: str,
        *,
        poll_seconds: float = 10.0,
        timeout_s: float = 1800.0,
        on_status: Callable[[JobStatus], None] | None = None,
    ) -> JobStatus:
        poll = max(poll_seconds, 10.0)  # the docs ask for no faster than every 10 s
        waited = 0.0
        while True:
            status = self.get_job(job_id)
            if on_status:
                on_status(status)
            if status.terminal:
                return status
            if waited >= timeout_s:
                raise GnaniError("JOB_TIMEOUT", f"Gnani job did not finish within {int(timeout_s)} s.")
            self._sleep(poll)
            waited += poll

    def fetch_result(self, job_id: str, status: JobStatus) -> Transcript:
        if status.status in ("COMPLETED", "PARTIAL_FAILURE"):
            done = [f for f in self.list_files(job_id, status="COMPLETED") if f.transcript_url]
            if done:
                return parse_transcript(self.download_transcript(done[0].transcript_url or ""))
            reason = "; ".join(f.error_message or f.status for f in self.list_files(job_id)) or "no completed file"
            raise GnaniError("JOB_FAILED", f"Gnani finished the job but returned no transcript ({reason}).")
        if status.status == "START_FAILED":
            raise GnaniError("START_FAILED", status.cancel_reason or "Gnani could not start the job.")
        if status.status == "CANCELLED":
            raise GnaniError("JOB_CANCELLED", status.cancel_reason or "The Gnani job was cancelled.")
        reason = "; ".join(f.error_message or "" for f in self.list_files(job_id) if f.error_message)
        raise GnaniError("JOB_FAILED", reason or "Gnani could not transcribe the audio.")

    def transcribe(
        self,
        audio_path: Path,
        config: dict[str, Any],
        *,
        filename: str | None = None,
        job_id: str | None = None,
        on_job_created: Callable[[str, dict[str, Any]], None] | None = None,
        on_status: Callable[[JobStatus], None] | None = None,
        poll_seconds: float = 10.0,
        timeout_s: float = 1800.0,
    ) -> tuple[Transcript, str, dict[str, Any]]:
        """Idempotent: pass `job_id` to resume polling a job that exists. Returns (transcript, job_id, config_sent)."""
        sent = config
        if job_id:
            try:
                current = self.get_job(job_id)
            except GnaniError as e:
                if e.code != "JOB_NOT_FOUND":
                    raise
                job_id = None
            else:
                if current.status == "CREATED":
                    self.start_job(job_id)
        if not job_id:
            job_id, sent = self.create_job(audio_path, config, filename)
            if on_job_created:
                on_job_created(job_id, sent)  # saved immediately so a restart resumes instead of paying twice
            self.start_job(job_id)
        status = self.wait_for_job(job_id, poll_seconds=poll_seconds, timeout_s=timeout_s, on_status=on_status)
        return self.fetch_result(job_id, status), job_id, sent


def client_from_settings(settings: Settings, http: httpx.Client | None = None) -> GnaniBatchClient:
    return GnaniBatchClient(settings.gnani_base_url, settings.gnani_api_key.get_secret_value(), http=http)
