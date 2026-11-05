"""A fake Gnani Batch STT service for tests. No test ever touches the real API (plan.md Section 12, step 2.2).

It speaks the documented shapes (create 201, start 202, status, files with a pre-signed URL, transcript JSON) and has
switches for the failure cases: credits, bad key, rate limit, server errors, failed jobs, model-name rejection.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser

import httpx

TRANSCRIPT_HOST = "gnaniasraudios.s3.amazonaws.com"

DEFAULT_SEGMENTS = [
    (0.0, 4.2, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.4, 6.0, 2, "Haan ji, boliye."),
    (6.2, 12.5, 1, "Sir, aapke personal loan ki EMI pending hai, 5500 rupaye. Kab tak ho payega?"),
    (12.8, 16.0, 2, "Agle hafte tak kar dunga."),
]


@dataclass
class FakeJob:
    job_id: str
    config: dict
    filename: str
    size: int
    started: bool = False
    polls_since_start: int = 0
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class FakeGnani:
    def __init__(self, api_key: str = "test-gnani-key-0000", polls_until_done: int = 2) -> None:
        self.api_key = api_key
        self.polls_until_done = polls_until_done
        self.jobs: dict[str, FakeJob] = {}
        self.transcripts: dict[str, list[tuple[float, float, int, str]]] = {}
        self.requests: list[tuple[str, str]] = []
        self.api_headers: list[httpx.Headers] = []
        self.transcript_request_headers: list[httpx.Headers] = []
        # failure switches
        self.inject: list[int] = []  # HTTP statuses returned for the next requests, in order
        self.job_outcome = "COMPLETED"  # COMPLETED | PARTIAL_FAILURE | FAILED | START_FAILED | CANCELLED
        self.credits_exhausted = False
        self.scope_error = False
        self.accepted_models = {"prisma-v2.5", "prisma-v3.0"}
        self.default_segments = DEFAULT_SEGMENTS
        self.on_request = None  # optional hook: called with (method, path) before each request is handled
        self.job_error_message = "UNSUPPORTED_LANGUAGE: language not supported for this file"

    # -- helpers ------------------------------------------------------------------------------------

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle), follow_redirects=True)

    @staticmethod
    def _json(status: int, body: dict) -> httpx.Response:
        return httpx.Response(status, json=body)

    def _error(self, status: int) -> httpx.Response:
        if status == 401:
            return self._json(
                401, {"detail": {"error_code": "INVALID_API_KEY", "message": "Invalid API key", "status_code": 401}}
            )
        if status == 402:
            return self._json(
                402,
                {"detail": {"error_code": "INSUFFICIENT_CREDIT", "message": "Insufficient credit", "status_code": 402}},
            )
        if status == 403:
            return self._json(
                403,
                {
                    "detail": {
                        "error_code": "SCOPE_NOT_ALLOWED",
                        "message": "Service 'STT' not in allowed scopes",
                        "status_code": 403,
                    }
                },
            )
        if status == 429:
            return self._json(
                429,
                {
                    "detail": {
                        "error_code": "RATE_LIMITED",
                        "message": "Only 1 active request is allowed at a time.",
                        "status_code": 429,
                    }
                },
            )
        return self._json(status, {"error": "INTERNAL_SERVER_ERROR", "message": "boom"})

    @staticmethod
    def _parts(request: httpx.Request) -> dict[str, tuple[str | None, bytes]]:
        ctype = request.headers.get("content-type", "")
        msg = BytesParser(policy=policy.default).parsebytes(f"Content-Type: {ctype}\r\n\r\n".encode() + request.content)
        out: dict[str, tuple[str | None, bytes]] = {}
        for part in msg.iter_parts():
            out[part.get_param("name", header="content-disposition")] = (
                part.get_filename(),
                part.get_payload(decode=True) or b"",
            )
        return out

    # -- the service --------------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append((request.method, path))
        if self.on_request:
            self.on_request(request.method, path)

        if request.url.host == TRANSCRIPT_HOST:  # pre-signed URL: no key needed, and none must be sent
            self.transcript_request_headers.append(request.headers)
            return self._transcript(path)

        self.api_headers.append(request.headers)
        key = request.headers.get("x-api-key-id")
        if not key:
            return self._json(
                401, {"detail": {"error_code": "MISSING_API_KEY", "message": "Missing API key", "status_code": 401}}
            )
        if key != self.api_key:
            return self._error(401)
        if self.credits_exhausted:
            return self._error(402)
        if self.scope_error:
            return self._error(403)
        if self.inject:
            return self._error(self.inject.pop(0))

        if request.method == "POST" and path == "/stt/v3/batch/jobs":
            return self._create(request)
        if (m := re.fullmatch(r"/stt/v3/batch/jobs/([^/]+)/start", path)) and request.method == "POST":
            return self._start(m.group(1))
        if (m := re.fullmatch(r"/stt/v3/batch/jobs/([^/]+)/files", path)) and request.method == "GET":
            return self._files(m.group(1), request.url.params.get("status"))
        if (m := re.fullmatch(r"/stt/v3/batch/jobs/([^/]+)", path)) and request.method == "GET":
            return self._status(m.group(1))
        if request.method == "GET" and path == "/stt/v3/batch/jobs":
            return self._json(200, {"data": [], "pagination": {"has_more": False, "next_cursor": None}})
        return self._json(404, {"error": "NOT_FOUND", "message": f"No route {path}"})

    def _create(self, request: httpx.Request) -> httpx.Response:
        parts = self._parts(request)
        if "config" not in parts:
            return self._json(400, {"error": "INVALID_CONFIG", "message": "config is required"})
        try:
            config = json.loads(parts["config"][1])
        except ValueError:
            return self._json(500, {"error": "INTERNAL_SERVER_ERROR", "message": "Internal Server Error"})
        if "files" not in parts:
            return self._json(400, {"error": "NO_FILES_PROVIDED", "message": "No files provided"})
        filename, data = parts["files"]
        if len(data) > 10 * 1024 * 1024:
            return self._json(400, {"error": "FILE_TOO_LARGE", "message": "File exceeds 10 MB"})
        if not (filename or "").lower().endswith((".wav", ".flac", ".mp3", ".m4a", ".ogg")):
            return self._json(400, {"error": "INVALID_CONFIG", "message": "Unsupported file extension"})
        model = str(config.get("model", ""))
        if model.lower() not in self.accepted_models:
            return self._json(400, {"error": "INVALID_CONFIG", "message": f"Invalid model '{model}'"})
        if "format" in config and model.lower() == "prisma-v2.5":
            return self._json(400, {"error": "INVALID_CONFIG", "message": "format is only supported with prisma-v3.0"})
        if "language_code" not in config:
            return self._json(400, {"error": "UNSUPPORTED_LANGUAGE", "message": "language_code is required"})
        job = FakeJob(str(uuid.uuid4()), config, filename or "audio.wav", len(data))
        self.jobs[job.job_id] = job
        return self._json(
            201,
            {
                "job_id": job.job_id,
                "status": "CREATED",
                "total_files_accepted": 1,
                "created_at": "2026-11-05T10:00:00Z",
                "message": f"1 file(s) uploaded. Call POST /v1/jobs/{job.job_id}/start to begin processing.",
            },
        )

    def _start(self, job_id: str) -> httpx.Response:
        job = self.jobs.get(job_id)
        if not job:
            return self._json(404, {"error": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"})
        if job.started:
            return self._json(
                409, {"error": "JOB_ALREADY_STARTED", "message": "Job cannot be restarted from state 'IN_PROGRESS'"}
            )
        job.started = True
        return self._json(202, {"job_id": job_id, "status": "STARTING", "message": "Job start accepted."})

    def _current_status(self, job: FakeJob) -> str:
        if not job.started:
            return "CREATED"
        job.polls_since_start += 1
        if job.polls_since_start == 1:
            return "STARTING"
        if job.polls_since_start <= self.polls_until_done:
            return "IN_PROGRESS"
        return self.job_outcome

    def _status(self, job_id: str) -> httpx.Response:
        job = self.jobs.get(job_id)
        if not job:
            return self._json(404, {"error": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"})
        status = self._current_status(job)
        return self._json(
            200,
            {
                "job_id": job_id,
                "status": status,
                "config": job.config,
                "progress": {
                    "total_files": 1,
                    "completed_files": int(status == "COMPLETED"),
                    "failed_files": int(status in ("FAILED", "PARTIAL_FAILURE")),
                    "in_progress_files": 0,
                    "queued_files": 0,
                    "cancelled_files": 0,
                },
                "cancel_reason": "Insufficient audio" if status in ("START_FAILED", "CANCELLED") else None,
                "created_at": "2026-11-05T10:00:00Z",
                "started_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "updated_at": "2026-11-05T10:00:05Z",
            },
        )

    def _files(self, job_id: str, status_filter: str | None) -> httpx.Response:
        job = self.jobs.get(job_id)
        if not job:
            return self._json(404, {"error": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"})
        ok = self.job_outcome in ("COMPLETED", "PARTIAL_FAILURE")
        entry = {
            "file_id": job.file_id,
            "original_path": job.filename,
            "status": "COMPLETED" if ok else "FAILED",
            "duration_seconds": "16.0",
            "transcript_url": f"https://{TRANSCRIPT_HOST}/results/{job.file_id}.json?X-Amz-Expires=3600"
            if ok
            else None,
            "error_message": None if ok else self.job_error_message,
            "created_at": "2026-11-05T10:00:00Z",
            "completed_at": "2026-11-05T10:00:20Z",
        }
        data = [entry] if status_filter in (None, entry["status"]) else []
        return self._json(
            200,
            {
                "job_id": job_id,
                "data": data,
                "pagination": {"has_more": False, "next_cursor": None, "total_count": len(data)},
            },
        )

    def _transcript(self, path: str) -> httpx.Response:
        file_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        job = next((j for j in self.jobs.values() if j.file_id == file_id), None)
        if not job:
            return httpx.Response(403, text="expired")
        segs = self.transcripts.get(job.filename, self.default_segments)
        return self._json(
            200,
            {
                "file_id": file_id,
                "job_id": job.job_id,
                "original_path": job.filename,
                "language_code": job.config.get("language_code", "hi-IN"),
                "duration_seconds": segs[-1][1] + 1.0,
                "model": "gnani-prisma-v3.0",
                "mode": "transcribe",
                "segments": [
                    {"segment_id": i, "start_time": s, "end_time": e, "text": t, "speaker_id": sp}
                    for i, (s, e, sp, t) in enumerate(segs)
                ],
                "full_transcript": " ".join(t for *_, t in segs),
                "created_at": "2026-11-05T10:00:20Z",
            },
        )
