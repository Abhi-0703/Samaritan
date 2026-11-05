"""The processing pipeline for one call (plan.md Section 6.6).

queued -> transcribing -> analysing -> done (or failed). Order after transcription: speaker roles -> PII masking ->
Layer 1 -> Layer 2 -> merge -> score -> save. Idempotent: a cached transcript skips Gnani, and a saved job id is resumed
instead of creating (and paying for) a second job.
"""

from __future__ import annotations

import logging
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.detection.llm_judge import PROMPT_VERSION, judge_call
from app.detection.masking import mask_pii
from app.detection.merge import merge_flags
from app.detection.roles import RoleMapping, map_roles
from app.detection.rules_engine import run_layer1
from app.detection.types import DSegment
from app.models import Call, Segment, Violation
from app.services import audio
from app.services.gnani_client import GnaniBatchClient, GnaniError, build_config, parse_transcript
from app.services.llm.service import LLMService
from app.services.queries import enabled_codes, recompute_call_score
from app.storage.base import AudioStorage

log = logging.getLogger("pipeline")


class QueueHalt(Exception):
    """A fatal Gnani error (credits, key, scope): no call can succeed, so the worker stops taking calls."""


def _now() -> datetime:
    return datetime.now(UTC)


def _set_status(session: Session, call: Call, status: str) -> None:
    call.status = status
    session.commit()  # committed straight away so the web app's polling sees progress


def fail_call(session: Session, call: Call, message: str) -> None:
    call.status = "failed"
    call.error = message[:500]
    session.commit()


# ---- stage 1: transcription --------------------------------------------------------------------------------------


def transcribe_call(
    session: Session, call: Call, gnani: GnaniBatchClient, storage: AudioStorage, settings: Settings
) -> None:
    _set_status(session, call, "transcribing")
    src = storage.local_path(call.audio_path)
    config = build_config(call.language, settings)

    def on_job_created(job_id: str, sent: dict) -> None:
        call.gnani_job_id = job_id  # saved immediately: a restart resumes this job instead of paying twice
        call.transcription_config = sent
        session.commit()

    with tempfile.TemporaryDirectory() as tmp:
        prepared = audio.prepare_for_gnani(src, Path(tmp), str(call.id))
        transcript, job_id, sent = gnani.transcribe(
            prepared.path, config, job_id=call.gnani_job_id, on_job_created=on_job_created,
            poll_seconds=settings.gnani_poll_seconds,
        )  # fmt: skip
    call.gnani_job_id = job_id
    call.transcription_config = sent
    call.raw_transcript = transcript.raw  # cached server-side only; never returned by the API
    if transcript.duration_s:
        call.duration_s = transcript.duration_s
    session.commit()


# ---- stage 2: analysis (also used by swap-roles and re-analysis) -------------------------------------------------


def _roles_for(call: Call, transcript, override: int | None) -> RoleMapping:
    mapping = map_roles([(s.speaker_id, s.start_s, s.text) for s in transcript.segments])
    ids = sorted({s.speaker_id for s in transcript.segments if s.speaker_id is not None})
    if override is not None and override in ids and len(ids) >= 2:
        return RoleMapping(override, {i: ("agent" if i == override else "borrower") for i in ids}, mapping.scores)
    return mapping


def analyse_call(session: Session, call: Call, llm: LLMService | None) -> None:
    """Re-runnable without touching Gnani. Replaces segments and violations, keeping reviewer decisions."""
    if not call.raw_transcript:
        raise ValueError("The call has no transcript to analyse.")
    started = time.monotonic()
    _set_status(session, call, "analysing")
    transcript = parse_transcript(call.raw_transcript)
    override = (call.analysis_meta or {}).get("agent_speaker_override")
    roles = _roles_for(call, transcript, override)
    call.agent_speaker_id = roles.agent_speaker_id

    dsegs = [
        DSegment(i, roles.label(s.speaker_id), s.start_s, s.end_s, mask_pii(s.text).text)  # type: ignore[arg-type]
        for i, s in enumerate(transcript.segments)
    ]  # masked before anything is stored or sent to an LLM
    enabled = enabled_codes(session)
    layer1 = run_layer1(dsegs, call.language, call.called_at, call.borrower_requested_time, enabled)

    judge = None
    session.commit()  # no write transaction may stay open across the LLM call: the cache writes through its own session
    if llm is not None:
        judge = judge_call(llm, dsegs, call.language, layer1.candidates, enabled)
    flags = merge_flags(dsegs, layer1, judge, call.called_at, enabled)

    # keep earlier reviewer decisions for the same rule at the same segment
    old_segments = {s.id: s.idx for s in call.segments}
    decisions = {
        (v.rule_code, old_segments.get(v.segment_id) if v.segment_id else None): v.reviewer_status
        for v in call.violations
        if v.reviewer_status != "open"
    }
    session.execute(delete(Violation).where(Violation.call_id == call.id))
    session.execute(delete(Segment).where(Segment.call_id == call.id))
    session.flush()
    session.expire(call, ["segments", "violations"])

    rows: dict[int, Segment] = {}
    for d in dsegs:
        rows[d.index] = Segment(id=uuid.uuid4(), call_id=call.id, idx=d.index, speaker=d.speaker, start_s=d.start_s,
                                end_s=d.end_s, text=d.text)  # fmt: skip
        session.add(rows[d.index])
    session.flush()
    for f in flags:
        seg = rows.get(f.segment_index) if f.segment_index is not None else None
        session.add(
            Violation(
                id=uuid.uuid4(), call_id=call.id, rule_code=f.rule_code, segment_id=seg.id if seg else None,
                quote=f.quote, start_s=f.start_s, explanation=f.explanation, confidence=f.confidence,
                detected_by=f.detected_by, reviewer_status=decisions.get((f.rule_code, f.segment_index), "open"),
            )
        )  # fmt: skip
    session.flush()
    session.expire(call, ["segments", "violations"])

    llm_ok = bool(judge and judge.ok)
    call.analysis_meta = {
        **{k: v for k, v in (call.analysis_meta or {}).items() if k == "agent_speaker_override"},
        "prompt_version": PROMPT_VERSION,
        "llm_failed": not llm_ok,
        "llm_error": None if llm_ok or judge is None else judge.error,
        "llm_provider_used": judge.provider if judge else None,
        "llm_model": judge.model if judge else None,
        "llm_fallback_used": bool(judge and judge.fallback_used),
        "llm_cached": bool(judge and judge.cached),
        "llm_windows": judge.windows if judge else 0,
        "llm_prompt_tokens": judge.prompt_tokens if judge else 0,
        "llm_completion_tokens": judge.completion_tokens if judge else 0,
        "llm_rejected": len(judge.rejected) if judge else 0,
        "analysis_seconds": round(time.monotonic() - started, 2),
    }
    call.roles_look_correct = judge.roles_look_correct if llm_ok and judge else True
    call.status = "done"
    call.error = None
    call.processed_at = _now()
    session.flush()
    recompute_call_score(session, call)
    session.commit()


# ---- the whole pipeline ------------------------------------------------------------------------------------------


def process_call(
    session: Session,
    call_id: uuid.UUID,
    gnani: GnaniBatchClient,
    llm: LLMService | None,
    storage: AudioStorage,
    settings: Settings,
) -> None:
    """Runs one call to done or failed. Raises QueueHalt on a fatal Gnani error; every other failure marks the call."""
    call = session.get(Call, call_id)
    if call is None:
        return
    try:
        if not call.raw_transcript:
            transcribe_call(session, call, gnani, storage, settings)
        analyse_call(session, call, llm)
    except GnaniError as e:
        session.rollback()
        call = session.get(Call, call_id)
        log.warning("transcription failed: %s", e.code, extra={"call_id": str(call_id)})
        fail_call(session, call, e.user_message)
        if e.fatal:
            raise QueueHalt(e.user_message) from e
    except audio.AudioError as e:
        session.rollback()
        fail_call(session, session.get(Call, call_id), e.message)
    except Exception as e:
        session.rollback()
        log.exception("analysis failed", extra={"call_id": str(call_id)})
        fail_call(session, session.get(Call, call_id), f"Analysis failed: {type(e).__name__}. Retry the call.")


def queued_call_ids(session: Session) -> list[uuid.UUID]:
    rows = session.scalars(
        select(Call).where(Call.status.in_(("queued", "transcribing", "analysing"))).order_by(Call.created_at)
    )
    return [c.id for c in rows]
