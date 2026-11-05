from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings, get_settings
from app.db import get_session, session_factory
from app.detection.rules_engine import IST
from app.errors import ApiError
from app.evaluation import keys as keys_mod
from app.evaluation import runner
from app.guards import demo_guard
from app.models import EvalRun
from app.routers.deps import get_runtime
from app.runtime import Runtime

router = APIRouter()


def eval_schema(row: EvalRun) -> schemas.EvalRun:
    return schemas.EvalRun(
        id=str(row.id),
        run_at=row.run_at.astimezone(IST).isoformat(timespec="seconds"),
        config=row.config,  # type: ignore[arg-type]
        prompt_version=row.prompt_version,
        models=schemas.EvalModels(**row.models),
        n_calls=row.n_calls,
        overall=schemas.PRF(**row.overall),
        rule_level_recall=row.rule_level_recall or 0.0,
        timestamp_accuracy=row.timestamp_accuracy or 0.0,
        clean_calls_flagged=row.clean_calls_flagged or 0,
        clean_calls_total=row.clean_calls_total or 0,
        role_mapping_accuracy=row.role_mapping_accuracy or 0.0,
        per_rule={k: schemas.RuleMetrics(**v) for k, v in row.per_rule.items()},
        per_slice={k: schemas.SliceMetrics(**v) for k, v in row.per_slice.items()},
        failures=[schemas.EvalFailure(**f) for f in row.failures],
    )


def latest(session: Session) -> schemas.LatestEval:
    def one(config: str) -> schemas.EvalRun | None:
        row = session.scalars(
            select(EvalRun).where(EvalRun.config == config).order_by(EvalRun.run_at.desc()).limit(1)
        ).first()
        return eval_schema(row) if row else None

    return schemas.LatestEval(rules_only=one("rules_only"), rules_plus_llm=one("rules_plus_llm"))


@router.get("/eval/latest", response_model=schemas.LatestEval)
def get_latest(session: Session = Depends(get_session)) -> schemas.LatestEval:
    return latest(session)


def admin_guard(request: Request, settings: Settings = Depends(get_settings)) -> None:
    expected = settings.admin_token.get_secret_value()
    given = request.headers.get("x-admin-token", "")
    if not expected or not secrets.compare_digest(given.encode(), expected.encode()):
        raise ApiError(403, "forbidden", "The admin token is missing or incorrect.")


@router.post("/eval/run", response_model=schemas.LatestEval, dependencies=[Depends(admin_guard), Depends(demo_guard)])
async def run_eval(runtime: Runtime = Depends(get_runtime)) -> schemas.LatestEval:
    """Dev only. Evaluates the cached transcripts of the test-set calls; never transcribes."""

    def work() -> schemas.LatestEval:
        try:
            keys = keys_mod.load_keys()
        except FileNotFoundError as e:
            raise ApiError(409, "no_answer_keys", "The answer keys are not available on this server.") from e
        with session_factory()() as session:
            ev = runner.evaluate(session, runtime.llm, keys)
            if not runner.store(session, ev):
                raise ApiError(409, "no_data", "No test-set call has a cached transcript yet.")
            return latest(session)

    return await run_in_threadpool(work)
