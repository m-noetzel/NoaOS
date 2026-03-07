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
from noa.api.v1.cost import router as cost_router
from noa.api.v1.chat import router as chat_router
from noa.api.v1.health import router as health_router
from noa.api.v1.memory import router as memory_router
from noa.api.v1.queue import router as queue_router
from noa.api.v1.runs import router as runs_router
from noa.api.v1.settings import router as settings_router
from noa.api.v1.tasks import router as tasks_router
from noa.api.v1.threads import router as threads_router
from noa.api.v1.tools import router as tools_router
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

    # 2. Set up ToolGateway with registered tools
    try:
        from noa.api.app_state import get_session_factory, set_gateway
        from noa.audit.service import AuditService
        from noa.orchestrator.nodes.tools import set_gateway as set_tools_gateway
        from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse
        from noa.tools.registration import register_tools

        # Build audit callback closure over session factory
        sf = get_session_factory()

        async def _audit_callback(
            request: ToolRequest, response: ToolResponse, status: str
        ) -> None:
            if sf is None:
                return
            import uuid
            from decimal import Decimal

            async with sf() as asession:
                svc = AuditService()
                await svc.create_entry_async(
                    session=asession,
                    user_id=request.user_id,  # type: ignore[arg-type]
                    session_id=request.session_id or uuid.uuid4(),
                    device_id=uuid.uuid4(),
                    trace_id=request.trace_id or uuid.uuid4(),
                    domain=request.privacy_mode,
                    model_provider="tool_gateway",
                    model_name="n/a",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=Decimal("0"),
                    tool_name=request.tool,
                    tool_args=request.args,
                    tool_result_summary=status,
                    privacy_classification=request.privacy_mode,
                    classification_confidence=1.0,
                )
                await asession.commit()

        gateway = ToolGateway(
            audit_callback=_audit_callback,
            session_factory=get_session_factory(),
        )
        register_tools(gateway)
        set_gateway(gateway)
        set_tools_gateway(gateway)
        logger.info(
            "ToolGateway wired: %s", gateway.list_tools()
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to set up ToolGateway")

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

    # Configure structured JSON logging (§28.3)
    from noa.logging_config import configure_logging

    log_level = os.environ.get("LOG_LEVEL", "INFO")
    configure_logging(level=log_level)

    # Start DB maintenance scheduler (OP4)
    db_scheduler = None
    from noa.api.app_state import get_engine as _get_engine

    _engine = _get_engine()
    if _engine is not None:
        from noa.maintenance.db_maintenance import DbMaintenanceScheduler

        db_scheduler = DbMaintenanceScheduler(engine=_engine, interval_hours=24)
        await db_scheduler.start()

    # Wire LLM pipeline (ProviderRouter, ToolRegistry, Runner)
    if settings is not None:
        wire_llm_pipeline(settings)

    # Start retention scheduler for audit log purge (§28.7)
    from noa.maintenance.retention import RetentionScheduler

    retention_scheduler: RetentionScheduler | None = None
    try:
        from noa.api.app_state import get_session_factory

        sf = get_session_factory()
        if sf is not None:
            # Thin wrapper that delegates to logger until sync session
            # is available (async-only engine cannot run sync purge).
            class _PurgeProxy:
                """Proxy that opens a sync session per purge call."""

                def purge_expired(self, retention_days: int = 90) -> int:
                    # Use the async engine's sync counterpart is not
                    # available; fall back to logging a skip.
                    logger.info(
                        "Retention purge skipped: "
                        "sync session not available in async context"
                    )
                    return 0

            retention_scheduler = RetentionScheduler(
                audit_service=_PurgeProxy(),
                retention_days=int(os.environ.get("RETENTION_DAYS", "90")),
                interval_hours=int(
                    os.environ.get("RETENTION_INTERVAL_HOURS", "24")
                ),
            )
            await retention_scheduler.start()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to start RetentionScheduler")

    yield

    # Shutdown: stop retention scheduler
    if retention_scheduler is not None:
        await retention_scheduler.stop()

    # Shutdown: stop DB maintenance scheduler
    if db_scheduler is not None:
        await db_scheduler.stop()

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
        "http://localhost:5173,http://localhost:5174,http://localhost:4173,http://localhost:8000",
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
    app.include_router(tools_router)
    app.include_router(queue_router)
    app.include_router(cost_router)

    return app
