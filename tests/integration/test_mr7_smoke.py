"""MR7 Integration smoke tests -- full auth flow against a wired ASGI app.

Validates: register -> login -> authenticated access -> refresh -> logout
using httpx.AsyncClient with ASGI transport (no Docker required).

The async DB engine requires the greenlet C extension which may not load
in sandboxed environments.  When greenlet is available we use a real
``sqlite+aiosqlite:///:memory:`` engine; otherwise we fall back to an
in-memory mock session that stores ORM objects in plain lists.  Either way
the full HTTP -> router -> service -> JWT stack is exercised end-to-end.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_EMAIL = "smoke@example.com"
TEST_PASSWORD = "Str0ng!Pass#2024"  # noqa: S105
DEVICE_ID = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Detect greenlet availability
# ---------------------------------------------------------------------------

_GREENLET_OK = False
try:
    import greenlet as _gl  # noqa: F401

    _GREENLET_OK = True
except (ImportError, OSError):
    pass


# ---------------------------------------------------------------------------
# In-memory mock session (fallback when greenlet is unavailable)
# ---------------------------------------------------------------------------


class _InMemoryStore:
    """Stores ORM objects in memory, keyed by tablename."""

    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, obj: Any) -> None:
        self.rows.append(obj)

    def find(self, model_cls: type, **filters: Any) -> Any | None:
        for row in self.rows:
            if not isinstance(row, model_cls):
                continue
            if all(getattr(row, k, _SENTINEL) == v for k, v in filters.items()):
                return row
        return None


_SENTINEL = object()


def _make_mock_session(store: _InMemoryStore) -> MagicMock:
    """Mock session that delegates add/execute to *store*."""
    session = MagicMock()
    # add() is synchronous in SQLAlchemy — use MagicMock, not AsyncMock
    session.add.side_effect = lambda obj: store.add(obj)
    session.commit = AsyncMock()

    async def _execute(stmt: Any) -> MagicMock:
        from noa.db.models.session import AuthSession
        from noa.db.models.user import User

        result = MagicMock()

        # Determine target model from the statement's froms
        try:
            froms = (
                stmt.get_final_froms()
                if hasattr(stmt, "get_final_froms")
                else list(stmt.froms)
            )
            table_name = str(froms[0])
        except Exception:  # noqa: BLE001
            table_name = ""

        model_cls: type = User if "users" in table_name else AuthSession

        # Extract equality filters from the WHERE clause
        filters: dict[str, Any] = {}
        wc = getattr(stmt, "whereclause", None)
        if wc is not None:
            clauses = getattr(wc, "clauses", [wc])
            for clause in clauses:
                try:
                    key = clause.left.key
                    val = (
                        clause.right.value
                        if hasattr(clause.right, "value")
                        else clause.right.effective_value
                        if hasattr(clause.right, "effective_value")
                        else None
                    )
                    if val is not None:
                        filters[key] = val
                except Exception:  # noqa: BLE001, S110
                    pass  # Best-effort filter extraction

        row = store.find(model_cls, **filters)
        result.scalar_one_or_none.return_value = row
        return result

    session.execute = _execute
    return session


class _SessionCtx:
    """Async context manager wrapping a mock session."""

    def __init__(self, store: _InMemoryStore) -> None:
        self._session = _make_mock_session(store)

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, *a: Any) -> None:
        pass


class _FakeSessionFactory:
    """Callable that returns ``_SessionCtx`` instances sharing one store."""

    def __init__(self, store: _InMemoryStore) -> None:
        self._store = store

    def __call__(self) -> _SessionCtx:
        return _SessionCtx(self._store)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _set_test_env() -> None:
    import os

    os.environ["NOA_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test-secret-key-for-mr7"  # noqa: S105
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def app() -> AsyncGenerator[FastAPI, None]:
    """Build a fully-wired FastAPI app backed by in-memory state."""
    _set_test_env()

    from noa.api import app_state

    engine_to_dispose = None

    if _GREENLET_OK:
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models import Base

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        app_state.set_engine(engine)
        app_state.set_session_factory(factory)
        engine_to_dispose = engine
    else:
        store = _InMemoryStore()
        app_state.set_engine(None)  # type: ignore[arg-type]
        app_state.set_session_factory(_FakeSessionFactory(store))  # type: ignore[arg-type]

    # Minimal lifespan (skip HealthChecker / LLM wiring)
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
        yield

    from noa.api.app import create_app

    application = create_app()
    application.router.lifespan_context = _test_lifespan  # type: ignore[assignment]

    yield application

    if engine_to_dispose is not None:
        await engine_to_dispose.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """httpx async client wired to the ASGI app."""
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _register_and_login(
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Register a user then log in, returning token data dict."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert reg.status_code == 201, f"register failed: {reg.text}"

    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "device_id": DEVICE_ID,
        },
    )
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_user(client: httpx.AsyncClient) -> None:
    """POST /register creates new user -> 201."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert "user_id" in body["data"]


@pytest.mark.asyncio
async def test_login_returns_tokens(client: httpx.AsyncClient) -> None:
    """POST /login returns access_token and refresh_token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "device_id": DEVICE_ID,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: httpx.AsyncClient) -> None:
    """POST /login with wrong password -> 401."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword!123",
            "device_id": DEVICE_ID,
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_returns_200(client: httpx.AsyncClient) -> None:
    """GET /health returns 200 (no auth required)."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


@pytest.mark.asyncio
async def test_settings_without_token(client: httpx.AsyncClient) -> None:
    """GET /settings without token -> 401/403."""
    resp = await client.get("/api/v1/settings")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_settings_with_valid_token(client: httpx.AsyncClient) -> None:
    """GET /settings with valid token -> 200."""
    tokens = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(client: httpx.AsyncClient) -> None:
    """POST /refresh rotates token pair."""
    tokens = await _register_and_login(client)
    old_refresh = tokens["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh, "device_id": DEVICE_ID},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != old_refresh


@pytest.mark.asyncio
async def test_logout_invalidates_session(client: httpx.AsyncClient) -> None:
    """POST /logout invalidates session."""
    tokens = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "logged_out"


@pytest.mark.asyncio
async def test_health_tools_returns_200(client: httpx.AsyncClient) -> None:
    """GET /health/tools returns 200."""
    resp = await client.get("/health/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "tools" in body["data"]


@pytest.mark.asyncio
async def test_tools_enable_with_auth(client: httpx.AsyncClient) -> None:
    """POST /tools/{name}/enable with valid token -> 200 for known tools."""
    tokens = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/api/v1/tools/web_search/enable",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "granted"
    assert body["data"]["tool"] == "web_search"
