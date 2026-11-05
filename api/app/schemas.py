"""API schemas. Keep in sync with web/src/lib/types.ts (plan.md Section 10.2). snake_case everywhere."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["critical", "high", "medium"]
CallStatus = Literal["queued", "transcribing", "analysing", "done", "failed"]
Language = Literal["hinglish", "marathi"]
ReviewerStatus = Literal["open", "confirmed", "dismissed"]
DetectedBy = Literal["rules", "llm", "both", "metadata"]
SpeakerLabel = Literal["agent", "borrower", "unknown"]

T = TypeVar("T")


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginated(Schema, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class Agent(Schema):
    id: str
    name: str
    team: str
    calls_count: int
    avg_score: float | None
    critical_count: int
    violation_rate: float  # 0..1
    top_rule_code: str | None


class AgentCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    team: str = Field(default="Collections", max_length=120)


class Call(Schema):
    id: str
    test_key: str | None
    agent_id: str
    agent_name: str
    loan_ref: str
    called_at: str  # ISO 8601 with +05:30
    duration_s: float | None
    language: Language
    status: CallStatus
    score: float | None
    violations_count: int
    max_severity: Severity | None
    error: str | None
    borrower_requested_time: bool


class Segment(Schema):
    id: str
    index: int
    speaker: SpeakerLabel
    start_s: float
    end_s: float
    text: str  # masked


class Violation(Schema):
    id: str
    call_id: str
    rule_code: str
    rule_name: str
    severity: Severity
    segment_id: str | None
    quote: str | None
    start_s: float | None
    explanation: str
    confidence: float
    detected_by: DetectedBy
    reviewer_status: ReviewerStatus


class Rule(Schema):
    code: str
    name: str
    description: str
    rbi_reference: str
    severity: Severity
    detection: str
    enabled: bool


class TranscriptionInfo(Schema):
    model: str
    language_code: str
    format: str | None


class CallDetail(Call):
    segments: list[Segment]
    violations: list[Violation]
    roles_look_correct: bool
    analysis_notice: str | None
    transcription: TranscriptionInfo | None


class UploadMetadata(Schema):
    filename: str
    agent_id: str | None = None
    agent_name: str | None = None
    called_at: str
    language: Language
    loan_ref: str = Field(min_length=1, max_length=64)
    borrower_requested_time: bool = False


class AudioUrl(Schema):
    url: str
    expires_at: str


class ViolationPatch(Schema):
    reviewer_status: ReviewerStatus


class ViolationPatchResult(Schema):
    violation: Violation
    call_score: float | None


class RulePatch(Schema):
    enabled: bool


class DayCount(Schema):
    date: str
    critical: int
    high: int
    medium: int


class TopRule(Schema):
    rule_code: str
    rule_name: str
    count: int
    pct_of_calls: float


class AgentReview(Schema):
    agent_id: str
    agent_name: str
    calls: int
    avg_score: float
    critical_flags: int


class RecentCritical(Schema):
    violation_id: str
    call_id: str
    agent_name: str
    called_at: str
    rule_code: str
    rule_name: str
    quote: str | None
    start_s: float | None


class OverviewStats(Schema):
    as_of: str
    calls_audited: int
    calls_with_violations: int
    calls_with_violations_pct: float  # 0..100
    critical_flags: int  # non-dismissed critical flags on finished calls in the last 14 days
    avg_score: float | None
    calls_pending: int
    violations_per_day: list[DayCount]  # last 14 days, oldest first
    top_rules: list[TopRule]
    agents_needing_review: list[AgentReview]
    recent_critical: list[RecentCritical]


class ScorePoint(Schema):
    date: str
    avg_score: float
    calls: int


class RuleCount(Schema):
    rule_code: str
    rule_name: str
    count: int


class AgentDetail(Agent):
    score_trend: list[ScorePoint]
    violations_by_rule: list[RuleCount]
    calls: list[Call]


class PRF(Schema):
    precision: float
    recall: float
    f1: float


class RuleMetrics(PRF):
    tp: int
    fp: int
    fn: int


class SliceMetrics(PRF):
    n_calls: int


class EvalFailure(Schema):
    test_key: str
    rule_code: str
    kind: Literal["fp", "fn"]
    note: str


class EvalModels(Schema):
    stt: str
    llm: str


class EvalRun(Schema):
    id: str
    run_at: str
    config: Literal["rules_only", "rules_plus_llm"]
    prompt_version: str
    models: EvalModels
    n_calls: int
    overall: PRF
    rule_level_recall: float
    timestamp_accuracy: float
    clean_calls_flagged: int
    clean_calls_total: int
    role_mapping_accuracy: float
    per_rule: dict[str, RuleMetrics]
    per_slice: dict[str, SliceMetrics]
    failures: list[EvalFailure]


class LatestEval(Schema):
    rules_only: EvalRun | None
    rules_plus_llm: EvalRun | None
