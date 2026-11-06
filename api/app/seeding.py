"""Seeding, copying local data to a new database, and resetting the public demo (plan.md Phase 3).

Nothing here transcribes or calls an LLM: processed calls are copied with their cached transcripts and violations,
and only calls the pipeline really processed are ever inserted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_yaml
from app.models import Agent, Call, EvalRun, LlmCache, Rule, Segment, Violation
from app.seed import seed_rules
from app.services.queries import recompute_all_scores
from app.storage.base import AudioStorage

IST = ZoneInfo("Asia/Kolkata")

# The six agents of the demo workspace (plan.md Section 12, Phase 1). Names in the test scripts are among them.
ROSTER = ["Rohit Patil", "Sneha Kulkarni", "Imran Shaikh", "Pooja Yadav", "Aakash Verma", "Kavita Joshi"]


@dataclass
class Report:
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, name: str, n: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + n

    def lines(self) -> list[str]:
        return [f"{k}: {v}" for k, v in self.counts.items()] + [f"note: {n}" for n in self.notes]


def seed_reference_data(session: Session) -> Report:
    """The nine rules and the six agents. Existing rows are kept, and a rule's enabled switch is never touched."""
    report = Report()
    report.add("rules added or refreshed", seed_rules(session))
    team = load_yaml("workspace.yaml")["default_agent_team"]
    have = {a.name.lower() for a in session.scalars(select(Agent))}
    for name in ROSTER:
        if name.lower() not in have:
            session.add(Agent(name=name, team=team))
            report.add("agents added")
    session.flush()
    return report


def redate(called_at: datetime, index: int, today: datetime | None = None) -> datetime:
    """Move a call into the last 14 days, keeping its time of day (V1 depends on it)."""
    today_ist = (today or datetime.now(IST)).astimezone(IST).date()
    day = today_ist - timedelta(days=index % 14)
    t = called_at.astimezone(IST)
    return datetime(day.year, day.month, day.day, t.hour, t.minute, t.second, tzinfo=IST)


def _row(obj) -> dict:
    return {a.key: getattr(obj, a.key) for a in obj.__mapper__.column_attrs}


def _copy_row(dst: Session, model, obj, replace: bool, report: Report, label: str, **overrides) -> bool:
    data = {**_row(obj), **overrides}
    pk = tuple(data[c.key] for c in model.__mapper__.primary_key)
    existing = dst.get(model, pk[0] if len(pk) == 1 else pk)
    if existing is not None and not replace:
        report.add(f"{label} skipped (already there)")
        return False
    dst.merge(model(**data))
    report.add(f"{label} copied")
    return True


def copy_data(
    src: Session,
    dst: Session,
    *,
    src_storage: AudioStorage | None = None,
    dst_storage: AudioStorage | None = None,
    only_test_set: bool = False,
    redate_calls: bool = False,
    replace: bool = False,
    today: datetime | None = None,
    progress: Callable[[str], None] = lambda _: None,
) -> Report:
    """Copy processed calls (with segments, violations and cached transcripts), the LLM cache, evaluation runs and the
    reviewer's rule switches from `src` to `dst`, without re-transcribing. Safe to run twice."""
    report = Report()
    for rule in src.scalars(select(Rule)):
        target = dst.get(Rule, rule.code)
        if target is not None and target.enabled != rule.enabled:
            target.enabled = rule.enabled
            report.add("rule switches copied")

    stmt = select(Call).order_by(Call.test_key, Call.created_at)
    if only_test_set:
        stmt = stmt.where(Call.is_test_set.is_(True), Call.status == "done")
    calls = list(src.scalars(stmt))

    dst_agents = {a.name.lower(): a for a in dst.scalars(select(Agent))}
    agent_map: dict = {}
    wanted = {c.agent_id for c in calls} if only_test_set else None  # a test seed brings only the agents it needs
    for a in src.scalars(select(Agent)):
        if wanted is not None and a.id not in wanted:
            continue
        match = dst.get(Agent, a.id) or dst_agents.get(a.name.lower())
        if match is None:
            match = Agent(**_row(a))
            dst.add(match)
            dst_agents[a.name.lower()] = match
            report.add("agents copied")
        agent_map[a.id] = match.id
    dst.flush()

    for i, call in enumerate(calls):
        if dst.get(Call, call.id) is not None and not replace:
            report.add("calls skipped (already there)")
            continue
        if replace:
            old = dst.get(Call, call.id)
            if old is not None:
                dst.delete(old)
                dst.flush()
        overrides = {"agent_id": agent_map[call.agent_id]}
        if redate_calls:
            overrides["called_at"] = redate(call.called_at, i, today)
        dst.add(Call(**{**_row(call), **overrides}))
        dst.flush()
        for seg in call.segments:
            dst.add(Segment(**_row(seg)))
        dst.flush()
        for v in call.violations:
            dst.add(Violation(**_row(v)))
        report.add("calls copied")
        report.add("segments copied", len(call.segments))
        report.add("violations copied", len(call.violations))
        if src_storage is not None and dst_storage is not None and call.audio_path:
            try:
                path = src_storage.local_path(call.audio_path)
                key = dst_storage.save(str(call.id), path, call.audio_path)
                if key != call.audio_path:
                    dst.get(Call, call.id).audio_path = key  # type: ignore[union-attr]
                report.add("audio files uploaded")
            except (OSError, ValueError, RuntimeError) as e:
                report.notes.append(f"audio for call {call.test_key or call.id} not copied: {type(e).__name__}")
        progress(call.test_key or str(call.id))
    dst.flush()

    runs = list(src.scalars(select(EvalRun).order_by(EvalRun.run_at.desc())))
    if only_test_set:  # the latest run of each configuration
        seen, latest = set(), []
        for r in runs:
            if r.config not in seen:
                seen.add(r.config)
                latest.append(r)
        runs = latest
    for r in runs:
        _copy_row(dst, EvalRun, r, False, report, "evaluation runs")
    for c in src.scalars(select(LlmCache)):
        _copy_row(dst, LlmCache, c, False, report, "cached LLM answers")
    return report


def reset_demo(
    session: Session,
    storage: AudioStorage,
    reanalyse: Callable[[Session, Call], None] | None = None,
) -> Report:
    """Back to the seeded state: uploads removed, reviewer decisions and rule switches reset, test-set calls kept.

    A test-set call whose roles a visitor swapped is analysed again from its cached transcript (no Gnani); that needs
    `reanalyse`, otherwise the call is reported so the operator can run it.
    """
    report = Report()
    for call in session.scalars(select(Call).where(Call.is_test_set.is_(False))):
        if call.audio_path:
            try:
                storage.delete(call.audio_path)
            except Exception as e:  # a missing file must not stop the reset
                report.notes.append(f"audio {call.audio_path} not deleted: {type(e).__name__}")
        session.delete(call)
        report.add("uploaded calls removed")
    session.flush()

    for call in session.scalars(select(Call).where(Call.is_test_set.is_(True))):
        meta = dict(call.analysis_meta or {})
        if "agent_speaker_override" in meta:
            meta.pop("agent_speaker_override")
            call.analysis_meta = meta
            session.flush()
            if reanalyse is not None:
                reanalyse(session, call)
                report.add("swapped roles restored")
            else:
                report.notes.append(f"{call.test_key}: roles were swapped; run a retry to restore them")
        for v in call.violations:
            if v.reviewer_status != "open":
                v.reviewer_status = "open"
                report.add("reviewer decisions cleared")
    for rule in session.scalars(select(Rule)):
        if not rule.enabled:
            rule.enabled = True
            report.add("rules switched back on")
    session.flush()

    roster = {n.lower() for n in ROSTER}
    for agent in session.scalars(select(Agent)):
        if agent.name.lower() not in roster and not agent.calls:
            session.delete(agent)
            report.add("extra agents removed")
    session.flush()
    recompute_all_scores(session)
    return report
