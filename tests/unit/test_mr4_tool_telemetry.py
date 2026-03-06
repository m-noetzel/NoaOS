"""Tests for MR4: Tool Call Telemetry to DB.

Covers ToolCallLog model, DB persistence via session_factory,
list fallback, and /health/tools endpoint.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

# -------------------------------------------------------------------
# Fake adapter for gateway tests
# -------------------------------------------------------------------


class _FakeAdapter:
    """Minimal ToolAdapter for testing."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or {"ok": True}
        self._error = error

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self._error:
            return ToolResponse(error=self._error)
        return ToolResponse(result=self._result, provider="fake")


# ===================================================================
# 1. ToolCallLog model tests
# ===================================================================


class TestToolCallLogModel:
    """Test ToolCallLog SQLAlchemy model instantiation."""

    def test_instantiation_with_required_fields(self) -> None:
        from noa.db.models.tool_call_log import ToolCallLog

        log = ToolCallLog(
            tool="web_search",
            function="search",
            latency_ms=42.5,
            status="ok",
            cached=False,
            user_id=uuid.uuid4(),
        )
        assert log.tool == "web_search"
        assert log.function == "search"
        assert log.latency_ms == 42.5
        assert log.status == "ok"
        assert log.cached is False

    def test_timestamp_auto_set(self) -> None:
        from noa.db.models.tool_call_log import ToolCallLog

        log = ToolCallLog(
            tool="calendar",
            function="list_events",
            latency_ms=10.0,
            status="ok",
            cached=False,
        )
        # The default factory should produce a timestamp
        assert log.timestamp is not None
        assert isinstance(log.timestamp, datetime)

    def test_id_defaults_to_uuid(self) -> None:
        from noa.db.models.tool_call_log import ToolCallLog

        log = ToolCallLog(
            tool="gmail",
            function="send",
            latency_ms=100.0,
            status="ok",
            cached=False,
        )
        assert log.id is not None
        assert isinstance(log.id, uuid.UUID)


# ===================================================================
# 2. Migration test
# ===================================================================


class TestMigration:
    """Verify migration file creates tool_call_logs table."""

    def test_migration_creates_table(self) -> None:
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "alembic",
            "versions",
            "003_tool_call_log.py",
        )
        migration_path = os.path.abspath(migration_path)
        assert os.path.exists(migration_path), "Migration file must exist"

        with open(migration_path) as f:
            content = f.read()

        # Verify revision metadata
        assert 'revision: str = "003"' in content
        assert 'down_revision: str = "002"' in content
        # Verify it creates the tool_call_logs table
        assert "tool_call_logs" in content
        assert "def upgrade" in content
        assert "def downgrade" in content


# ===================================================================
# 3. ToolGateway telemetry persistence tests
# ===================================================================


class TestGatewayTelemetryFallback:
    """Without session_factory, gateway falls back to in-memory list."""

    def test_telemetry_fallback_to_list_without_factory(self) -> None:
        gw = ToolGateway()
        gw.register("web_search", _FakeAdapter())

        req = ToolRequest(tool="web_search", function="search", args={})
        asyncio.run(gw.dispatch(req))

        # Should still record to list
        assert len(gw.telemetry) == 1
        assert gw.telemetry[0]["tool"] == "web_search"

    def test_session_factory_stored_in_init(self) -> None:
        mock_factory = MagicMock()
        gw = ToolGateway(session_factory=mock_factory)
        assert gw._session_factory is mock_factory


class TestGatewayDBPersistence:
    """With session_factory, gateway persists telemetry to DB."""

    def test_db_write_called_on_dispatch(self) -> None:
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        gw = ToolGateway(session_factory=mock_factory)
        gw.register("web_search", _FakeAdapter())

        req = ToolRequest(tool="web_search", function="search", args={})
        asyncio.run(gw.dispatch(req))

        # Factory should have been called to create a session
        mock_factory.assert_called()
        # Session should have had add() and commit() called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    def test_db_error_does_not_fail_dispatch(self) -> None:
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=Exception("DB down"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        gw = ToolGateway(session_factory=mock_factory)
        gw.register("web_search", _FakeAdapter())

        req = ToolRequest(tool="web_search", function="search", args={})
        resp = asyncio.run(gw.dispatch(req))

        # Dispatch should succeed even though DB write failed
        assert resp.error is None
        assert resp.result == {"ok": True}
        # Should fall back to list
        assert len(gw.telemetry) >= 1


# ===================================================================
# 4. /health/tools endpoint tests
# ===================================================================


def _make_test_app() -> Any:
    """Create a minimal FastAPI app with health router for testing."""
    from fastapi import FastAPI

    from noa.api.v1.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)
    return app


class TestHealthToolsEndpoint:
    """Tests for GET /health/tools endpoint."""

    def test_returns_200(self) -> None:
        app = _make_test_app()
        client = TestClient(app)
        resp = client.get("/health/tools")
        assert resp.status_code == 200

    def test_returns_per_tool_stats(self) -> None:
        app = _make_test_app()
        gw = ToolGateway()
        gw.register("web_search", _FakeAdapter())

        # Dispatch a few calls to build telemetry
        for _ in range(3):
            req = ToolRequest(tool="web_search", function="search", args={})
            asyncio.run(gw.dispatch(req))

        with patch("noa.api.v1.health._get_gateway", return_value=gw):
            client = TestClient(app)
            resp = client.get("/health/tools")

        data = resp.json()
        assert data["ok"] is True
        tools_data = data["data"]["tools"]
        assert "web_search" in tools_data
        assert tools_data["web_search"]["call_count"] == 3

    def test_shows_error_rate(self) -> None:
        app = _make_test_app()
        gw = ToolGateway()
        gw.register("web_search", _FakeAdapter())
        gw.register("bad_tool", _FakeAdapter(error="fail"))

        # 2 ok + 2 error
        for _ in range(2):
            asyncio.run(
                gw.dispatch(
                    ToolRequest(tool="web_search", function="s", args={})
                )
            )
        for _ in range(2):
            asyncio.run(
                gw.dispatch(
                    ToolRequest(tool="bad_tool", function="f", args={})
                )
            )

        with patch("noa.api.v1.health._get_gateway", return_value=gw):
            client = TestClient(app)
            resp = client.get("/health/tools")

        tools_data = resp.json()["data"]["tools"]
        assert tools_data["web_search"]["error_rate"] == 0.0
        assert tools_data["bad_tool"]["error_rate"] == 1.0

    def test_shows_latency_percentiles(self) -> None:
        app = _make_test_app()
        gw = ToolGateway()
        gw.register("web_search", _FakeAdapter())

        for _ in range(10):
            asyncio.run(
                gw.dispatch(
                    ToolRequest(tool="web_search", function="s", args={})
                )
            )

        with patch("noa.api.v1.health._get_gateway", return_value=gw):
            client = TestClient(app)
            resp = client.get("/health/tools")

        stats = resp.json()["data"]["tools"]["web_search"]
        assert "p50_latency_ms" in stats
        assert "p95_latency_ms" in stats
        assert isinstance(stats["p50_latency_ms"], (int, float))
        assert isinstance(stats["p95_latency_ms"], (int, float))

    def test_empty_when_no_calls(self) -> None:
        app = _make_test_app()
        gw = ToolGateway()

        with patch("noa.api.v1.health._get_gateway", return_value=gw):
            client = TestClient(app)
            resp = client.get("/health/tools")

        data = resp.json()
        assert data["ok"] is True
        assert data["data"]["tools"] == {}
