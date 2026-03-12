"""MCPToolAdapter — legacy stub superseded by McpRemoteAdapter (TM6).

This module contains the OLD MCPToolAdapter class that was a placeholder before
TM6 (Wave 18) delivered McpRemoteAdapter with real HTTP+SSE JSON-RPC 2.0 transport.

DEPRECATED: Use McpRemoteAdapter from noa.tools.mcp_discovery instead.
This class is retained only to avoid breaking any existing registry lookups that
reference it by name. Its execute() method intentionally raises NotImplementedError
as a guard — it should never be called in production.
"""

from __future__ import annotations

from typing import Any


class MCPToolAdapter:
    """Legacy adapter superseded by McpRemoteAdapter (TM6, Wave 18).

    DEPRECATED: This is the pre-TM6 stub. Real MCP dispatch goes through
    McpRemoteAdapter in noa.tools.mcp_discovery, which implements the
    JSON-RPC 2.0 over HTTP+SSE transport introduced in TM6.

    Risk tiers come from static config, NOT from MCP server discovery,
    per §2.1 (static allowlists).

    Args:
        name: Tool name.
        domain: "private" or "external".
        risk_tiers: Static risk tier mapping from config.
    """

    def __init__(
        self,
        *,
        name: str,
        domain: str,
        risk_tiers: dict[str, str],
    ) -> None:
        self.name = name
        self.domain = domain
        self.risk_tiers = risk_tiers

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute via MCP transport.

        DEPRECATED: This legacy stub always raises NotImplementedError. It was
        superseded by McpRemoteAdapter (noa.tools.mcp_discovery) in TM6 (Wave 18),
        which provides real JSON-RPC 2.0 over HTTP+SSE transport. If this raises in
        production, a registry entry is incorrectly pointing at MCPToolAdapter instead
        of McpRemoteAdapter.

        Raises:
            NotImplementedError: Always. This legacy adapter has no transport.
        """
        raise NotImplementedError(
            f"MCPToolAdapter is deprecated — use McpRemoteAdapter for "
            f"{self.name}.{function}. See noa.tools.mcp_discovery (TM6)."
        )
