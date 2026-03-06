"""McpRemoteAdapter — Phase 2 stub for container-isolated MCP transport.

In Phase 2 (multi-machine deployment), MCP servers run in isolated
containers. This adapter will communicate over HTTP+SSE or WebSocket.
For now, it defines the interface and raises NotImplementedError.

Spec refs: SPEC.md §8.2, §20
"""

from __future__ import annotations

from dataclasses import dataclass

from noa.tools.gateway import ToolRequest, ToolResponse


@dataclass
class McpRemoteConfig:
    """Configuration for a remote MCP server connection."""

    url: str
    auth_token: str


class McpRemoteAdapter:
    """Adapter for remote MCP servers (Phase 2 only).

    Args:
        config: Remote MCP connection configuration.
    """

    def __init__(self, *, config: McpRemoteConfig) -> None:
        self._config = config

    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute a tool call via remote MCP transport.

        Raises:
            NotImplementedError: Always — Phase 2 only.
        """
        raise NotImplementedError(
            "Phase 2: MCP remote transport not yet implemented"
        )
