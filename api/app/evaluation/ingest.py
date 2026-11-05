"""Register recordings from data/audio/ as test-set calls. The calls are created queued; transcribing them spends
Gnani credits, which the CLI confirms first."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, load_yaml
from app.evaluation.keys import AUDIO_DIR, SCRIPTS_DIR, AnswerKey
from app.models import Agent, Call
from app.services import audio
from app.storage.base import AudioStorage

IST = ZoneInfo("Asia/Kolkata")
AUDIO_SUFFIXES = (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".amr", ".mp4")
HEADER = re.compile(r"\[Agent:\s*(?P<agent>[^|\]]+?)\s*\|.*?Loan:\s*(?P<loan>[^|\]]+?)\s*\|")


def find_audio(test_key: str, directory: Path = AUDIO_DIR) -> Path | None:
    for suffix in AUDIO_SUFFIXES:
        path = directory / f"{test_key}{suffix}"
        if path.exists():
            return path
    return None


def script_details(test_key: str, directory: Path = SCRIPTS_DIR) -> tuple[str, str]:
    """(agent name, loan reference) from the script's header line."""
    path = directory / f"{test_key}.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    m = HEADER.search(text)
    return (m["agent"], m["loan"]) if m else ("Test agent", f"TEST-{test_key.upper()}")


def _agent(session: Session, name: str) -> Agent:
    found = next((a for a in session.scalars(select(Agent)) if a.name.lower() == name.lower()), None)
    if found:
        return found
    agent = Agent(name=name, team=load_yaml("workspace.yaml")["default_agent_team"])
    session.add(agent)
    session.flush()
    return agent


def ingest(
    session: Session,
    storage: AudioStorage,
    settings: Settings,
    keys: list[AnswerKey],
    only: set[str] | None = None,
    audio_dir: Path = AUDIO_DIR,
    scripts_dir: Path = SCRIPTS_DIR,
    now: datetime | None = None,
) -> tuple[list[Call], list[str]]:
    """Returns (calls created or already present, notes). Existing test calls are left alone."""
    notes: list[str] = []
    calls: list[Call] = []
    yesterday = (now or datetime.now(IST)).astimezone(IST).date() - timedelta(days=1)
    for key in keys:
        if only and key.test_key not in only:
            continue
        existing = session.scalars(select(Call).where(Call.test_key == key.test_key)).first()
        if existing:
            calls.append(existing)
            continue
        path = find_audio(key.test_key, audio_dir)
        if path is None:
            notes.append(f"{key.test_key}: no recording in {audio_dir}")
            continue
        try:
            info = audio.validate_upload(
                path, path.name, max_mb=settings.max_upload_mb, max_call_minutes=settings.max_call_minutes
            )
        except audio.AudioError as e:
            notes.append(f"{key.test_key}: {e.message}")
            continue
        agent_name, loan = script_details(key.test_key, scripts_dir)
        hh, mm = (int(x) for x in key.called_time_ist.split(":"))
        call_id = uuid.uuid4()
        call = Call(
            id=call_id,
            agent_id=_agent(session, agent_name).id,
            loan_ref=loan,
            called_at=datetime(yesterday.year, yesterday.month, yesterday.day, hh, mm, tzinfo=IST),
            borrower_requested_time=key.borrower_requested_time,
            duration_s=info.duration_s,
            language=key.language,
            audio_path=storage.save(str(call_id), path, path.name),
            status="queued",
            test_key=key.test_key,
            is_test_set=True,
        )
        session.add(call)
        calls.append(call)
    session.commit()
    return calls, notes
