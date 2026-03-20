"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from noa.api.middleware import RequestIDMiddleware, register_error_handlers
from noa.api.v1.analytics import router as analytics_router
from noa.api.v1.approvals import router as approvals_router
from noa.api.v1.artifacts import router as artifacts_router
from noa.api.v1.audit import router as audit_router
from noa.api.v1.auth import router as auth_router
from noa.api.v1.chat import router as chat_router
from noa.api.v1.cost import router as cost_router
from noa.api.v1.devices import router as devices_router
from noa.api.v1.health import router as health_router
from noa.api.v1.memory import router as memory_router
from noa.api.v1.queue import router as queue_router
from noa.api.v1.ratings import router as ratings_router
from noa.api.v1.runs import router as runs_router
from noa.api.v1.settings import router as settings_router
from noa.api.v1.tasks import router as tasks_router
from noa.api.v1.threads import router as threads_router
from noa.api.v1.tools import router as tools_router
from noa.api.v1.usage import router as usage_router
from noa.api.v1.voice import router as voice_router
from noa.db.engine import async_session_factory, create_async_engine_from_config

logger = logging.getLogger(__name__)


def wire_llm_pipeline(settings: Any) -> None:
    """Build and wire ProviderRouter, ToolGateway, and OrchestratorRunner.

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

        # M7: Wire PolicyEngine for step-up auth enforcement
        try:
            from noa.policy.engine import PolicyEngine

            gateway.policy_engine = PolicyEngine()
        except Exception:  # noqa: BLE001
            logger.warning("PolicyEngine not available for step-up auth")

        register_tools(gateway)

        # CQ1: Wire DbCapabilityChecker into gateway for per-dispatch checks
        try:
            from noa.tools.capabilities import DbCapabilityChecker

            if sf is not None:
                gateway.capability_checker = DbCapabilityChecker(
                    session_factory=sf,
                )
                logger.info("DbCapabilityChecker wired to ToolGateway")
        except Exception:  # noqa: BLE001
            logger.warning("DbCapabilityChecker not available")

        # CQ1: Load custom tools from DB at startup
        try:
            from noa.tools.registration import load_custom_tools

            if sf is not None:
                import asyncio

                async def _load_custom() -> None:
                    assert sf is not None  # noqa: S101
                    async with sf() as session:
                        await load_custom_tools(gateway, session)
                    logger.info("Custom tools loaded from DB")

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_load_custom())
                except RuntimeError:
                    pass
        except Exception:  # noqa: BLE001
            logger.warning("Failed to load custom tools from DB")

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

        # A4: Use PostgresCheckpointer when DB is available
        from typing import Any as _Any
        sf = get_session_factory()
        checkpointer: _Any
        if sf is not None:
            from noa.orchestrator.checkpointer import PostgresCheckpointer
            checkpointer = PostgresCheckpointer(session_factory=sf)
            logger.info("PostgresCheckpointer wired for run state persistence")
        else:
            from noa.orchestrator.checkpointer import NoOpCheckpointer
            checkpointer = NoOpCheckpointer()

        runner = OrchestratorRunner(graph=graph, checkpointer=checkpointer)
        set_runner(runner)
        logger.info("OrchestratorRunner wired and ready")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to build OrchestratorRunner — chat will not work",
        )


async def _probe_worker(url: str, name: str) -> bool:
    """Probe a worker health endpoint at startup.

    Returns True if the worker is healthy, False if unreachable or unhealthy.
    Never raises — startup must always proceed.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            healthy = resp.status_code < 500
            if not healthy:
                logger.warning(
                    "Worker %s returned HTTP %s — marking degraded",
                    name,
                    resp.status_code,
                )
            return healthy
    except httpx.TransportError as exc:
        logger.warning(
            "Worker %s unreachable at startup (%s) — marking degraded",
            name,
            exc,
        )
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown resources."""
    # Startup: initialise DB engine (optional — skip in tests if no DB)
    settings = None
    try:
        from noa.config import Settings

        settings = Settings()

        engine = create_async_engine_from_config(settings)
        factory = async_session_factory(engine)

        from noa.api.app_state import set_engine, set_session_factory

        set_engine(engine)
        set_session_factory(factory)
    except Exception:  # noqa: BLE001
        logger.warning(
            "DB engine creation failed — running without database",
            exc_info=True,
        )

    # Start private-container health checker (§17.1)
    from noa.api.app_state import set_health_checker
    from noa.queue.health import HealthChecker

    private_url = os.environ.get(
        "PRIVATE_WORKER_HEALTH_URL", "http://private-worker:8001/health"
    )
    checker = HealthChecker(poll_url=private_url)
    set_health_checker(checker)
    await checker.start()

    # DE3: Startup probe — log WARNING and set workers_degraded if any worker is down
    private_worker_url = os.environ.get(
        "PRIVATE_WORKER_HEALTH_URL", "http://private-worker:8001/health"
    )
    external_worker_url = os.environ.get(
        "EXTERNAL_WORKER_HEALTH_URL", "http://external-worker:8002/health"
    )
    private_ok = await _probe_worker(private_worker_url, "private-worker")
    external_ok = await _probe_worker(external_worker_url, "external-worker")
    app.state.workers_degraded = not (private_ok and external_ok)
    if app.state.workers_degraded:
        logger.warning(
            "One or more workers unreachable at startup — "
            "private_ok=%s external_ok=%s",
            private_ok,
            external_ok,
        )
    else:
        logger.info("All workers healthy at startup")

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

    # Wire both MemoryStores BEFORE wire_llm_pipeline() — register_tools() reads
    # them from app_state when wiring the memory and external_memory tools.
    # Private store: shared in-process in dev (§13.2)
    try:
        from noa.api.app_state import set_memory_store
        from noa.private_worker.handlers import _memory_store as _ms  # noqa: PLC2701

        set_memory_store(_ms)
        logger.info("MemoryStore wired to API")
    except Exception:  # noqa: BLE001
        logger.warning("MemoryStore not available — memory endpoints will return empty")

    # External store: separate namespace under /data/memory/external (BE-H9).
    # Imported from noa.external_worker.handlers to avoid API→private_worker import.
    try:
        from noa.api.app_state import set_external_memory_store  # noqa: I001
        from noa.external_worker.handlers import _memory_store as _ext_ms  # noqa: PLC2701

        set_external_memory_store(_ext_ms)
        logger.info("External MemoryStore wired to API")
    except Exception:  # noqa: BLE001
        logger.warning("External MemoryStore not available")

    # Wire LLM pipeline (ProviderRouter, ToolRegistry, Runner).
    # Memory stores must be wired above before this call — register_tools()
    # inside wire_llm_pipeline reads both stores from app_state.
    if settings is not None:
        wire_llm_pipeline(settings)

    # Wire APNs push notification service (§29.5)
    apns_http_client = None
    if settings is not None and settings.apns_key_id:
        missing = [
            name
            for name, val in [
                ("APNS_TEAM_ID", settings.apns_team_id),
                ("APNS_KEY_PATH", settings.apns_key_path),
                ("APNS_BUNDLE_ID", settings.apns_bundle_id),
            ]
            if not val
        ]
        if missing:
            logger.error(
                "APNs misconfigured — APNS_KEY_ID is set but missing: %s. "
                "Push notifications will be disabled.",
                ", ".join(missing),
            )
        else:
            import httpx

            from noa.api.app_state import set_apns_service
            from noa.push.apns import APNsService

            # All required fields are non-empty (checked via `missing` above)
            apns = APNsService(
                key_id=settings.apns_key_id or "",
                team_id=settings.apns_team_id or "",
                key_path=settings.apns_key_path or "",
                bundle_id=settings.apns_bundle_id or "",
            )
            apns_http_client = httpx.AsyncClient(http2=True, timeout=10.0)
            apns.initialize(apns_http_client)
            set_apns_service(apns)
            logger.info("APNs push notification service initialised")

    # Start retention scheduler for audit log purge (§28.7)
    from noa.maintenance.retention import RetentionScheduler

    retention_scheduler: RetentionScheduler | None = None
    try:
        from noa.api.app_state import get_session_factory

        sf = get_session_factory()
        if sf is not None:
            from sqlalchemy.orm import Session as _SyncSession

            from noa.audit.service import AuditService
            from noa.policy.approval import ApprovalService

            session: _SyncSession = sf()  # type: ignore[assignment]
            audit_svc = AuditService(session=session)
            approval_svc = ApprovalService(session=session)

            retention_scheduler = RetentionScheduler(
                audit_service=audit_svc,
                retention_days=int(os.environ.get("RETENTION_DAYS", "90")),
                interval_hours=int(
                    os.environ.get("RETENTION_INTERVAL_HOURS", "24")
                ),
                approval_service=approval_svc,
            )
            await retention_scheduler.start()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to start RetentionScheduler")

    # MVP-H3: Start queue drain worker (drains private tasks when domain recovers)
    drain_worker = None
    try:
        from noa.api.app_state import get_runner as _get_runner
        from noa.api.app_state import get_session_factory as _gsf
        from noa.queue.drain import QueueDrainWorker

        _drain_sf = _gsf()
        if _drain_sf is not None:
            drain_worker = QueueDrainWorker(
                session_factory=_drain_sf,
                health_checker=checker,
                runner=_get_runner(),
            )
            await drain_worker.start()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to start QueueDrainWorker")

    yield

    # Shutdown: stop queue drain worker
    if drain_worker is not None:
        await drain_worker.stop()

    # Shutdown: close APNs HTTP client
    if apns_http_client is not None:
        await apns_http_client.aclose()

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
    # Eagerly attempt DB engine creation for observability (H5).
    # This is best-effort — the real DB setup happens in lifespan().
    try:
        from noa.config import Settings as _Settings

        _s = _Settings()
        create_async_engine_from_config(_s)
    except Exception:  # noqa: BLE001
        logger.warning(
            "DB engine creation failed during app init — running without database",
            exc_info=True,
        )

    # W21-M1: Gate OpenAPI docs behind NOA_ENV — never expose in production.
    # NOA_ENV is the canonical environment variable (used by Settings.noa_env).
    # ENVIRONMENT is also accepted for backward compatibility.
    # If EITHER is "production", suppress docs.
    _noa_env = os.environ.get("NOA_ENV", "").lower()
    _env_var = os.environ.get("ENVIRONMENT", "").lower()
    _is_production = _noa_env == "production" or _env_var == "production"
    app = FastAPI(
        title="Noa",
        description="Noa — governed personal AI agent",
        version="0.1.0",
        lifespan=lifespan,
        # M2 / W21-M1: Hide OpenAPI docs in production — reduces attack surface
        docs_url=None if _is_production else "/docs",
        redoc_url=None if _is_production else "/redoc",
        openapi_url=None if _is_production else "/openapi.json",
    )

    # A1: Register app instance for app.state-backed DI
    from noa.api.app_state import set_app
    set_app(app)

    # Middleware (order matters — outermost first)
    # §29.4: LAN/VPN only — restrict CORS to known origins
    allowed_origins_raw = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:4173,http://localhost:8000",
    ).split(",")
    # DE2: Add NOA_DOMAIN HTTPS origin when set (required for OAuth2 redirect URIs)
    noa_domain = os.environ.get("NOA_DOMAIN", "").strip()
    if noa_domain and noa_domain != "localhost":
        allowed_origins_raw.append(f"https://{noa_domain}")
    # M2: Reject wildcard origins — credentials require explicit origins
    allowed_origins = [
        o.strip() for o in allowed_origins_raw
        if o.strip() and o.strip() != "*"
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization", "Content-Type", "Accept",
            "Idempotency-Key", "X-Trace-ID", "X-CSRF-Token",
        ],
    )
    app.add_middleware(RequestIDMiddleware)

    # Content-Security-Policy and security headers middleware (M4, M5)
    class CSPMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Any, call_next: Any) -> Any:  # noqa: ANN401
            response = await call_next(request)
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

    app.add_middleware(CSPMiddleware)

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
    app.include_router(devices_router)
    app.include_router(ratings_router)
    app.include_router(analytics_router)
    app.include_router(voice_router, prefix="/api/v1/voice")

    return app


# Lazy module-level ``app`` so that ``from noa.api.app import app``
# works AND patches applied *before* the import are honoured (QC3 / H5).
_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
