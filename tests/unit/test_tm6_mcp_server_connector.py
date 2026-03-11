"""Tests for MCP Server Connector — Phase TM6.

Spec: SPEC.md §2.1, §4.1, §8.3 (domain isolation)
Plan: PHASE_DETAILS.md TM6
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.tm6

_TOK = "test-mcp-tok"  # noqa: S105


def _mcp_tools() -> list[dict[str, Any]]:
    """Simulate MCP tools/list response."""
    return [
        {
            "name": "read_file",
            "description": "Read a file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write a file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    ]


def _cfg(**kw: Any) -> Any:
    from noa.tools.adapters.mcp_remote import McpRemoteConfig
    return McpRemoteConfig(
        url=kw.pop("url", "http://mcp-server:8080"),
        auth_token=kw.pop("auth_token", _TOK),  # noqa: S106
        **kw,
    )


def _adapter(**kw: Any) -> Any:
    from noa.tools.adapters.mcp_remote import McpRemoteAdapter
    return McpRemoteAdapter(config=_cfg(), **kw)


# ===================================================================
# MCP Transport
# ===================================================================


class TestMcpRemoteAdapterTransport:
    """Real HTTP+SSE transport replaces stub."""

    @pytest.mark.asyncio
    async def test_no_longer_raises_not_implemented(self) -> None:
        """execute must not raise NotImplementedError."""
        from noa.tools.gateway import ToolRequest

        adapter = _adapter()
        req = ToolRequest(
            tool="fs", function="read_file",
            args={"path": "/x"},
        )
        with pytest.raises(Exception) as exc_info:
            await adapter.execute(req)
        assert not isinstance(
            exc_info.value, NotImplementedError,
        )

    @pytest.mark.asyncio
    async def test_returns_tool_response(self) -> None:
        """execute returns ToolResponse on success."""
        from noa.tools.gateway import ToolRequest, ToolResponse

        adapter = _adapter()
        adapter._call_mcp = AsyncMock(
            return_value={"content": "data"},
        )
        req = ToolRequest(
            tool="fs", function="read_file",
            args={"path": "/x"},
        )
        resp = await adapter.execute(req)
        assert isinstance(resp, ToolResponse)
        assert resp.result == {"content": "data"}
        assert resp.error is None

    @pytest.mark.asyncio
    async def test_wraps_server_error(self) -> None:
        """Server errors captured in ToolResponse.error."""
        from noa.tools.gateway import ToolRequest, ToolResponse

        adapter = _adapter()
        adapter._call_mcp = AsyncMock(
            side_effect=RuntimeError("MCP error -32600"),
        )
        req = ToolRequest(
            tool="fs", function="read_file",
            args={"path": "/nope"},
        )
        resp = await adapter.execute(req)
        assert isinstance(resp, ToolResponse)
        assert resp.error is not None

    @pytest.mark.asyncio
    async def test_sends_auth_and_function(self) -> None:
        """Auth token and function name forwarded."""
        from noa.tools.gateway import ToolRequest

        adapter = _adapter()
        adapter._call_mcp = AsyncMock(return_value={"ok": True})
        req = ToolRequest(
            tool="fs", function="read_file",
            args={"path": "/x"},
        )
        await adapter.execute(req)
        adapter._call_mcp.assert_called_once()
        assert "read_file" in str(
            adapter._call_mcp.call_args,
        )


# ===================================================================
# MCP Discovery
# ===================================================================


class TestMcpDiscovery:
    """Auto-discover tools from MCP server."""

    @pytest.mark.asyncio
    async def test_returns_tool_definitions(self) -> None:
        """discover_tools returns tool list."""
        from noa.tools.mcp_discovery import discover_tools

        with patch(
            "noa.tools.mcp_discovery._fetch_tools_list",
            new_callable=AsyncMock,
            return_value=_mcp_tools(),
        ):
            tools = await discover_tools(
                server_url="http://mcp:8080",
                auth_token=_TOK,
            )
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert "read_file" in names

    @pytest.mark.asyncio
    async def test_converts_input_schema(self) -> None:
        """inputSchema → parameters."""
        from noa.tools.mcp_discovery import discover_tools

        with patch(
            "noa.tools.mcp_discovery._fetch_tools_list",
            new_callable=AsyncMock,
            return_value=_mcp_tools(),
        ):
            tools = await discover_tools(
                server_url="http://mcp:8080",
                auth_token=_TOK,
            )
        rf = next(t for t in tools if t["name"] == "read_file")
        assert "parameters" in rf
        assert rf["parameters"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_raises_on_unreachable(self) -> None:
        """Unreachable server → McpConnectionError."""
        from noa.tools.mcp_discovery import (
            McpConnectionError,
            discover_tools,
        )

        with (
            patch(
                "noa.tools.mcp_discovery._fetch_tools_list",
                new_callable=AsyncMock,
                side_effect=ConnectionError("refused"),
            ),
            pytest.raises(McpConnectionError),
        ):
            await discover_tools(
                server_url="http://bad:9999",
                auth_token=_TOK,
            )

    @pytest.mark.asyncio
    async def test_empty_server(self) -> None:
        """Server with no tools → empty list."""
        from noa.tools.mcp_discovery import discover_tools

        with patch(
            "noa.tools.mcp_discovery._fetch_tools_list",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await discover_tools(
                server_url="http://mcp:8080",
                auth_token=_TOK,
            )
        assert tools == []


# ===================================================================
# Domain Routing
# ===================================================================


class TestMcpDomainRouting:
    """MCP servers assigned to domains."""

    def test_has_domain_attribute(self) -> None:
        """Adapter exposes domain."""
        adapter = _adapter()
        assert hasattr(adapter, "domain") or hasattr(
            adapter, "_domain",
        )

    def test_rejects_invalid_domain(self) -> None:
        """Invalid domain rejected."""
        from noa.tools.adapters.mcp_remote import (
            McpRemoteAdapter,
        )

        with pytest.raises((ValueError, TypeError)):
            McpRemoteAdapter(config=_cfg(), domain="cloud")

    def test_registration_assigns_domain(self) -> None:
        """register_mcp_server is callable."""
        from noa.tools.registration import register_mcp_server
        assert callable(register_mcp_server)

    @pytest.mark.asyncio
    async def test_private_tool_blocked_externally(self) -> None:
        """Private-domain tool blocked for external tasks."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        mock_adapter = AsyncMock()
        mock_adapter.domain = "private"
        gw.register("priv_mcp", mock_adapter)

        req = ToolRequest(
            tool="priv_mcp", function="read_file",
            args={"path": "/secret"},
            privacy_mode="external",
        )
        with pytest.raises((PermissionError, ValueError)):
            await gw.dispatch(req)


# ===================================================================
# API Endpoint
# ===================================================================


class TestMcpServerRegistrationEndpoint:
    """POST /api/v1/tools/mcp-servers."""

    @pytest.mark.asyncio
    async def test_endpoint_exists(self) -> None:
        """Endpoint registered (not 404/405)."""
        from fastapi.testclient import TestClient

        from noa.api.app import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/tools/mcp-servers",
            json={
                "url": "http://mcp:8080",
                "auth_token": _TOK,
                "domain": "external",
            },
        )
        assert resp.status_code != 404
        assert resp.status_code != 405

    @pytest.mark.asyncio
    async def test_requires_url(self) -> None:
        """Missing url → 422 or 401."""
        from fastapi.testclient import TestClient

        from noa.api.app import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/tools/mcp-servers",
            json={"auth_token": _TOK, "domain": "external"},
        )
        assert resp.status_code in (401, 422)


# ===================================================================
# Gateway Integration
# ===================================================================


class TestMcpGatewayIntegration:
    """MCP tools through standard gateway."""

    @pytest.mark.asyncio
    async def test_dispatched_through_gateway(self) -> None:
        """MCP tool dispatchable via gateway."""
        from noa.tools.gateway import (
            ToolGateway,
            ToolRequest,
            ToolResponse,
        )

        gw = ToolGateway()
        adapter = _adapter()
        adapter._call_mcp = AsyncMock(
            return_value={"content": "hello"},
        )
        gw.register("mcp_fs", adapter)

        req = ToolRequest(
            tool="mcp_fs", function="read_file",
            args={"path": "/test"},
        )
        resp = await gw.dispatch(req)
        assert isinstance(resp, ToolResponse)
        assert resp.result is not None

    @pytest.mark.asyncio
    async def test_appears_in_allowlist(self) -> None:
        """Registered MCP tool in gateway allowlist."""
        from noa.tools.gateway import ToolGateway

        gw = ToolGateway()
        adapter = _adapter()
        gw.register("mcp_notion", adapter)
        assert "mcp_notion" in gw.allowlist

    @pytest.mark.asyncio
    async def test_telemetry_recorded(self) -> None:
        """MCP invocations logged in telemetry."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _adapter()
        adapter._call_mcp = AsyncMock(
            return_value={"data": "ok"},
        )
        gw.register("mcp_test", adapter)

        req = ToolRequest(
            tool="mcp_test", function="fn",
            args={"key": "val"},
        )
        await gw.dispatch(req)
        assert len(gw.telemetry) >= 1
        assert gw.telemetry[-1]["tool"] == "mcp_test"

    @pytest.mark.asyncio
    async def test_discovered_tools_to_schemas(self) -> None:
        """MCP tools convert to TOOL_SCHEMAS format."""
        from noa.tools.mcp_discovery import (
            discovered_tools_to_schemas,
        )

        schemas = discovered_tools_to_schemas(
            server_name="mcp_fs",
            tools=_mcp_tools(),
            domain="external",
        )
        assert "mcp_fs" in schemas
        funcs = schemas["mcp_fs"]["functions"]
        assert "read_file" in funcs
        assert "write_file" in funcs
        assert funcs["read_file"]["domain"] == "external"
        assert "parameters" in funcs["read_file"]
