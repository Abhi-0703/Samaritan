from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.config import Settings, get_settings
from app.db import get_engine, init_db, session_scope
from app.errors import register_error_handlers
from app.guards import RateLimiter
from app.logging_config import configure_logging
from app.migrate import upgrade_to_head
from app.routers import agents, calls, evaluation, rules, stats, violations
from app.runtime import Runtime, build_runtime
from app.seed import seed_rules


def create_app(runtime_factory: Callable[[Settings], Runtime] | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings)
        if settings.database_url.startswith("sqlite"):
            upgrade_to_head()  # Postgres migrations are applied explicitly (Phase 3)
        init_db()
        if not settings.database_url.startswith("sqlite") and "rules" not in inspect(get_engine()).get_table_names():
            raise RuntimeError("The database has no tables yet. Run `python -m app.migrate` once, then start the API.")
        with session_scope() as session:
            seed_rules(session)
        runtime = (runtime_factory or build_runtime)(settings)
        app.state.runtime = runtime
        runtime.worker.resume_unfinished()  # free hosts sleep and restart: pick up unfinished calls
        if settings.worker_enabled:
            runtime.worker.start()
        yield
        runtime.worker.stop()

    app = FastAPI(title="Samaritan API", version="0.1.0", lifespan=lifespan)
    app.state.rate_limiter = RateLimiter(limit=10, window_s=3600)
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

    for module in (calls, violations, agents, rules, stats, evaluation):
        app.include_router(module.router)
    return app


app = create_app()
