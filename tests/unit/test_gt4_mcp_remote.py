"""Tests for GT4: McpRemoteAdapter (Phase 2 Stub).

Covers: McpRemoteAdapter stub with NotImplementedError,
McpRemoteConfig dataclass.

Spec refs: SPEC.md §8.2, §20
"""
# ruff: noqa: S105, S106

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gt4


class TestMcpRemoteAdapter:
    """Tests for McpRemoteAdapter stub."""

    def test_has_execute_method(self):
        """McpRemoteAdapter must have execute(request) signature."""
        from noa.tools.adapters.mcp_remote import McpRemoteAdapter, McpRemoteConfig

        config = McpRemoteConfig(url="http://mcp:8080", auth_token="tok")
        adapter = McpRemoteAdapter(config=config)

        assert hasattr(adapter, "execute")
        assert callable(adapter.execute)

    @pytest.mark.asyncio
    async def test_execute_no_longer_raises_not_implemented(self):
        """TM6: execute uses real transport, not stub."""
        from noa.tools.adapters.mcp_remote import McpRemoteAdapter, McpRemoteConfig
        from noa.tools.gateway import ToolRequest

        config = McpRemoteConfig(url="http://mcp:8080", auth_token="tok")
        adapter = McpRemoteAdapter(config=config)

        request = ToolRequest(
            tool="notion", function="search_pages", args={"query": "x"}
        )

        with pytest.raises(Exception) as exc_info:
            await adapter.execute(request)
        assert not isinstance(exc_info.value, NotImplementedError)

    def test_config_has_url_and_auth_token(self):
        """McpRemoteConfig must have url and auth_token fields."""
        from noa.tools.adapters.mcp_remote import McpRemoteConfig

        config = McpRemoteConfig(url="http://mcp:8080", auth_token="secret")
        assert config.url == "http://mcp:8080"
        assert config.auth_token == "secret"

    def test_adapter_accepts_config(self):
        """McpRemoteAdapter must accept McpRemoteConfig in constructor."""
        from noa.tools.adapters.mcp_remote import McpRemoteAdapter, McpRemoteConfig

        config = McpRemoteConfig(url="http://mcp:9090", auth_token="t")
        adapter = McpRemoteAdapter(config=config)
        assert adapter._config is config
