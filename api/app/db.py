"""Database engine and sessions. One SQLAlchemy codebase serves SQLite locally and Postgres on Supabase."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def make_engine(url: str) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def init_db(url: str | None = None) -> Engine:
    """(Re)create the engine. Tests call this with a temporary database."""
    global _engine, _factory
    _engine = make_engine(url or get_settings().database_url)
    _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    return _engine or init_db()


def session_factory() -> sessionmaker[Session]:
    if _factory is None:
        init_db()
    assert _factory is not None
    return _factory


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_factory()() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """For the worker and scripts: commit on success, roll back on error."""
    with session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
