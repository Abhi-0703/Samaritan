"""Reads and aggregations shared by the routers and the pipeline. Semantics follow docs/decisions.md D-012.

A call's score, `violations_count` and `max_severity` count only non-dismissed violations of enabled rules.
`CallDetail.violations` includes dismissed ones but hides violations of disabled rules.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import schemas
from app.detection.rules_engine import IST
from app.models import Agent, Call, Rule, Segment, Violation
from app.services.scoring import call_score, mean_score

SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1}
LLM_NOTICE = "Analysed without LLM: the language model was unavailable, so only keyword rules were applied."


def iso_ist(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="seconds")


def ist_day(dt: datetime) -> str:
    return dt.astimezone(IST).date().isoformat()


def rules_by_code(session: Session) -> dict[str, Rule]:
    return {r.code: r for r in session.scalars(select(Rule))}


def enabled_codes(session: Session) -> set[str]:
    return {r.code for r in session.scalars(select(Rule).where(Rule.enabled.is_(True)))}


def is_active(v: Violation, rules: dict[str, Rule]) -> bool:
    rule = rules.get(v.rule_code)
    return bool(rule and rule.enabled and v.reviewer_status != "dismissed")


def active_violations(call: Call, rules: dict[str, Rule]) -> list[Violation]:
    return [v for v in call.violations if is_active(v, rules)]


def compute_score(call: Call, rules: dict[str, Rule]) -> float:
    return call_score(rules[v.rule_code].severity for v in active_violations(call, rules))


def recompute_call_score(session: Session, call: Call) -> float | None:
    if call.status != "done":
        return None
    call.score = compute_score(call, rules_by_code(session))
    return call.score


def recompute_all_scores(session: Session) -> int:
    rules = rules_by_code(session)
    calls = session.scalars(select(Call).where(Call.status == "done").options(selectinload(Call.violations))).all()
    for c in calls:
        c.score = compute_score(c, rules)
    return len(calls)


# ---- serialisers -------------------------------------------------------------------------------------------------


def call_schema(call: Call, rules: dict[str, Rule]) -> schemas.Call:
    done = call.status == "done"
    active = active_violations(call, rules) if done else []
    max_sev = max((rules[v.rule_code].severity for v in active), key=SEVERITY_RANK.__getitem__, default=None)
    return schemas.Call(
        id=str(call.id),
        test_key=call.test_key,
        agent_id=str(call.agent_id),
        agent_name=call.agent.name,
        loan_ref=call.loan_ref,
        called_at=iso_ist(call.called_at),
        duration_s=call.duration_s,
        language=call.language,  # type: ignore[arg-type]
        status=call.status,  # type: ignore[arg-type]
        score=compute_score(call, rules) if done else None,
        violations_count=len(active),
        max_severity=max_sev,
        error=call.error,
        borrower_requested_time=call.borrower_requested_time,
    )


def violation_schema(v: Violation, rules: dict[str, Rule]) -> schemas.Violation:
    rule = rules[v.rule_code]
    return schemas.Violation(
        id=str(v.id), call_id=str(v.call_id), rule_code=v.rule_code, rule_name=rule.name,
        severity=rule.severity,  # type: ignore[arg-type]
        segment_id=str(v.segment_id) if v.segment_id else None, quote=v.quote, start_s=v.start_s,
        explanation=v.explanation, confidence=v.confidence, detected_by=v.detected_by,  # type: ignore[arg-type]
        reviewer_status=v.reviewer_status,  # type: ignore[arg-type]
    )  # fmt: skip


def segment_schema(s: Segment) -> schemas.Segment:
    return schemas.Segment(
        id=str(s.id),
        index=s.idx,
        speaker=s.speaker,
        start_s=s.start_s,
        end_s=s.end_s,
        text=s.text,  # type: ignore[arg-type]
    )


def rule_schema(r: Rule) -> schemas.Rule:
    return schemas.Rule(
        code=r.code, name=r.name, description=r.description, rbi_reference=r.rbi_reference,
        severity=r.severity, detection=r.detection, enabled=r.enabled,  # type: ignore[arg-type]
    )  # fmt: skip


def call_detail(session: Session, call: Call) -> schemas.CallDetail:
    rules = rules_by_code(session)
    base = call_schema(call, rules)
    meta = call.analysis_meta or {}
    transcription = None
    if call.raw_transcript:
        cfg = call.transcription_config or {}
        transcription = schemas.TranscriptionInfo(
            model=str(call.raw_transcript.get("model") or cfg.get("model") or ""),
            language_code=str(call.raw_transcript.get("language_code") or cfg.get("language_code") or ""),
            format=cfg.get("format"),
        )
    visible = [v for v in call.violations if rules[v.rule_code].enabled]
    visible.sort(key=lambda v: (-1.0 if v.start_s is None else v.start_s, v.rule_code))
    return schemas.CallDetail(
        **base.model_dump(),
        segments=[segment_schema(s) for s in call.segments],
        violations=[violation_schema(v, rules) for v in visible],
        roles_look_correct=call.roles_look_correct,
        analysis_notice=LLM_NOTICE if meta.get("llm_failed") else None,
        transcription=transcription,
    )


# ---- agents ------------------------------------------------------------------------------------------------------


def _done_calls(session: Session) -> list[Call]:
    return list(
        session.scalars(
            select(Call).where(Call.status == "done").options(selectinload(Call.violations), selectinload(Call.agent))
        )
    )


def agent_stats(agent: Agent, done_calls: list[Call], rules: dict[str, Rule]) -> schemas.Agent:
    mine = [c for c in done_calls if c.agent_id == agent.id]
    scores = [compute_score(c, rules) for c in mine]
    active = [v for c in mine for v in active_violations(c, rules)]
    counts = Counter(v.rule_code for v in active)
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return schemas.Agent(
        id=str(agent.id), name=agent.name, team=agent.team, calls_count=len(mine), avg_score=mean_score(scores),
        critical_count=sum(1 for v in active if rules[v.rule_code].severity == "critical"),
        violation_rate=(sum(1 for c in mine if active_violations(c, rules)) / len(mine)) if mine else 0.0,
        top_rule_code=top[0][0] if top else None,
    )  # fmt: skip


def list_agents(session: Session) -> list[schemas.Agent]:
    rules, done = rules_by_code(session), _done_calls(session)
    return [agent_stats(a, done, rules) for a in session.scalars(select(Agent).order_by(Agent.name))]


def agent_detail(session: Session, agent: Agent) -> schemas.AgentDetail:
    rules, done = rules_by_code(session), _done_calls(session)
    base = agent_stats(agent, done, rules)
    mine = [c for c in done if c.agent_id == agent.id]
    by_day: dict[str, list[float]] = defaultdict(list)
    for c in mine:
        by_day[ist_day(c.called_at)].append(compute_score(c, rules))
    trend = [schemas.ScorePoint(date=d, avg_score=sum(s) / len(s), calls=len(s)) for d, s in sorted(by_day.items())]
    counts = Counter(v.rule_code for c in mine for v in active_violations(c, rules))
    by_rule = [
        schemas.RuleCount(rule_code=code, rule_name=rules[code].name, count=n) for code, n in counts.most_common()
    ]
    all_calls = session.scalars(
        select(Call).where(Call.agent_id == agent.id).options(selectinload(Call.violations), selectinload(Call.agent))
    ).all()
    schemas_ = [call_schema(c, rules) for c in all_calls]
    schemas_.sort(key=lambda c: (c.score if c.score is not None else 101, c.called_at))
    return schemas.AgentDetail(**base.model_dump(), score_trend=trend, violations_by_rule=by_rule, calls=schemas_)


# ---- overview ----------------------------------------------------------------------------------------------------


def overview(session: Session, now: datetime | None = None) -> schemas.OverviewStats:
    now = now or datetime.now(UTC)
    rules, done = rules_by_code(session), _done_calls(session)
    pending = (
        session.scalar(
            select(func.count()).select_from(Call).where(Call.status.in_(("queued", "transcribing", "analysing")))
        )
        or 0
    )
    window_days = [(now - timedelta(days=i)).astimezone(IST).date().isoformat() for i in range(13, -1, -1)]
    cutoff = window_days[0]

    per_day = {d: Counter() for d in window_days}
    flagged_calls = 0
    critical = 0
    rule_counts: Counter = Counter()
    rule_calls: dict[str, set] = defaultdict(set)
    recent: list[tuple[datetime, Call, Violation]] = []
    for c in done:
        active = active_violations(c, rules)
        flagged_calls += bool(active)
        in_window = ist_day(c.called_at) >= cutoff
        for v in active:
            sev = rules[v.rule_code].severity
            rule_counts[v.rule_code] += 1
            rule_calls[v.rule_code].add(c.id)
            if in_window:
                critical += sev == "critical"
                if ist_day(c.called_at) in per_day:
                    per_day[ist_day(c.called_at)][sev] += 1
            if sev == "critical":
                recent.append((c.called_at, c, v))

    agents = list_agents(session)
    needing = sorted((a for a in agents if a.avg_score is not None), key=lambda a: a.avg_score)[:5]  # type: ignore[arg-type,return-value]
    n = len(done)
    recent.sort(key=lambda t: t[0], reverse=True)
    return schemas.OverviewStats(
        as_of=iso_ist(now), calls_audited=n, calls_with_violations=flagged_calls,
        calls_with_violations_pct=(flagged_calls / n * 100) if n else 0.0, critical_flags=critical,
        avg_score=mean_score(compute_score(c, rules) for c in done), calls_pending=pending,
        violations_per_day=[
            schemas.DayCount(
                date=d, critical=per_day[d]["critical"], high=per_day[d]["high"], medium=per_day[d]["medium"]
            )
            for d in window_days
        ],
        top_rules=[
            schemas.TopRule(
                rule_code=code, rule_name=rules[code].name, count=cnt,
                pct_of_calls=(len(rule_calls[code]) / n * 100) if n else 0.0,
            )
            for code, cnt in rule_counts.most_common(6)
        ],
        agents_needing_review=[
            schemas.AgentReview(
                agent_id=a.id, agent_name=a.name, calls=a.calls_count, avg_score=a.avg_score or 0.0,
                critical_flags=a.critical_count,
            )
            for a in needing
        ],
        recent_critical=[
            schemas.RecentCritical(
                violation_id=str(v.id), call_id=str(c.id), agent_name=c.agent.name, called_at=iso_ist(c.called_at),
                rule_code=v.rule_code, rule_name=rules[v.rule_code].name, quote=v.quote, start_s=v.start_s,
            )
            for _, c, v in recent[:6]
        ],
    )  # fmt: skip
