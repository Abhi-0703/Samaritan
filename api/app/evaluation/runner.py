"""Run both configurations over the cached transcripts of the test-set calls and store the results.

Never transcribes: a call without a cached transcript is listed as "not evaluated". Both configurations see the same
transcripts, so differences come from detection, not from transcription variance (architecture.md Section 12).
The nine rules are always all enabled here, whatever the reviewer toggles in the app.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.llm_judge import PROMPT_VERSION, JudgeOutcome, judge_call
from app.detection.merge import MergedFlag, merge_flags, rules_only_flags
from app.evaluation.keys import AnswerKey
from app.evaluation.metrics import (
    CallMatch,
    Predicted,
    Summary,
    match_call,
    prf,
    role_mapping_accuracy,
    slices,
    summarise,
)
from app.models import Call, EvalRun, Rule
from app.services.llm.service import LLMService
from app.services.pipeline import prepare

IST = ZoneInfo("Asia/Kolkata")
CONFIGS = ("rules_only", "rules_plus_llm")


@dataclass
class CallOutcome:
    key: AnswerKey
    match: CallMatch
    agent_speaker_id: int | None
    true_agent_speaker_id: int | None
    role_truth: str  # "label" (human) or "script order"


@dataclass
class ConfigResult:
    config: str
    outcomes: list[CallOutcome]
    models: dict[str, str]
    prompt_version: str = PROMPT_VERSION


@dataclass
class Evaluation:
    results: dict[str, ConfigResult] = field(default_factory=dict)  # config -> result
    not_evaluated: list[tuple[str, str]] = field(default_factory=list)  # (test_key, reason)
    warnings: list[str] = field(default_factory=list)


def _called_at(call: Call, key: AnswerKey) -> datetime:
    """The call's own date at the key's time of day, so V1 is judged on what the key says, not on an upload edit."""
    hh, mm = (int(x) for x in key.called_time_ist.split(":"))
    day = call.called_at.astimezone(IST).date()
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)


def _predicted(flags: list[MergedFlag]) -> list[Predicted]:
    return [Predicted(f.rule_code, f.start_s, f.quote) for f in flags]


def _first_speaker(raw: dict) -> int | None:
    for seg in raw.get("segments", []):
        if seg.get("speaker_id") is not None:
            return seg["speaker_id"]
    return None


def evaluate(
    session: Session,
    llm: LLMService | None,
    keys: list[AnswerKey],
    only: set[str] | None = None,
) -> Evaluation:
    ev = Evaluation()
    all_rules = {r.code for r in session.scalars(select(Rule))}
    outcomes: dict[str, list[CallOutcome]] = {c: [] for c in CONFIGS}
    judges: list[JudgeOutcome] = []
    stt_models: set[str] = set()
    llm_failed: list[str] = []

    for key in keys:
        if only and key.test_key not in only:
            continue
        call = session.scalars(select(Call).where(Call.test_key == key.test_key)).first()
        if call is None:
            ev.not_evaluated.append((key.test_key, "no call with this test key (not recorded or not ingested yet)"))
            continue
        if not call.raw_transcript:
            ev.not_evaluated.append((key.test_key, f"no cached transcript (status {call.status})"))
            continue
        called_at = _called_at(call, key)
        prepared = prepare(call.raw_transcript, key.language, called_at, key.borrower_requested_time, all_rules)
        stt_models.add((call.transcription_config or {}).get("model", "unknown"))
        truth, basis = (
            (key.agent_speaker_id, "label")
            if key.agent_speaker_id is not None
            else (_first_speaker(call.raw_transcript), "script order")
        )

        def record(config: str, flags: list[MergedFlag], k=key, p=prepared, t=truth, b=basis) -> None:
            outcomes[config].append(CallOutcome(k, match_call(k, _predicted(flags)), p.roles.agent_speaker_id, t, b))

        record("rules_only", rules_only_flags(prepared.segments, prepared.layer1, called_at, all_rules))
        if llm is not None:
            judge = judge_call(llm, prepared.segments, key.language, prepared.layer1.candidates, all_rules)
            judges.append(judge)
            if judge.ok:
                record("rules_plus_llm", merge_flags(prepared.segments, prepared.layer1, judge, called_at, all_rules))
            else:
                llm_failed.append(key.test_key)

    stt = ", ".join(sorted(stt_models)) or "unknown"
    ev.results["rules_only"] = ConfigResult("rules_only", outcomes["rules_only"], {"stt": stt, "llm": "none"})
    if llm is None:
        ev.warnings.append("No LLM is configured, so rules_plus_llm was not evaluated.")
    elif llm_failed:
        ev.warnings.append(
            f"The LLM was unreachable for {len(llm_failed)} call(s) ({', '.join(llm_failed)}), so rules_plus_llm was "
            "not recorded: a partly rules-only run would be misleading. Run it again."
        )
    else:
        used = sorted({f"{j.provider}/{j.model}" for j in judges if j.provider})
        fallback = any(j.fallback_used for j in judges)
        if fallback:
            ev.warnings.append("The fallback LLM provider answered for at least one call; the models list shows both.")
        ev.results["rules_plus_llm"] = ConfigResult(
            "rules_plus_llm", outcomes["rules_plus_llm"], {"stt": stt, "llm": ", ".join(used) or "unknown"}
        )
    return ev


def summary_for(result: ConfigResult, only: list[str] | None = None) -> tuple[Summary, float]:
    keys = {o.key.test_key: o.key for o in result.outcomes}
    picked = [o for o in result.outcomes if only is None or o.key.test_key in only]
    summary = summarise([o.match for o in picked], keys)
    roles = role_mapping_accuracy((o.agent_speaker_id, o.true_agent_speaker_id) for o in picked)
    return summary, roles


def to_eval_row(result: ConfigResult) -> EvalRun:
    """The EvalRun row (and, through the schema, the API shape) for one configuration."""
    keys = {o.key.test_key: o.key for o in result.outcomes}
    summary, roles = summary_for(result)
    per_slice = {}
    for name, members in slices(keys).items():
        s, _ = summary_for(result, members)
        per_slice[name] = {**_prf(s.overall), "n_calls": s.n_calls}
    return EvalRun(
        id=uuid.uuid4(),
        run_at=datetime.now(UTC),
        config=result.config,
        prompt_version=result.prompt_version,
        models=result.models,
        n_calls=summary.n_calls,
        overall=_prf(summary.overall),
        rule_level_recall=summary.rule_level_recall,
        timestamp_accuracy=summary.timestamp_accuracy,
        clean_calls_flagged=summary.clean_calls_flagged,
        clean_calls_total=summary.clean_calls_total,
        role_mapping_accuracy=roles,
        per_rule={rule: {**_prf(prf(c)), "tp": c.tp, "fp": c.fp, "fn": c.fn} for rule, c in summary.per_rule.items()},
        per_slice=per_slice,
        failures=[
            {"test_key": f.test_key, "rule_code": f.rule_code, "kind": f.kind, "note": f.note}
            for o in result.outcomes
            for f in o.match.failures
        ],
    )


def _prf(p) -> dict[str, float]:
    return {"precision": p.precision, "recall": p.recall, "f1": p.f1}


def store(session: Session, ev: Evaluation) -> list[EvalRun]:
    rows = [to_eval_row(r) for r in ev.results.values() if r.outcomes]
    session.add_all(rows)
    session.commit()
    return rows
