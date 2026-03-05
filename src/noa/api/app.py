"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from noa.api.middleware import RequestIDMiddleware, register_error_handlers
from noa.api.v1.approvals import router as approvals_router
from noa.api.v1.artifacts import router as artifacts_router
from noa.api.v1.auth import router as auth_router
from noa.api.v1.chat import router as chat_router
from noa.api.v1.health import router as health_router
from noa.api.v1.memory import router as memory_router
from noa.api.v1.runs import router as runs_router
from noa.api.v1.settings import router as settings_router
from noa.api.v1.tasks import router as tasks_router
from noa.api.v1.threads import router as threads_router
from noa.api.v1.usage import router as usage_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown resources."""
    # Startup: initialise DB engine (optional — skip in tests if no DB)
    try:
        from noa.config import Settings

        settings = Settings()
        from noa.db.engine import (
            async_session_factory,
            create_async_engine_from_config,
        )

        engine = create_async_engine_from_config(settings)
        factory = async_session_factory(engine)

        from noa.api.app_state import set_engine, set_session_factory

        set_engine(engine)
        set_session_factory(factory)
    except Exception:  # noqa: BLE001, S110
        pass  # Allow running without DB for health-only testing

    yield

    # Shutdown: dispose engine if present
    from noa.api.app_state import get_engine

    shutdown_engine = get_engine()
    if shutdown_engine is not None:
        await shutdown_engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Noa",
        description="Noa — governed personal AI agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    # §29.4: LAN/VPN only — restrict CORS to known origins
    allowed_origins = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://localhost:8000",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # Error handlers
    register_error_handlers(app)

    # Mount routers
    # Top-level health routes (for /health, /health/ready, /health/metrics)
    app.include_router(health_router)
    # Versioned API routes
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router)
    app.include_router(runs_router)
    app.include_router(approvals_router)
    app.include_router(chat_router)
    app.include_router(threads_router)
    app.include_router(memory_router)
    app.include_router(settings_router)
    app.include_router(usage_router)
    app.include_router(tasks_router)
    app.include_router(artifacts_router)

    return app
