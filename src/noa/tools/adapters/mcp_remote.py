"""McpRemoteAdapter — real HTTP+SSE MCP transport for remote MCP servers.

Communicates with MCP servers over HTTP using JSON-RPC 2.0 protocol.
Each adapter is domain-scoped (private or external) for routing enforcement.

Spec refs: SPEC.md §4.1, §8.2, §8.3, §20
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from noa.tools.gateway import ToolRequest, ToolResponse

logger = logging.getLogger(__name__)

_VALID_DOMAINS = frozenset({"private", "external"})


@dataclass
class McpRemoteConfig:
    """Configuration for a remote MCP server connection."""

    url: str
    auth_token: str


class McpRemoteAdapter:
    """Adapter for remote MCP servers using HTTP+SSE JSON-RPC transport.

    Args:
        config: Remote MCP connection configuration.
        domain: Domain scope — must be 'private' or 'external'.
    """

    def __init__(
        self,
        *,
        config: McpRemoteConfig,
        domain: str = "external",
    ) -> None:
        if domain not in _VALID_DOMAINS:
            raise ValueError(
                f"Invalid domain '{domain}': must be one of {sorted(_VALID_DOMAINS)}"
            )
        self._config = config
        self.domain = domain

    async def _call_mcp(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Send a JSON-RPC 2.0 request to the MCP server over HTTP.

        Args:
            method: The MCP method name (e.g. 'tools/call').
            params: Method parameters.

        Returns:
            The 'result' field from the JSON-RPC response.

        Raises:
            RuntimeError: If the server returns a JSON-RPC error.
            httpx.ConnectError: If the server is unreachable.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.auth_token}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._config.url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            body = resp.json()

        if "error" in body and body["error"] is not None:
            err = body["error"]
            code = err.get("code", "unknown")
            msg = err.get("message", "MCP server error")
            raise RuntimeError(f"MCP server returned error code {code}: {msg}")

        return body.get("result")

    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute a tool call via remote MCP transport.

        Sends a tools/call JSON-RPC request to the MCP server and wraps
        the result (or error) in a ToolResponse. MCP application-level
        errors (RuntimeError from JSON-RPC error responses) are captured
        in ToolResponse.error. Transport-level errors (connection failures)
        propagate to the caller.
        """
        try:
            result = await self._call_mcp(
                method="tools/call",
                params={
                    "name": request.function,
                    "arguments": request.args,
                },
            )
            return ToolResponse(
                result=result,
                provider="mcp_remote",
            )
        except RuntimeError as exc:
            # MCP application-level error (JSON-RPC error response)
            logger.warning(
                "MCP server error for %s.%s: %s",
                request.tool,
                request.function,
                exc,
            )
            return ToolResponse(
                result=None,
                error=str(exc),
                provider="mcp_remote",
            )
