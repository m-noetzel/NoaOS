"""FastAPI application factory with lifespan management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from starlette.middleware.cors import CORSMiddleware

from noa.api.middleware import RequestIDMiddleware, register_error_handlers
from noa.api.v1.auth import router as auth_router
from noa.api.v1.health import router as health_router
from noa.api.v1.runs import router as runs_router


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
    # Auth routes
    app.include_router(auth_router)
    # Runs routes (SSE streaming per §22.4)
    app.include_router(runs_router)

    # Protected chat stub (used by auth tests to verify middleware)
    from noa.auth.middleware import require_auth

    _chat_router = APIRouter(prefix="/api/v1", tags=["chat"])

    @_chat_router.post("/chat")
    async def chat_stub(
        payload: dict[str, Any] = Depends(require_auth),  # noqa: B008
    ) -> dict[str, Any]:
        return {"ok": True, "data": {"message": "stub"}}

    app.include_router(_chat_router)

    return app
