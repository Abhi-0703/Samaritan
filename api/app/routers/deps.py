from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Call
from app.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as e:
        raise not_found(what, value) from e


def load_call(session: Session, call_id: str) -> Call:
    call = session.get(Call, parse_uuid(call_id, "Call"))
    if call is None:
        raise not_found("Call", call_id)
    return call


def bad_request(message: str, code: str = "invalid_request") -> ApiError:
    return ApiError(400, code, message)
