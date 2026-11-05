from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_session
from app.services.queries import overview

router = APIRouter()


@router.get("/stats/overview", response_model=schemas.OverviewStats)
def get_overview(session: Session = Depends(get_session)) -> schemas.OverviewStats:
    return overview(session)
