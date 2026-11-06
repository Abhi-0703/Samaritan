from __future__ import annotations

import json
import mimetypes
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.datastructures import UploadFile

from app import schemas
from app.config import Settings, get_settings, load_yaml
from app.db import get_session
from app.detection.rules_engine import IST
from app.errors import ApiError
from app.guards import demo_guard
from app.models import Agent, Call
from app.routers.deps import bad_request, get_runtime, load_call
from app.runtime import Runtime
from app.services import audio
from app.services.pipeline import analyse_call
from app.services.queries import call_detail, call_schema, ist_day, rules_by_code
from app.storage.supabase import StorageError

router = APIRouter()

SORT_KEYS = {"id", "agent_name", "called_at", "duration_s", "language", "status", "score", "violations_count"}
SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1}


# ---- list --------------------------------------------------------------------------------------------------------


@router.get("/calls", response_model=schemas.Paginated[schemas.Call])
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    agent_id: str | None = None,
    language: schemas.Language | None = None,
    status: schemas.CallStatus | None = None,
    severity: schemas.Severity | None = None,
    rule_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "called_at",
    order: Literal["asc", "desc"] = "desc",
    session: Session = Depends(get_session),
) -> schemas.Paginated[schemas.Call]:
    if sort not in SORT_KEYS:
        raise bad_request(f"sort must be one of: {', '.join(sorted(SORT_KEYS))}.")
    rules = rules_by_code(session)
    stmt = select(Call).options(selectinload(Call.violations), selectinload(Call.agent))
    if agent_id:
        try:
            stmt = stmt.where(Call.agent_id == uuid.UUID(agent_id))
        except ValueError:
            return schemas.Paginated(items=[], page=page, page_size=page_size, total=0)
    if language:
        stmt = stmt.where(Call.language == language)
    if status:
        stmt = stmt.where(Call.status == status)
    # The dataset is small, so the remaining filters, sorting and paging run in Python: simple and the same on
    # SQLite and Postgres.
    items = [(c, call_schema(c, rules)) for c in session.scalars(stmt)]
    needle = q.strip().lower() if q else ""

    def keep(c: Call, s: schemas.Call) -> bool:
        if needle and not (
            needle in c.loan_ref.lower() or needle in (c.test_key or "").lower() or str(c.id).startswith(needle)
        ):
            return False
        active = [v for v in c.violations if v.reviewer_status != "dismissed" and rules[v.rule_code].enabled]
        if severity and not any(rules[v.rule_code].severity == severity for v in active):
            return False
        if rule_code and not any(v.rule_code == rule_code for v in active):
            return False
        day = ist_day(c.called_at)
        return not (date_from and day < date_from) and not (date_to and day > date_to)

    items = [(c, s) for c, s in items if keep(c, s)]

    def key(s: schemas.Call):
        return {
            "id": s.id, "agent_name": s.agent_name, "called_at": s.called_at,
            "duration_s": s.duration_s if s.duration_s is not None else -1, "language": s.language,
            "status": s.status, "score": s.score if s.score is not None else -1,
            "violations_count": s.violations_count * 10 + SEVERITY_RANK.get(s.max_severity or "", 0),
        }[sort]  # fmt: skip

    items.sort(key=lambda t: t[1].called_at, reverse=True)  # stable tie-break: newest first
    items.sort(key=lambda t: key(t[1]), reverse=(order == "desc"))
    total = len(items)
    start = (page - 1) * page_size
    return schemas.Paginated(
        items=[s for _, s in items[start : start + page_size]], page=page, page_size=page_size, total=total
    )


# ---- upload ------------------------------------------------------------------------------------------------------


def _parse_called_at(value: str, filename: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise bad_request(
            f"{filename}: called_at must be an ISO 8601 date and time, such as 2026-11-03T11:20:00+05:30."
        ) from e
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)  # a time typed without an offset is read as IST


def _resolve_agent(session: Session, meta: schemas.UploadMetadata, settings: Settings) -> Agent:
    if meta.agent_id:
        try:
            agent = session.get(Agent, uuid.UUID(meta.agent_id))
        except ValueError:
            agent = None
        if agent is None:
            raise ApiError(404, "not_found", f"Agent {meta.agent_id} was not found.")
        return agent
    name = (meta.agent_name or "").strip()
    if not name:
        raise bad_request(f"{meta.filename}: choose an agent or give an agent_name.")
    existing = session.scalars(select(Agent)).all()
    found = next((a for a in existing if a.name.lower() == name.lower()), None)
    if found:
        return found
    agent = Agent(name=name, team=load_yaml("workspace.yaml")["default_agent_team"])
    session.add(agent)
    session.flush()
    return agent


@router.post("/calls/upload", response_model=list[schemas.Call], dependencies=[Depends(demo_guard)])
async def upload_calls(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    runtime: Runtime = Depends(get_runtime),
) -> list[schemas.Call]:
    form = await request.form(max_files=100, max_fields=20)
    uploads = [f for key in ("files", "files[]") for f in form.getlist(key) if isinstance(f, UploadFile)]
    raw_meta = form.get("metadata")
    if not uploads:
        raise bad_request("Attach at least one audio file in the `files` field.")
    if not isinstance(raw_meta, str):
        raise bad_request("Send the `metadata` field: a JSON array with one entry per file, in the same order.")
    try:
        metas = [schemas.UploadMetadata.model_validate(m) for m in json.loads(raw_meta)]
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise bad_request(f"metadata is not valid ({where}): {first['msg']}.") from e
    except (ValueError, TypeError) as e:
        raise bad_request("metadata must be a JSON array with one object per file.") from e
    if len(metas) != len(uploads):
        raise bad_request(f"Got {len(uploads)} file(s) but {len(metas)} metadata entries; they must match.")

    def work() -> list[schemas.Call]:
        with tempfile.TemporaryDirectory() as tmp:
            staged: list[tuple[Path, audio.AudioInfo, schemas.UploadMetadata, str]] = []
            for i, (up, meta) in enumerate(zip(uploads, metas, strict=True)):
                name = up.filename or meta.filename
                path = Path(tmp) / f"{i}{Path(name).suffix.lower()}"
                size = 0
                limit = settings.max_upload_mb * 1024 * 1024
                with path.open("wb") as out:
                    while chunk := up.file.read(1024 * 1024):
                        size += len(chunk)
                        if size > limit:
                            raise ApiError(413, "file_too_large", f"{name} is larger than {settings.max_upload_mb} MB.")
                        out.write(chunk)
                try:
                    info = audio.validate_upload(
                        path, name, max_mb=settings.max_upload_mb, max_call_minutes=settings.max_call_minutes
                    )
                except audio.AudioError as e:
                    raise ApiError(e.status_code, e.code, e.message) from e
                _parse_called_at(meta.called_at, name)  # validate everything before creating anything
                staged.append((path, info, meta, name))

            created: list[Call] = []
            for path, info, meta, name in staged:
                agent = _resolve_agent(session, meta, settings)
                call_id = uuid.uuid4()
                key = runtime.storage.save(str(call_id), path, name)
                call = Call(
                    id=call_id, agent_id=agent.id, loan_ref=meta.loan_ref.strip(),
                    called_at=_parse_called_at(meta.called_at, name),
                    borrower_requested_time=meta.borrower_requested_time,
                    duration_s=info.duration_s, language=meta.language, audio_path=key, status="queued",
                )  # fmt: skip
                session.add(call)
                created.append(call)
            session.commit()
            rules = rules_by_code(session)
            for c in created:
                session.refresh(c)
            return [call_schema(c, rules) for c in created]

    result = await run_in_threadpool(work)
    for c in result:
        runtime.worker.enqueue(uuid.UUID(c.id))
    return result


# ---- one call ----------------------------------------------------------------------------------------------------


@router.get("/calls/{call_id}", response_model=schemas.CallDetail)
def get_call(call_id: str, session: Session = Depends(get_session)) -> schemas.CallDetail:
    return call_detail(session, load_call(session, call_id))


@router.get("/calls/{call_id}/audio", response_model=schemas.AudioUrl)
def get_audio_url(
    call_id: str, request: Request, session: Session = Depends(get_session), runtime: Runtime = Depends(get_runtime)
) -> schemas.AudioUrl:
    call = load_call(session, call_id)
    try:
        url, expires = runtime.storage.url(str(call.id), call.audio_path)
    except StorageError as e:
        raise ApiError(502, "storage_unavailable", "The audio could not be fetched from storage. Try again.") from e
    if url.startswith("/"):
        url = str(request.base_url).rstrip("/") + url
    expires = expires or datetime.now(UTC) + timedelta(hours=1)
    return schemas.AudioUrl(url=url, expires_at=expires.astimezone(IST).isoformat(timespec="seconds"))


@router.get("/calls/{call_id}/audio/file")
def get_audio_file(
    call_id: str, session: Session = Depends(get_session), runtime: Runtime = Depends(get_runtime)
) -> FileResponse:
    call = load_call(session, call_id)
    path = runtime.storage.local_path(call.audio_path)
    if not path.exists():
        raise ApiError(404, "not_found", "The audio file for this call is missing.")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")


@router.post("/calls/{call_id}/retry", response_model=schemas.Call, dependencies=[Depends(demo_guard)])
def retry_call(
    call_id: str,
    retranscribe: bool = False,
    session: Session = Depends(get_session),
    runtime: Runtime = Depends(get_runtime),
) -> schemas.Call:
    """Re-runs analysis, reusing the cached transcript unless `?retranscribe=true` (which spends credits).

    A call that failed mid-transcription keeps its Gnani job id, so the retry resumes that job instead of paying twice.
    """
    call = load_call(session, call_id)
    if call.status in ("queued", "transcribing", "analysing"):
        return call_schema(call, rules_by_code(session))
    if retranscribe:
        call.raw_transcript = None
        call.gnani_job_id = None
    call.status, call.error = "queued", None
    session.commit()
    runtime.worker.resume()
    runtime.worker.enqueue(call.id)
    return call_schema(call, rules_by_code(session))


@router.post("/calls/{call_id}/swap-roles", response_model=schemas.CallDetail, dependencies=[Depends(demo_guard)])
def swap_roles(
    call_id: str, session: Session = Depends(get_session), runtime: Runtime = Depends(get_runtime)
) -> schemas.CallDetail:
    """Swap Agent and Borrower and re-run detection only (no re-transcription)."""
    call = load_call(session, call_id)
    if call.status != "done" or not call.raw_transcript:
        raise bad_request("Roles can only be swapped on a call that has finished processing.", "invalid_state")
    ids = sorted({s["speaker_id"] for s in call.raw_transcript.get("segments", []) if s.get("speaker_id") is not None})
    if len(ids) < 2 or call.agent_speaker_id is None:
        raise bad_request("Roles cannot be swapped: only one speaker was detected on this call.", "invalid_state")
    other = next(i for i in ids if i != call.agent_speaker_id)
    call.analysis_meta = {**(call.analysis_meta or {}), "agent_speaker_override": other}
    session.commit()
    analyse_call(session, call, runtime.llm)
    session.refresh(call)
    return call_detail(session, call)
