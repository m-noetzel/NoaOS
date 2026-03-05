"""MCPToolAdapter — stub for future MCP server integration.

Implements ToolInterface with risk tiers from static config.
Transport layer (stdio/SSE) deferred to a future phase.
"""

from __future__ import annotations

from typing import Any


class MCPToolAdapter:
    """Adapter that wraps a future MCP call_tool() behind ToolInterface.

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
        """Execute via MCP transport (not yet wired).

        Raises:
            NotImplementedError: MCP transport not yet implemented.
        """
        raise NotImplementedError(
            f"MCP transport not wired for {self.name}.{function}"
        )
