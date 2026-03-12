"""Postgres integration test fixtures.

Uses a real PostgreSQL database for integration tests.

Priority order for the database URL:
  1. TEST_DATABASE_URL env var (set when the existing postgres container is
     available, e.g. ``postgresql+asyncpg://noa:kindness@postgres:5432/noa_test``)
  2. testcontainers-managed Postgres (spun up automatically in CI environments
     that support Docker-in-Docker)

The database is created once per test session and all tables are created via
Alembic migrations so the full migration chain is exercised.
"""

from __future__ import annotations

import atexit
import asyncio
import concurrent.futures
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve Postgres URL
# ---------------------------------------------------------------------------

_PG_URL: str | None = None


def _resolve_pg_url() -> str:
    """Return the async Postgres URL for integration tests."""
    global _PG_URL  # noqa: PLW0603
    if _PG_URL is not None:
        return _PG_URL

    # 1. Prefer an explicit TEST_DATABASE_URL env var
    explicit = os.environ.get("TEST_DATABASE_URL", "")
    if explicit:
        _PG_URL = explicit
        return _PG_URL

    # 2. Fall back to testcontainers
    try:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

        _pg_container = PostgresContainer("postgres:16-alpine")
        _pg_container.start()
        atexit.register(_pg_container.stop)
        # testcontainers returns a sync URL; convert to asyncpg driver
        sync_url = _pg_container.get_connection_url()
        async_url = sync_url.replace("psycopg2", "asyncpg").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        _PG_URL = async_url
        return _PG_URL
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "No TEST_DATABASE_URL env var set and testcontainers failed to start. "
            "Set TEST_DATABASE_URL=postgresql+asyncpg://... to run integration tests. "
            f"testcontainers error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Run Alembic migrations
# ---------------------------------------------------------------------------


def _run_migrations(url: str) -> None:
    """Run all Alembic migrations against *url* (sync call, session-scoped)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    # Drop all tables (including alembic_version) and recreate via migrations.
    async def _reset() -> None:
        import noa.settings.models  # noqa: F401 — registers UserSettings on Base
        from noa.db.models import Base  # noqa: I001 — must import after settings.models

        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            # Drop alembic_version so migrations run from scratch
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await engine.dispose()

    # Run in a fresh thread to avoid "event loop already running" under
    # pytest-asyncio auto mode, which manages an event loop at session scope.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _reset()).result()

    # Run all migrations from scratch
    command.upgrade(alembic_cfg, "head")


# ---------------------------------------------------------------------------
# Session-scoped Postgres fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url() -> str:
    """Return the async Postgres URL and ensure schema is migrated."""
    url = _resolve_pg_url()
    _run_migrations(url)
    return url


# ---------------------------------------------------------------------------
# Per-test app fixture
# ---------------------------------------------------------------------------


_ENV_KEYS = ("NOA_ENV", "SECRET_KEY", "DATABASE_URL")
_ORIGINAL_ENV: dict[str, str | None] = {}


def _patch_env(pg_url_str: str) -> None:
    """Save original env values and set integration test overrides."""
    for key in _ENV_KEYS:
        _ORIGINAL_ENV[key] = os.environ.get(key)
    os.environ["NOA_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "integration-test-secret-key"  # noqa: S105
    os.environ["DATABASE_URL"] = pg_url_str


def _restore_env() -> None:
    """Restore env to pre-test state."""
    for key in _ENV_KEYS:
        original = _ORIGINAL_ENV.get(key)
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original


def _make_test_app(pg_url_str: str) -> FastAPI:
    """Build a fully-wired FastAPI app backed by the given Postgres URL."""
    _patch_env(pg_url_str)

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    import noa.settings.models  # noqa: F401,I001 — register UserSettings on Base

    from noa.api import app_state

    engine = create_async_engine(pg_url_str)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app_state.set_engine(engine)
    app_state.set_session_factory(factory)

    # Wire MemoryStore directly (not in lifespan — httpx.ASGITransport does not
    # send lifespan events, so any setup done inside _test_lifespan won't run).
    try:
        from noa.private_worker.memory_store import MemoryStore

        app_state.set_memory_store(MemoryStore())
    except Exception:  # noqa: BLE001
        logger.warning("MemoryStore unavailable in integration test setup", exc_info=True)

    @asynccontextmanager
    async def _test_lifespan(_a: FastAPI) -> AsyncGenerator[None, None]:
        from noa.queue.health import HealthChecker

        checker = HealthChecker.__new__(HealthChecker)
        checker._available = False  # noqa: SLF001
        checker._task = None  # noqa: SLF001
        checker._history = []  # noqa: SLF001
        checker.start = AsyncMock()  # type: ignore[assignment]
        checker.stop = AsyncMock()  # type: ignore[assignment]
        app_state.set_health_checker(checker)
        _a.state.workers_degraded = False

        yield

    from noa.api.app import create_app

    application = create_app()
    application.router.lifespan_context = _test_lifespan  # type: ignore[assignment]
    return application


@pytest_asyncio.fixture
async def pg_app(pg_url: str) -> AsyncGenerator[FastAPI, None]:
    """Per-test FastAPI app wired to Postgres."""
    from noa.api import app_state

    app_state.reset_all()
    application = _make_test_app(pg_url)
    try:
        yield application
    finally:
        app_state.reset_all()
        _restore_env()


@pytest_asyncio.fixture
async def pg_client(pg_app: FastAPI) -> AsyncGenerator[Any, None]:
    """httpx AsyncClient wired to the Postgres-backed ASGI app."""
    import httpx

    transport = httpx.ASGITransport(app=pg_app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_PASSWORD = "Str0ng!Pass#2024"  # noqa: S105


async def register_and_login(client: Any, email: str) -> dict[str, Any]:
    """Register *email* and log in, returning token data dict."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert reg.status_code == 201, f"register failed: {reg.text}"

    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "device_id": "test-device-001",
        },
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["data"]  # type: ignore[no-any-return]
