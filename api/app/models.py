"""SQLAlchemy models. Equivalent to the reference SQL in plan.md Section 11, using portable types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# jsonb on Postgres, plain JSON on SQLite
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Stores UTC. SQLite drops time zones, so naive values coming back are treated as UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetimes must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str] = mapped_column(Text, nullable=False, default="Collections")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    calls: Mapped[list[Call]] = relationship(back_populates="agent")


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (CheckConstraint("severity in ('critical','high','medium')", name="ck_rules_severity"),)

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rbi_reference: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    detection: Mapped[str] = mapped_column(Text, nullable=False)  # 'metadata' | 'rules+llm' | 'llm'
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        CheckConstraint("language in ('hinglish','marathi')", name="ck_calls_language"),
        CheckConstraint("status in ('queued','transcribing','analysing','done','failed')", name="ck_calls_status"),
        Index("ix_calls_agent_id", "agent_id"),
        Index("ix_calls_called_at", "called_at"),
        Index("ix_calls_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    test_key: Mapped[str | None] = mapped_column(String(32), unique=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id"), nullable=False)
    loan_ref: Mapped[str] = mapped_column(Text, nullable=False)
    called_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    borrower_requested_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_s: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    audio_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    gnani_job_id: Mapped[str | None] = mapped_column(Text)
    transcription_config: Mapped[dict | None] = mapped_column(JSONType)
    raw_transcript: Mapped[dict | None] = mapped_column(JSONType)  # SERVER-ONLY, never returned by the API
    agent_speaker_id: Mapped[int | None] = mapped_column(Integer)
    roles_look_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    analysis_meta: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    is_test_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    agent: Mapped[Agent] = relationship(back_populates="calls")
    segments: Mapped[list[Segment]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="Segment.idx"
    )
    violations: Mapped[list[Violation]] = relationship(back_populates="call", cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        CheckConstraint("speaker in ('agent','borrower','unknown')", name="ck_segments_speaker"),
        Index("ix_segments_call_idx", "call_id", "idx"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    start_s: Mapped[float] = mapped_column(Float, nullable=False)
    end_s: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # MASKED text only

    call: Mapped[Call] = relationship(back_populates="segments")


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (
        CheckConstraint("detected_by in ('rules','llm','both','metadata')", name="ck_violations_detected_by"),
        CheckConstraint("reviewer_status in ('open','confirmed','dismissed')", name="ck_violations_reviewer"),
        Index("ix_violations_call_id", "call_id"),
        Index("ix_violations_rule_code", "rule_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(8), ForeignKey("rules.code"), nullable=False)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("segments.id", ondelete="SET NULL"))
    quote: Mapped[str | None] = mapped_column(Text)
    start_s: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    detected_by: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    call: Mapped[Call] = relationship(back_populates="violations")
    rule: Mapped[Rule] = relationship()


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = (CheckConstraint("config in ('rules_only','rules_plus_llm')", name="ck_eval_config"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    config: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    models: Mapped[dict] = mapped_column(JSONType, nullable=False)
    n_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[dict] = mapped_column(JSONType, nullable=False)
    rule_level_recall: Mapped[float | None] = mapped_column(Float)
    timestamp_accuracy: Mapped[float | None] = mapped_column(Float)
    clean_calls_flagged: Mapped[int | None] = mapped_column(Integer)
    clean_calls_total: Mapped[int | None] = mapped_column(Integer)
    role_mapping_accuracy: Mapped[float | None] = mapped_column(Float)
    per_rule: Mapped[dict] = mapped_column(JSONType, nullable=False)
    per_slice: Mapped[dict] = mapped_column(JSONType, nullable=False)
    failures: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)


class LlmCache(Base):
    __tablename__ = "llm_cache"

    # sha256(provider, model, prompt_version, system, user)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
