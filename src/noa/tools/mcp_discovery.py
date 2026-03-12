"""MCP auto-discovery — connect to an MCP server and discover available tools.

Fetches the tools/list from a remote MCP server and converts the MCP tool
definitions into the internal TOOL_SCHEMAS format used by the LLM pipeline.

Spec refs: SPEC.md §2.1 (static allowlists), §8.3 (inter-domain communication)
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class McpConnectionError(Exception):
    """Raised when an MCP server is unreachable or returns an invalid response."""


async def _fetch_tools_list(
    server_url: str,
    auth_token: str,
) -> list[dict[str, Any]]:
    """Fetch the tools/list from an MCP server via JSON-RPC 2.0.

    Args:
        server_url: The MCP server URL.
        auth_token: Bearer token for authentication.

    Returns:
        List of MCP tool definitions.

    Raises:
        McpConnectionError: If the server is unreachable.
        RuntimeError: If the server returns a JSON-RPC error.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            server_url,
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()

    if "error" in body and body["error"] is not None:
        err = body["error"]
        raise RuntimeError(
            f"MCP server error: {err.get('message', 'unknown')}"
        )

    return cast(list[dict[str, Any]], body.get("result", []))


async def discover_tools(
    server_url: str,
    auth_token: str,
) -> list[dict[str, Any]]:
    """Connect to an MCP server and discover available tools.

    Fetches the MCP tools/list and converts each tool definition into
    the internal format with 'name', 'description', and 'parameters'.

    Args:
        server_url: The MCP server URL.
        auth_token: Bearer token for authentication.

    Returns:
        List of tool definitions in internal format.

    Raises:
        McpConnectionError: If the server is unreachable.
    """
    try:
        mcp_tools = await _fetch_tools_list(server_url, auth_token)
    except (ConnectionError, OSError, httpx.ConnectError) as exc:
        raise McpConnectionError(
            f"Failed to connect to MCP server at {server_url}: {exc}"
        ) from exc

    result: list[dict[str, Any]] = []
    for tool in mcp_tools:
        converted = {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {
                "type": "object",
                "properties": {},
            }),
        }
        result.append(converted)

    return result


def discovered_tools_to_schemas(
    server_name: str,
    tools: list[dict[str, Any]],
    domain: str = "external",
) -> dict[str, Any]:
    """Convert discovered MCP tools into TOOL_SCHEMAS format.

    Produces a dict compatible with the canonical TOOL_SCHEMAS structure:
    ``{server_name: {functions: {func_name: {description, parameters, domain}}}}``

    Args:
        server_name: Name to register the server under (e.g. 'mcp_fs').
        tools: List of MCP tool definitions (from tools/list or discover_tools).
        domain: Domain scope ('private' or 'external').

    Returns:
        Dict in TOOL_SCHEMAS format.
    """
    functions: dict[str, Any] = {}
    for tool in tools:
        name = tool["name"]
        # Accept both 'inputSchema' (raw MCP) and 'parameters' (already converted)
        parameters = tool.get("parameters", tool.get("inputSchema", {
            "type": "object",
            "properties": {},
        }))
        functions[name] = {
            "description": tool.get("description", ""),
            "parameters": parameters,
            "domain": domain,
        }

    return {
        server_name: {
            "description": f"MCP server: {server_name}",
            "functions": functions,
        },
    }
