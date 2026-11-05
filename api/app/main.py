from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db, session_scope
from app.errors import register_error_handlers
from app.logging_config import configure_logging
from app.migrate import upgrade_to_head
from app.seed import seed_rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    if settings.database_url.startswith("sqlite"):
        upgrade_to_head()  # Postgres migrations are applied explicitly (Phase 3)
    init_db()
    with session_scope() as session:
        seed_rules(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Samaritan API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
