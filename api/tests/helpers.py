from __future__ import annotations

import struct
import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Agent, Call, Segment, Violation
from app.services.queries import recompute_call_score

IST = timezone(timedelta(hours=5, minutes=30))


def make_wav(path: Path, seconds: float = 5.0, rate: int = 16000) -> Path:
    """A real, valid WAV (a quiet tone) so ffprobe and ffmpeg accept it."""
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", 3000 if (i // 40) % 2 else -3000) for i in range(n)))
    return path


def make_agent(session: Session, name: str = "Rohit Patil", team: str = "Collections") -> Agent:
    agent = Agent(name=name, team=team)
    session.add(agent)
    session.commit()
    return agent


def make_call(
    session: Session,
    agent: Agent,
    *,
    status: str = "done",
    called_at: datetime | None = None,
    language: str = "hinglish",
    loan_ref: str = "SF-PL-100001",
    violations: list[tuple[str, str]] | None = None,  # (rule_code, reviewer_status)
    test_key: str | None = None,
    duration_s: float = 100.0,
) -> Call:
    """A call in the database without running the pipeline: segments and violations are written directly."""
    call = Call(
        id=uuid.uuid4(), agent_id=agent.id, loan_ref=loan_ref,
        called_at=called_at or datetime(2026, 11, 3, 11, 0, tzinfo=IST),
        language=language, audio_path="x.wav", status=status, duration_s=duration_s, test_key=test_key,
    )  # fmt: skip
    session.add(call)
    session.flush()
    if status == "done":
        segs = [Segment(id=uuid.uuid4(), call_id=call.id, idx=i, speaker="agent" if i % 2 == 0 else "borrower",
                        start_s=i * 5.0, end_s=i * 5.0 + 4, text=f"line {i}") for i in range(6)]  # fmt: skip
        session.add_all(segs)
        session.flush()
        for n, (code, reviewer) in enumerate(violations or []):
            session.add(
                Violation(call_id=call.id, rule_code=code, segment_id=segs[(n * 2) % 6].id, quote=f"quote {n}",
                          start_s=segs[(n * 2) % 6].start_s, explanation="why", confidence=0.9, detected_by="both",
                          reviewer_status=reviewer)
            )  # fmt: skip
        session.flush()
        session.refresh(call, ["violations"])
        recompute_call_score(session, call)
    session.commit()
    return call
