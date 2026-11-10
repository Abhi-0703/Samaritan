from __future__ import annotations

import os

import pytest

from app import db as db_module
from app.config import get_settings
from app.migrate import upgrade_to_head
from app.storage import get_storage


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory):
    """`TEST_PG=1 pytest` runs the whole suite on a throwaway local Postgres (pgserver) instead of SQLite."""
    if not os.environ.get("TEST_PG"):
        yield None
        return
    import pgserver

    server = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    yield server.get_uri()
    server.cleanup()  # stop it now, while logging still works


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch, pg_url):
    """Every test gets its own database and audio folder and never sees the real keys in api/.env."""
    if pg_url:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            pg_url.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT"
        )
        with engine.connect() as conn:  # a clean schema per test
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        engine.dispose()
        monkeypatch.setenv("DATABASE_URL", pg_url)
    else:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_BACKEND", "local")  # never the real Supabase bucket, whatever api/.env says
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("LOCAL_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("GNANI_API_KEY", "test-gnani-key-0000")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-0000")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-0000")
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-model")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("UPLOAD_PASSCODE", "")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("LLM_CACHE", "on")
    monkeypatch.setenv("WORKER_ENABLED", "false")  # tests drain the queue themselves
    get_settings.cache_clear()
    get_storage.cache_clear()
    if pg_url:  # the app applies Postgres migrations explicitly, not at start-up
        upgrade_to_head()
    yield
    get_settings.cache_clear()
    get_storage.cache_clear()
    db_module._engine = None
    db_module._factory = None


@pytest.fixture
def session():
    """A session on a freshly migrated database, with the nine rules seeded."""
    from app.seed import seed_rules

    upgrade_to_head()
    db_module.init_db()
    with db_module.session_scope() as s:
        seed_rules(s)
    with db_module.session_factory()() as s:
        yield s


@pytest.fixture
def gnani_fake():
    from tests.fakes.gnani_fake import FakeGnani

    return FakeGnani(api_key="test-gnani-key-0000")


@pytest.fixture
def llm_fake():
    from tests.fakes.llm_fake import FakeProvider, answer

    return FakeProvider(responses=[answer()])


@pytest.fixture
def runtime(session, gnani_fake, llm_fake):
    """Everything the app needs, with fakes in place of Gnani and the LLM."""
    from app.detection.llm_judge import PROMPT_VERSION
    from app.runtime import Runtime, make_worker
    from app.services.gnani_client import GnaniBatchClient
    from app.services.llm.cache import DbLlmCache
    from app.services.llm.limiter import TokenLimiter
    from app.services.llm.service import LLMService
    from app.storage import get_storage

    settings = get_settings()
    gnani = GnaniBatchClient(
        "https://api.vachana.ai", "test-gnani-key-0000", http=gnani_fake.client(), sleep=lambda s: None
    )
    llm = LLMService(
        llm_fake, None, {llm_fake.name: TokenLimiter(1000, 10_000_000, sleep=lambda s: None)},
        DbLlmCache(db_module.session_scope, settings.llm_cache), PROMPT_VERSION, sleep=lambda s: None,
    )  # fmt: skip
    storage = get_storage()
    return Runtime(settings, gnani, llm, storage, make_worker(settings, gnani, llm, storage))


@pytest.fixture
def client(runtime):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(lambda s: runtime)) as c:
        yield c
