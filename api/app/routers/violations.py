from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_session
from app.errors import not_found
from app.models import Violation
from app.routers.deps import parse_uuid
from app.services.queries import recompute_call_score, rules_by_code, violation_schema

router = APIRouter()


@router.patch("/violations/{violation_id}", response_model=schemas.ViolationPatchResult)
def review_violation(
    violation_id: str, body: schemas.ViolationPatch, session: Session = Depends(get_session)
) -> schemas.ViolationPatchResult:
    v = session.get(Violation, parse_uuid(violation_id, "Violation"))
    if v is None:
        raise not_found("Violation", violation_id)
    v.reviewer_status = body.reviewer_status
    session.flush()
    session.refresh(v.call, ["violations"])
    score = recompute_call_score(session, v.call)
    session.commit()
    return schemas.ViolationPatchResult(violation=violation_schema(v, rules_by_code(session)), call_score=score)
