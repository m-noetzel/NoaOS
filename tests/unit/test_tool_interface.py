"""Tests for TI6: ToolInterface Protocol, ToolRegistry, MCPToolAdapter.

Covers: ToolInterface compliance for all 5 MVP tools, ToolRegistry
dispatch, allowlist enforcement, MCPToolAdapter stub, tool_node wiring.

Spec refs: SPEC.md §2.1, §12
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti6


# ---------------------------------------------------------------------------
# ToolInterface Protocol compliance
# ---------------------------------------------------------------------------


class TestToolInterfaceCompliance:
    """All 5 MVP tools must satisfy the ToolInterface Protocol."""

    def test_memory_tool_satisfies_interface(self):
        """MemoryTool must implement ToolInterface.

        SPEC.md §12.5 — Memory tool.
        """
        from noa.tools.interface import ToolInterface
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock()
        tool = MemoryTool(rpc_client=mock_rpc)
        assert isinstance(tool, ToolInterface)

    def test_calendar_tool_satisfies_interface(self):
        """CalendarTool must implement ToolInterface.

        SPEC.md §12.1 — Calendar tool.
        """
        from noa.tools.calendar import CalendarTool
        from noa.tools.interface import ToolInterface

        tool = CalendarTool(api_client=AsyncMock())
        assert isinstance(tool, ToolInterface)

    def test_gmail_tool_satisfies_interface(self):
        """GmailTool must implement ToolInterface.

        SPEC.md §12.2 — Gmail tool.
        """
        from noa.tools.gmail import GmailTool
        from noa.tools.interface import ToolInterface

        tool = GmailTool(api_client=AsyncMock())
        assert isinstance(tool, ToolInterface)

    def test_notion_tool_satisfies_interface(self):
        """NotionTool must implement ToolInterface.

        SPEC.md §12.3 — Notion tool.
        """
        from noa.tools.interface import ToolInterface
        from noa.tools.notion import NotionTool

        tool = NotionTool(api_client=AsyncMock())
        assert isinstance(tool, ToolInterface)

    def test_web_search_tool_satisfies_interface(self):
        """WebSearchTool must implement ToolInterface.

        SPEC.md §12.4 — Web Search tool.
        """
        from noa.tools.interface import ToolInterface
        from noa.tools.web_search import WebSearchTool

        tool = WebSearchTool(provider=AsyncMock())
        assert isinstance(tool, ToolInterface)


# ---------------------------------------------------------------------------
# ToolInterface attributes
# ---------------------------------------------------------------------------


class TestToolInterfaceAttributes:
    """ToolInterface must expose name, domain, risk_tiers, execute."""

    def test_interface_requires_name(self):
        """ToolInterface must require a 'name' attribute.

        SPEC.md §12 — Each tool has a name.
        """
        from noa.tools.interface import ToolInterface

        assert "name" in ToolInterface.__annotations__

    def test_interface_requires_domain(self):
        """ToolInterface must require a 'domain' attribute."""
        from noa.tools.interface import ToolInterface

        assert "domain" in ToolInterface.__annotations__

    def test_interface_requires_execute(self):
        """ToolInterface must require an 'execute' method."""
        from noa.tools.interface import ToolInterface

        assert hasattr(ToolInterface, "execute")


# ---------------------------------------------------------------------------
# ToolGateway allowlist (replaces ToolRegistry tests after CQ2 cleanup)
# ---------------------------------------------------------------------------


class TestToolGatewayAllowlist:
    """Tests for ToolGateway allowlist per §2.1 (static allowlists)."""

    def test_gateway_allowlist_matches_registered_tools(self):
        """ToolGateway allowlist must match registered tool names.

        SPEC.md §2.1 — Static allowlists.
        """
        from noa.tools.gateway import ToolGateway

        gw = ToolGateway()
        adapter1 = AsyncMock()
        adapter2 = AsyncMock()
        gw.register("calendar", adapter1)
        gw.register("gmail", adapter2)

        assert gw.allowlist == frozenset({"calendar", "gmail"})

    def test_gateway_list_tools(self):
        """ToolGateway must list all registered tools."""
        from noa.tools.gateway import ToolGateway

        gw = ToolGateway()
        gw.register("calendar", AsyncMock())

        assert "calendar" in gw.list_tools()


# ---------------------------------------------------------------------------
# MCPToolAdapter
# ---------------------------------------------------------------------------
# tool_node wiring
# ---------------------------------------------------------------------------


class TestToolNodeWiring:
    """Tests for tool_node dispatch through ToolGateway."""

    @pytest.mark.asyncio
    async def test_tool_node_dispatches_through_gateway(self):
        """tool_node must dispatch through ToolGateway.

        SPEC.md §2.1 — Static allowlist dispatch.
        """
        from noa.tools.adapters.direct import DirectApiAdapter
        from noa.tools.gateway import ToolGateway, ToolRequest

        mock_tool = AsyncMock()
        mock_tool.name = "calendar"
        mock_tool.domain = "external"
        mock_tool.risk_tiers = {"list_events": "low"}
        mock_tool.execute.return_value = {"id": "evt-123"}

        gw = ToolGateway()
        gw.register("calendar", DirectApiAdapter(tool=mock_tool))

        req = ToolRequest(
            tool="calendar",
            function="list_events",
            args={"start_date": "2026-03-05"},
        )
        resp = await gw.dispatch(req)

        assert resp.error is None
        assert resp.result == {"id": "evt-123"}

    @pytest.mark.asyncio
    async def test_gateway_unknown_tool_returns_error(self):
        """Dispatching unknown tool must return an error response."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()

        req = ToolRequest(tool="nonexistent", function="test", args={})
        resp = await gw.dispatch(req)
        assert resp.error is not None
        assert "not registered" in resp.error.lower()
