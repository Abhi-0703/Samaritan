from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app import db
from app.config import Settings
from app.models import Agent, Base, Call, Rule
from app.seed import seed_rules
from app.seeding_cli import describe, main
from app.storage.local import LocalStorage
from tests.helpers import make_agent, make_call, make_wav


@pytest.fixture
def local_source(tmp_path):
    """A processed 'local' database and its audio folder."""
    engine = db.make_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_rules(s)
        s.commit()
        call = make_call(s, make_agent(s, "Rohit Patil"), test_key="call_01", violations=[("V5", "open")])
        call.is_test_set = True
        audio = LocalStorage(tmp_path / "local_audio")
        call.audio_path = audio.save(str(call.id), make_wav(tmp_path / "a.wav", 1), "a.wav")
        s.commit()
    return ["--source-url", f"sqlite:///{tmp_path / 'local.db'}", "--source-audio", str(tmp_path / "local_audio")]


def counts(session):
    session.expire_all()
    return session.query(Agent).count(), session.query(Call).count()


def test_seed_without_yes_is_a_dry_run(session, local_source, capsys):
    session.query(Agent).delete()
    session.commit()
    assert main("seed", ["--from-local", *local_source]) == 0
    out = capsys.readouterr().out
    assert "Dry run. Nothing was changed" in out and counts(session) == (0, 0)


def test_seed_yes_adds_reference_data_and_the_processed_calls(session, local_source, capsys):
    assert main("seed", ["--yes", "--from-local", *local_source]) == 0
    out = capsys.readouterr().out
    assert "calls copied: 1" in out and "audio files uploaded: 1" in out
    assert counts(session) == (6, 1)
    assert session.query(Agent).filter_by(name="Rohit Patil").count() == 1  # not duplicated next to the roster entry
    assert main("seed", ["--yes", "--from-local", *local_source]) == 0  # running it again adds nothing
    assert counts(session) == (6, 1)


def test_seed_without_from_local_adds_only_reference_data(session, local_source):
    assert main("seed", ["--yes", *local_source]) == 0
    assert counts(session) == (6, 0)


def test_migrate_copies_everything_and_refuses_the_same_database(session, local_source, capsys, monkeypatch):
    assert main("migrate_local_to_supabase", ["--yes", *local_source]) == 0
    assert counts(session)[1] == 1
    url = db.get_engine().url.render_as_string(hide_password=False)
    assert main("migrate_local_to_supabase", ["--yes", "--source-url", url]) == 2
    assert "same database" in capsys.readouterr().err


def test_reset_demo_removes_uploads(session, tmp_path, capsys):
    visitor_id = make_call(session, make_agent(session, "Visitor")).id
    session.commit()
    assert main("reset_demo", []) == 0 and session.get(Call, visitor_id) is not None  # dry run
    assert main("reset_demo", ["--yes"]) == 0
    session.expire_all()
    assert session.get(Call, visitor_id) is None and "uploaded calls removed: 1" in capsys.readouterr().out
    assert session.query(Rule).count() == 9


def test_the_destination_is_described_without_its_password():
    s = Settings(
        database_url="postgresql://postgres.abcd:S3cr3t!@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
        storage_backend="supabase",
    )
    text = describe(s)
    assert "S3cr3t" not in text and "postgres.abcd" not in text
    assert text == "database postgresql at aws-0-ap-south-1.pooler.supabase.com:6543; audio storage: supabase"


def test_supabase_urls_are_normalised_to_the_psycopg_driver():
    assert db.normalise_url("postgresql://u:p@h:6543/postgres") == "postgresql+psycopg://u:p@h:6543/postgres"
    assert db.normalise_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert db.normalise_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert db.normalise_url("sqlite:////tmp/x.db") == "sqlite:////tmp/x.db"


def test_the_postgres_engine_is_set_up_for_the_transaction_pooler(monkeypatch):
    import psycopg

    seen = {}

    def fake_connect(*args, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop here")

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    engine = db.make_engine("postgresql://u:p@localhost:6543/postgres")
    assert engine.url.drivername == "postgresql+psycopg" and engine.pool.size() == 5
    with pytest.raises(Exception, match="stop here"):
        engine.connect()
    assert seen["prepare_threshold"] is None  # no prepared statements: the pooler would lose them between queries


@pytest.mark.skipif(not __import__("os").environ.get("TEST_PG"), reason="needs a Postgres: run with TEST_PG=1")
def test_start_up_on_an_unmigrated_postgres_says_what_to_do(pg_url, runtime):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from app.main import create_app

    engine = create_engine(pg_url.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    with pytest.raises(RuntimeError, match="python -m app.migrate"), TestClient(create_app(lambda s: runtime)):
        pass


def test_a_relative_sqlite_path_is_read_from_the_api_folder_not_the_working_directory(tmp_path, monkeypatch):
    from app.config import API_DIR

    monkeypatch.chdir(tmp_path)
    assert db.normalise_url("sqlite:///./local.db") == f"sqlite:///{API_DIR / 'local.db'}"
    assert db.normalise_url("sqlite:///.data/x.db") == f"sqlite:///{API_DIR / '.data' / 'x.db'}"
    assert db.normalise_url("sqlite:////abs/path.db") == "sqlite:////abs/path.db"
    assert db.normalise_url("sqlite://") == "sqlite://"
    assert db.normalise_url("sqlite:///:memory:") == "sqlite:///:memory:"
