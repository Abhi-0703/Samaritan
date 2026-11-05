from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_session
from app.errors import not_found
from app.models import Rule
from app.services.queries import recompute_all_scores, rule_schema

router = APIRouter()


@router.get("/rules", response_model=list[schemas.Rule])
def list_rules(session: Session = Depends(get_session)) -> list[schemas.Rule]:
    return [rule_schema(r) for r in session.scalars(select(Rule).order_by(Rule.code))]


@router.patch("/rules/{code}", response_model=schemas.Rule)
def toggle_rule(code: str, body: schemas.RulePatch, session: Session = Depends(get_session)) -> schemas.Rule:
    """Disabling skips the rule in future analysis, hides its flags and recomputes every score. Nothing is deleted."""
    rule = session.get(Rule, code.upper())
    if rule is None:
        raise not_found("Rule", code)
    rule.enabled = body.enabled
    session.flush()
    recompute_all_scores(session)
    session.commit()
    return rule_schema(rule)
