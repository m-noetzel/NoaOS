"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from noa.api.middleware import RequestIDMiddleware, register_error_handlers
from noa.api.v1.approvals import router as approvals_router
from noa.api.v1.artifacts import router as artifacts_router
from noa.api.v1.audit import router as audit_router
from noa.api.v1.auth import router as auth_router
from noa.api.v1.chat import router as chat_router
from noa.api.v1.health import router as health_router
from noa.api.v1.memory import router as memory_router
from noa.api.v1.runs import router as runs_router
from noa.api.v1.settings import router as settings_router
from noa.api.v1.tasks import router as tasks_router
from noa.api.v1.threads import router as threads_router
from noa.api.v1.usage import router as usage_router

logger = logging.getLogger(__name__)


def wire_llm_pipeline(settings: Any) -> None:
    """Build and wire ProviderRouter, ToolRegistry, and OrchestratorRunner.

    Called during app lifespan startup. Gracefully degrades if no
    LLM API keys are configured (logs warning, doesn't crash).
    """
    from noa.api.app_state import set_provider_router, set_runner
    from noa.orchestrator.nodes.agent import set_router as set_agent_router

    # 1. Build ProviderRouter from settings
    try:
        from noa.external_worker.llm.router import ProviderRouter

        router = ProviderRouter.from_settings(settings)
        set_provider_router(router)
        set_agent_router(router)
        logger.info(
            "LLM pipeline wired: providers=%s",
            router.available_providers,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to build ProviderRouter — LLM calls will fail",
        )
        return

    # 2. Set up ToolRegistry on tools module (if tools available)
    try:
        from noa.orchestrator.nodes.tools import set_registry
        from noa.tools.interface import ToolRegistry

        # Build registry from available tool implementations
        tools: dict[str, Any] = {}
        # Future phases will register real tools here
        if tools:
            registry = ToolRegistry(tools)
            set_registry(registry)
            logger.info("ToolRegistry wired: %s", registry.list_tools())
        else:
            logger.info("No tools registered yet — tool calls will use fallback")
    except Exception:  # noqa: BLE001
        logger.warning("Failed to set up ToolRegistry")

    # 3. Build OrchestratorRunner with compiled graph
    try:
        from noa.orchestrator.graph import build_graph
        from noa.orchestrator.runner import OrchestratorRunner

        graph = build_graph().compile()
        runner = OrchestratorRunner(graph=graph)
        set_runner(runner)
        logger.info("OrchestratorRunner wired and ready")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to build OrchestratorRunner — chat will not work",
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown resources."""
    # Startup: initialise DB engine (optional — skip in tests if no DB)
    settings = None
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

    # Start private-container health checker (§17.1)
    from noa.api.app_state import set_health_checker
    from noa.queue.health import HealthChecker

    private_url = os.environ.get(
        "PRIVATE_WORKER_HEALTH_URL", "http://private-worker:8001/health"
    )
    checker = HealthChecker(poll_url=private_url)
    set_health_checker(checker)
    await checker.start()

    # Wire LLM pipeline (ProviderRouter, ToolRegistry, Runner)
    if settings is not None:
        wire_llm_pipeline(settings)

    yield

    # Shutdown: stop health checker, dispose engine
    await checker.stop()

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
    app.include_router(audit_router)

    return app
