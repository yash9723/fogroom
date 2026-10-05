"""FOGROOM API application."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.redis import get_redis, redis_state
from app.db.session import db
from app.realtime import ws
from app.realtime.bus import subscribe_forever
from app.realtime.manager import manager
from app.scenario.runner import runner

logger = logging.getLogger("fogroom")

DESCRIPTION = """
**FOGROOM - Decision Training Under Information Uncertainty** (SIH26248)

Multiplayer simulation platform that trains teams to decide well when communications are
delayed, incomplete, contradictory or unavailable. Every participant has an independent
information state; the **Information-State Digital Twin** endpoints reconstruct exactly what
each participant knew at any moment for After Action Review.

All scenarios are fictional. Metrics are experimental training metrics.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    redis_state.init()
    stop = asyncio.Event()
    subscriber = asyncio.create_task(
        subscribe_forever(manager.dispatch, stop), name="redis-subscriber"
    )
    if settings.engine_autorun:
        await runner.resume_all()
    logger.info("FOGROOM API started (env=%s, demo_mode=%s)", settings.app_env, settings.demo_mode)
    try:
        yield
    finally:
        stop.set()
        subscriber.cancel()
        await asyncio.gather(subscriber, return_exceptions=True)
        await runner.shutdown()
        await redis_state.close()
        await db.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="FOGROOM API",
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "auth", "description": "Registration, login, token rotation"},
            {"name": "scenarios", "description": "Scenario templates (instructor)"},
            {"name": "rooms", "description": "Training rooms, lobby and exercise lifecycle"},
            {
                "name": "live",
                "description": "Live state for instructor and trainees, reconnect sync",
            },
            {
                "name": "controls",
                "description": "Instructor live controls (degradation, events, notes)",
            },
            {"name": "trainee", "description": "Decisions, acknowledgements, team communication"},
            {
                "name": "aar",
                "description": "Information-State Digital Twin, decision inspection, AAR",
            },
            {"name": "analytics", "description": "Dashboard and cross-exercise analytics"},
            {"name": "admin", "description": "User administration"},
        ],
    )
    register_error_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router)
    app.include_router(ws.router)

    @app.get("/health", tags=["health"], summary="Liveness / readiness")
    async def health() -> dict[str, Any]:
        checks = {"database": "ok", "redis": "ok"}
        try:
            async with db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            checks["database"] = "error"
        try:
            await get_redis().ping()
        except Exception:
            checks["redis"] = "error"
        return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded", **checks}

    # Single-service deploy: serve the static-exported frontend; mounted last so API routes win.
    if settings.web_static_dir and Path(settings.web_static_dir).is_dir():
        app.mount("/", StaticFiles(directory=settings.web_static_dir, html=True), name="web")

    return app


app = create_app()
