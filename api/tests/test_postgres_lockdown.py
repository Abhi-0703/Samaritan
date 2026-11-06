"""The Supabase lock-down SQL, run on a local Postgres with stand-ins for Supabase's roles and storage schema."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

SQL = Path(__file__).resolve().parents[2] / "supabase" / "rls_and_storage.sql"

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_PG"), reason="needs a Postgres: run with TEST_PG=1")


@pytest.fixture
def pg(pg_url):
    engine = create_engine(pg_url.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT")
    yield engine
    with engine.connect() as c:
        c.execute(text("DROP SCHEMA IF EXISTS storage CASCADE"))
        for role in ("anon", "authenticated"):
            c.execute(text(f"DROP OWNED BY {role}"))
            c.execute(text(f"DROP ROLE IF EXISTS {role}"))
    engine.dispose()


def prepare(engine):
    with engine.connect() as c:
        for role in ("anon", "authenticated"):
            c.execute(text(f"DROP ROLE IF EXISTS {role}"))
            c.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        c.execute(text("GRANT USAGE ON SCHEMA public TO anon, authenticated"))
        c.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated"))  # Supabase's default
        c.execute(text("DROP SCHEMA IF EXISTS storage CASCADE"))
        c.execute(text("CREATE SCHEMA storage"))
        c.execute(text(
            "CREATE TABLE storage.buckets (id text primary key, name text not null, public boolean default false,"
            " file_size_limit bigint)"
        ))  # fmt: skip
        c.execute(text("INSERT INTO storage.buckets (id, name, public) VALUES ('call-audio', 'call-audio', true)"))


def test_lockdown_sql(session, pg):
    from app.models import Agent

    session.add(Agent(name="Someone", team="Collections"))
    session.commit()
    prepare(pg)
    with pg.connect() as c:
        c.execute(text("SELECT count(*) FROM agents"))  # before: the roles could read everything
        c.execute(text("SET ROLE anon"))
        assert c.execute(text("SELECT count(*) FROM agents")).scalar() == 1
        c.execute(text("RESET ROLE"))

    sql = SQL.read_text(encoding="utf-8")
    with pg.connect() as c:
        c.execute(text(sql))
        c.execute(text(sql))  # safe to run twice
        tables = [r[0] for r in c.execute(text("select tablename from pg_tables where schemaname='public'"))]
        assert {"agents", "calls", "segments", "violations", "rules", "eval_runs", "llm_cache"} <= set(tables)
        off = c.execute(text("select relname from pg_class c join pg_namespace n on n.oid=c.relnamespace "
                             "where n.nspname='public' and c.relkind='r' and not c.relrowsecurity")).all()  # fmt: skip
        assert off == []  # row level security is on for every table
        bucket = c.execute(text("select public, file_size_limit from storage.buckets where id='call-audio'")).one()
        assert tuple(bucket) == (False, 26214400)
        for role in ("anon", "authenticated"):
            c.execute(text(f"SET ROLE {role}"))
            for table in tables:
                with pytest.raises(Exception, match="permission denied"):
                    c.execute(text(f"SELECT * FROM {table} LIMIT 1"))
            c.execute(text("RESET ROLE"))
        # the owner (the API's role) is unaffected
        assert c.execute(text("SELECT count(*) FROM agents")).scalar() == 1
