from __future__ import annotations

import pytest

from app import db as db_module
from app.config import get_settings
from app.migrate import upgrade_to_head
from app.storage import get_storage


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own database and audio folder and never sees the real keys in api/.env."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("LOCAL_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("GNANI_API_KEY", "test-gnani-key-0000")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-0000")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-0000")
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-model")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("UPLOAD_PASSCODE", "")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("LLM_CACHE", "on")
    get_settings.cache_clear()
    get_storage.cache_clear()
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
