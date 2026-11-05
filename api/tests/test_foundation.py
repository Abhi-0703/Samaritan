from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from app.config import Settings, get_settings, load_yaml
from app.logging_config import RedactingFormatter
from app.main import create_app
from app.models import Agent, Call, Rule
from app.seed import seed_rules


def test_settings_parse_env_values():
    s = Settings(llm_cache="off", cors_origins="http://a.test, http://b.test")
    assert s.llm_cache is False
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
    assert Settings(llm_cache="on").llm_cache is True


def test_secrets_are_not_in_repr_or_str():
    s = get_settings()
    text = repr(s) + str(s)
    for secret in s.secret_values:
        assert secret not in text


def test_logging_redacts_secrets():
    fmt = RedactingFormatter(["super-secret-value"])
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "key is %s", ("super-secret-value",), None)
    out = fmt.format(rec)
    assert "super-secret-value" not in out and "[REDACTED]" in out


def test_health_and_error_envelope():
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        r = client.get("/nope")
        assert r.status_code == 404
        assert set(r.json()) == {"error"} and r.json()["error"]["code"] == "not_found"


def test_startup_migrates_and_seeds_nine_rules():
    with TestClient(create_app()):
        pass
    from app import db

    with db.session_factory()() as s:
        codes = sorted(r.code for r in s.scalars(select(Rule)))
    assert codes == [f"V{i}" for i in range(1, 10)]


def test_seed_is_idempotent_and_keeps_enabled_switch(session):
    rule = session.get(Rule, "V5")
    rule.enabled = False
    session.commit()
    assert seed_rules(session) == 0
    session.commit()
    assert session.get(Rule, "V5").enabled is False


def test_rule_yaml_matches_plan_severities():
    sev = {r["code"]: r["severity"] for r in load_yaml("rules.yaml")["rules"]}
    assert sev == {
        "V1": "high",
        "V2": "critical",
        "V3": "critical",
        "V4": "critical",
        "V5": "high",
        "V6": "high",
        "V7": "critical",
        "V8": "medium",
        "V9": "medium",
    }


def test_datetimes_round_trip_as_utc(session):
    agent = Agent(name="Test Agent")
    session.add(agent)
    session.flush()
    ist = timezone(timedelta(hours=5, minutes=30))
    called = datetime(2026, 11, 3, 21, 40, tzinfo=ist)
    call = Call(agent_id=agent.id, loan_ref="SF-PL-000001", called_at=called, language="hinglish", audio_path="x.wav")
    session.add(call)
    session.commit()
    session.expire_all()
    got = session.get(Call, call.id)
    assert got.called_at == called
    assert got.called_at.utcoffset() == timedelta(0)
    assert got.called_at.astimezone(UTC).hour == 16  # 21:40 IST is 16:10 UTC


def test_naive_datetimes_are_rejected(session):
    agent = Agent(name="A")
    session.add(agent)
    session.flush()
    naive = datetime(2026, 1, 1)
    session.add(Call(agent_id=agent.id, loan_ref="x", called_at=naive, language="hinglish", audio_path="x"))
    with pytest.raises(StatementError, match="timezone-aware"):
        session.flush()


def test_database_constraints(session):
    agent = Agent(name="A")
    session.add(agent)
    session.flush()
    session.add(Call(agent_id=agent.id, loan_ref="x", called_at=datetime.now(UTC), language="klingon", audio_path="x"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    orphan = Call(agent_id=uuid.uuid4(), loan_ref="x", called_at=datetime.now(UTC), language="hinglish", audio_path="x")
    session.add(orphan)
    with pytest.raises(IntegrityError):  # foreign keys are enforced on SQLite
        session.flush()
