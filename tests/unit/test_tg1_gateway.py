"""Tests for TG1: ToolRequest/ToolResponse + ToolGateway.

Spec refs: SPEC.md §19.1 (idempotency), §19.2 (dry-run),
§19.3 (rate limits), §2.1 (allowlist).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from noa.tools.gateway import (
    ToolGateway,
    ToolRequest,
    ToolResponse,
)

# -------------------------------------------------------------------
# ToolRequest / ToolResponse dataclass tests
# -------------------------------------------------------------------


class TestToolRequest:
    def test_create_with_required_fields(self) -> None:
        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "hello"},
        )
        assert req.tool == "web_search"
        assert req.function == "web_search"
        assert req.args == {"query": "hello"}
        assert req.idempotency_key is None
        assert req.privacy_mode == "external"

    def test_create_with_all_fields(self) -> None:
        req = ToolRequest(
            tool="calendar",
            function="create_event",
            args={"title": "meeting"},
            idempotency_key="abc-123",
            privacy_mode="private",
        )
        assert req.idempotency_key == "abc-123"
        assert req.privacy_mode == "private"


class TestToolResponse:
    def test_create_with_result(self) -> None:
        resp = ToolResponse(result={"data": [1, 2, 3]})
        assert resp.result == {"data": [1, 2, 3]}
        assert resp.error is None
        assert resp.latency_ms >= 0
        assert resp.cached is False

    def test_create_with_error(self) -> None:
        resp = ToolResponse(error="timeout")
        assert resp.result is None
        assert resp.error == "timeout"

    def test_create_with_provider(self) -> None:
        resp = ToolResponse(
            result={}, provider="direct", latency_ms=42.5
        )
        assert resp.provider == "direct"
        assert resp.latency_ms == 42.5


# -------------------------------------------------------------------
# Fake adapter for testing
# -------------------------------------------------------------------


class FakeAdapter:
    """Test adapter implementing ToolAdapter protocol."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or {"ok": True}
        self._error = error
        self.calls: list[ToolRequest] = []

    async def execute(
        self, request: ToolRequest
    ) -> ToolResponse:
        self.calls.append(request)
        if self._error:
            return ToolResponse(error=self._error)
        return ToolResponse(
            result=self._result, provider="fake"
        )


# -------------------------------------------------------------------
# ToolGateway tests
# -------------------------------------------------------------------


class TestToolGateway:
    def test_register_and_dispatch(self) -> None:
        adapter = FakeAdapter(result={"results": []})
        gw = ToolGateway()
        gw.register("web_search", adapter)

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "hi"},
        )
        resp = asyncio.run(gw.dispatch(req))

        assert resp.result == {"results": []}
        assert resp.error is None
        assert len(adapter.calls) == 1

    def test_reject_unregistered_tool(self) -> None:
        gw = ToolGateway()
        req = ToolRequest(
            tool="unknown", function="do_thing", args={}
        )
        resp = asyncio.run(gw.dispatch(req))

        assert resp.error is not None
        err = resp.error.lower()
        assert "not registered" in err or "not allowed" in err

    def test_telemetry_recorded(self) -> None:
        adapter = FakeAdapter()
        gw = ToolGateway()
        gw.register("web_search", adapter)

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
        )
        resp = asyncio.run(gw.dispatch(req))

        assert resp.latency_ms >= 0
        assert len(gw.telemetry) == 1
        entry = gw.telemetry[0]
        assert entry["tool"] == "web_search"
        assert entry["function"] == "web_search"
        assert "latency_ms" in entry
        assert entry["status"] == "ok"

    def test_telemetry_on_error(self) -> None:
        adapter = FakeAdapter(error="api_error")
        gw = ToolGateway()
        gw.register("web_search", adapter)

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={},
        )
        resp = asyncio.run(gw.dispatch(req))

        assert resp.error == "api_error"
        assert len(gw.telemetry) == 1
        assert gw.telemetry[0]["status"] == "error"

    def test_idempotency_key_caching(self) -> None:
        adapter = FakeAdapter(result={"count": 1})
        gw = ToolGateway()
        gw.register("web_search", adapter)

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
            idempotency_key="key-1",
        )
        resp1 = asyncio.run(gw.dispatch(req))
        resp2 = asyncio.run(gw.dispatch(req))

        assert resp1.result == {"count": 1}
        assert resp2.result == {"count": 1}
        assert resp2.cached is True
        # Adapter should only be called once
        assert len(adapter.calls) == 1

    def test_rate_limit_enforcement(self) -> None:
        adapter = FakeAdapter()
        gw = ToolGateway()
        gw.register("web_search", adapter)
        gw.set_rate_limit(
            "web_search", max_calls=1, window_seconds=3600
        )

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "a"},
        )
        resp1 = asyncio.run(gw.dispatch(req))
        assert resp1.error is None

        resp2 = asyncio.run(gw.dispatch(req))
        assert resp2.error is not None
        assert "rate limit" in resp2.error.lower()

    def test_dry_run_mode(self) -> None:
        adapter = FakeAdapter()
        gw = ToolGateway()
        gw.register("gmail", adapter)

        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={"to": "a@b.com", "body": "hi"},
        )
        resp = asyncio.run(
            gw.dispatch(req, dry_run=True)
        )

        assert resp.result is not None
        assert "preview" in resp.result or "action" in resp.result
        assert len(adapter.calls) == 0

    def test_allowlist_property(self) -> None:
        gw = ToolGateway()
        gw.register("web_search", FakeAdapter())
        gw.register("calendar", FakeAdapter())
        assert gw.allowlist == frozenset(
            {"web_search", "calendar"}
        )

    def test_list_tools(self) -> None:
        gw = ToolGateway()
        gw.register("a", FakeAdapter())
        gw.register("b", FakeAdapter())
        assert sorted(gw.list_tools()) == ["a", "b"]


# -------------------------------------------------------------------
# tool_node integration
# -------------------------------------------------------------------


class TestToolNodeGatewayIntegration:
    def _make_state(
        self, tool_calls: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "tool_calls": tool_calls,
            "tool_results": [],
            "messages": [],
            "privacy_mode": "external",
            "selected_model": "test",
            "response": None,
            "total_cost": 0.0,
        }

    @pytest.mark.asyncio
    async def test_tool_node_uses_gateway_when_set(self) -> None:
        from noa.orchestrator.nodes import tools as tm

        adapter = FakeAdapter(result={"search_results": []})
        gw = ToolGateway()
        gw.register("web_search", adapter)

        old_gw = getattr(tm, "_gateway", None)
        old_reg = tm._registry
        try:
            tm._gateway = gw
            tm._registry = None

            calls = [{
                "tool": "web_search",
                "function": "web_search",
                "args": {"query": "test"},
            }]
            result = await tm.tool_node(self._make_state(calls))
            assert len(result["tool_results"]) == 1
            tr = result["tool_results"][0]
            assert tr.get("error") is None
        finally:
            tm._gateway = old_gw
            tm._registry = old_reg

    @pytest.mark.asyncio
    async def test_tool_node_falls_back_to_registry(self) -> None:
        from noa.orchestrator.nodes import tools as tm

        mock_reg = MagicMock(spec=tm.ToolRegistry)
        mock_reg.dispatch = AsyncMock(
            return_value={"data": "ok"}
        )
        mock_reg.list_tools.return_value = ["calendar"]
        mock_tool = MagicMock()
        mock_tool.risk_tiers = {"list_events": "low"}
        mock_reg.get.return_value = mock_tool

        old_gw = getattr(tm, "_gateway", None)
        old_reg = tm._registry
        try:
            tm._gateway = None
            tm._registry = mock_reg

            calls = [{
                "tool": "calendar",
                "function": "list_events",
                "args": {},
            }]
            result = await tm.tool_node(self._make_state(calls))
            assert len(result["tool_results"]) == 1
        finally:
            tm._gateway = old_gw
            tm._registry = old_reg
