"""Run Alembic migrations from code (used at start-up on SQLite and by tests)."""

from __future__ import annotations

from alembic.config import Config

from alembic import command
from app.config import API_DIR


def upgrade_to_head() -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False  # keep our own structured logging
    command.upgrade(cfg, "head")


if __name__ == "__main__":  # python -m app.migrate  (Postgres migrations are applied explicitly, never at start-up)
    from app.config import get_settings

    upgrade_to_head()
    print("Migrations applied to", get_settings().database_url.split("@")[-1].split("?")[0])
