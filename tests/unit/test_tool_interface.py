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
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """Tests for the ToolRegistry per §2.1 (static allowlists)."""

    def test_registry_dispatch_routes_to_correct_tool(self):
        """ToolRegistry must dispatch to the correct tool.

        SPEC.md §2.1 — Tool dispatch through registry.
        """
        from noa.tools.interface import ToolRegistry

        mock_tool = AsyncMock()
        mock_tool.name = "test_tool"
        registry = ToolRegistry({"test_tool": mock_tool})

        assert registry.get("test_tool") is mock_tool

    def test_registry_unknown_tool_raises_error(self):
        """ToolRegistry must raise KeyError for unknown tools.

        SPEC.md §2.2 — LLM may NOT execute tools not in allowlist.
        """
        from noa.tools.interface import ToolRegistry

        registry = ToolRegistry({})

        with pytest.raises(KeyError, match="unknown_tool"):
            registry.get("unknown_tool")

    def test_registry_allowlist_matches_keys(self):
        """ToolRegistry allowlist must match registered tool names.

        SPEC.md §2.1 — Static allowlists.
        """
        from noa.tools.interface import ToolRegistry

        mock1 = AsyncMock()
        mock1.name = "calendar"
        mock2 = AsyncMock()
        mock2.name = "gmail"
        registry = ToolRegistry({"calendar": mock1, "gmail": mock2})

        assert registry.allowlist == frozenset({"calendar", "gmail"})

    def test_registry_list_tools(self):
        """ToolRegistry must list all registered tools."""
        from noa.tools.interface import ToolRegistry

        mock1 = AsyncMock()
        mock1.name = "calendar"
        registry = ToolRegistry({"calendar": mock1})

        assert "calendar" in registry.list_tools()


# ---------------------------------------------------------------------------
# MCPToolAdapter
# ---------------------------------------------------------------------------


class TestMCPToolAdapter:
    """Tests for the MCPToolAdapter stub."""

    def test_mcp_adapter_implements_interface(self):
        """MCPToolAdapter must implement ToolInterface.

        MCP-ready design per MASTER_PLAN TI6.
        """
        from noa.tools.interface import ToolInterface
        from noa.tools.mcp_adapter import MCPToolAdapter

        adapter = MCPToolAdapter(
            name="mcp_test",
            domain="external",
            risk_tiers={"default": "low"},
        )
        assert isinstance(adapter, ToolInterface)

    @pytest.mark.asyncio
    async def test_mcp_adapter_execute_raises_not_implemented(self):
        """MCPToolAdapter.execute() must raise NotImplementedError.

        Transport layer deferred per MASTER_PLAN TI6.
        """
        from noa.tools.mcp_adapter import MCPToolAdapter

        adapter = MCPToolAdapter(
            name="mcp_test",
            domain="external",
            risk_tiers={"default": "low"},
        )

        with pytest.raises(NotImplementedError, match="MCPToolAdapter is deprecated"):
            await adapter.execute(function="test", args={})

    def test_mcp_adapter_risk_tiers_from_config(self):
        """MCPToolAdapter risk_tiers must come from static config.

        SPEC.md §2.1 — Risk tiers NOT from MCP server discovery.
        """
        from noa.tools.mcp_adapter import MCPToolAdapter

        tiers = {"search": "low", "create": "medium"}
        adapter = MCPToolAdapter(
            name="mcp_test",
            domain="external",
            risk_tiers=tiers,
        )

        assert adapter.risk_tiers == tiers


# ---------------------------------------------------------------------------
# tool_node wiring
# ---------------------------------------------------------------------------


class TestToolNodeWiring:
    """Tests for tool_node dispatch through ToolRegistry."""

    @pytest.mark.asyncio
    async def test_tool_node_dispatches_through_registry(self):
        """tool_node must dispatch through ToolRegistry.

        SPEC.md §2.1 — Static allowlist dispatch.
        """
        from noa.tools.interface import ToolRegistry

        mock_tool = AsyncMock()
        mock_tool.name = "calendar"
        mock_tool.execute.return_value = {"id": "evt-123"}

        registry = ToolRegistry({"calendar": mock_tool})

        result = await registry.dispatch(
            name="calendar",
            function="list_events",
            args={"start_date": "2026-03-05"},
        )

        mock_tool.execute.assert_called_once_with(
            function="list_events",
            args={"start_date": "2026-03-05"},
        )
        assert result == {"id": "evt-123"}

    @pytest.mark.asyncio
    async def test_tool_node_unknown_tool_returns_error(self):
        """Dispatching unknown tool must raise KeyError."""
        from noa.tools.interface import ToolRegistry

        registry = ToolRegistry({})

        with pytest.raises(KeyError):
            await registry.dispatch(
                name="nonexistent", function="test", args={},
            )
