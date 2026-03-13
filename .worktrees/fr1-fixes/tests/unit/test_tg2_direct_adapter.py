"""Tests for TG2: DirectApiAdapter.

Wraps a ToolInterface implementation and converts
ToolRequest/ToolResponse for the ToolGateway.
"""

from __future__ import annotations

import asyncio
from typing import Any

from noa.tools.adapters.direct import DirectApiAdapter
from noa.tools.gateway import ToolAdapter, ToolRequest, ToolResponse

# -------------------------------------------------------------------
# Fake ToolInterface for testing
# -------------------------------------------------------------------


class FakeTool:
    name: str = "fake"
    domain: str = "external"
    risk_tiers: dict[str, str] = {"do_thing": "low"}

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result or {"ok": True}
        self._error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append((function, args))
        if self._error:
            raise self._error
        return self._result


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------


class TestDirectApiAdapter:
    def test_implements_tool_adapter(self) -> None:
        adapter = DirectApiAdapter(tool=FakeTool())
        assert isinstance(adapter, ToolAdapter)

    def test_forwards_execute_to_tool(self) -> None:
        tool = FakeTool(result={"data": [1]})
        adapter = DirectApiAdapter(tool=tool)

        req = ToolRequest(
            tool="fake",
            function="do_thing",
            args={"key": "val"},
        )
        resp = asyncio.run(adapter.execute(req))

        assert resp.result == {"data": [1]}
        assert resp.error is None
        assert len(tool.calls) == 1
        assert tool.calls[0] == ("do_thing", {"key": "val"})

    def test_converts_request_args(self) -> None:
        tool = FakeTool()
        adapter = DirectApiAdapter(tool=tool)

        req = ToolRequest(
            tool="fake",
            function="do_thing",
            args={"a": 1, "b": "two"},
        )
        asyncio.run(adapter.execute(req))

        assert tool.calls[0] == ("do_thing", {"a": 1, "b": "two"})

    def test_wraps_result_in_tool_response(self) -> None:
        tool = FakeTool(result={"items": []})
        adapter = DirectApiAdapter(tool=tool)

        req = ToolRequest(
            tool="fake", function="do_thing", args={}
        )
        resp = asyncio.run(adapter.execute(req))

        assert isinstance(resp, ToolResponse)
        assert resp.result == {"items": []}

    def test_captures_latency(self) -> None:
        adapter = DirectApiAdapter(tool=FakeTool())
        req = ToolRequest(
            tool="fake", function="do_thing", args={}
        )
        resp = asyncio.run(adapter.execute(req))

        assert resp.latency_ms >= 0

    def test_captures_error_no_exception_leak(self) -> None:
        tool = FakeTool(error=RuntimeError("boom"))
        adapter = DirectApiAdapter(tool=tool)

        req = ToolRequest(
            tool="fake", function="do_thing", args={}
        )
        resp = asyncio.run(adapter.execute(req))

        assert resp.error is not None
        assert "boom" in resp.error
        assert resp.result is None

    def test_provider_field_is_direct(self) -> None:
        adapter = DirectApiAdapter(tool=FakeTool())
        req = ToolRequest(
            tool="fake", function="do_thing", args={}
        )
        resp = asyncio.run(adapter.execute(req))

        assert resp.provider == "direct"

    def test_passes_function_name_correctly(self) -> None:
        tool = FakeTool()
        adapter = DirectApiAdapter(tool=tool)

        req = ToolRequest(
            tool="fake",
            function="do_thing",
            args={"x": 42},
        )
        asyncio.run(adapter.execute(req))

        assert tool.calls[0][0] == "do_thing"
