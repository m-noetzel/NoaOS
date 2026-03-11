"""Tool node — enforces static allowlist and dispatches tools.

Spec refs: SPEC.md S2.1 (tool allowlists are static per workflow),
           SPEC.md S2.2 (LLM may NOT execute tools not in allowlist).

Dispatches through ToolRegistry when available, falling back to
execute_tool for backward-compat (tests patch this).
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState
from noa.tools.gateway import ToolGateway, ToolRequest
from noa.tools.interface import ToolRegistry

# Module-level registry reference, set at startup via set_registry().
_registry: ToolRegistry | None = None

# Module-level gateway reference, set at startup via set_gateway().
_gateway: ToolGateway | None = None

# Static tool allowlist (S2.1) — used as fallback when no registry is set.
TOOL_ALLOWLIST: frozenset[str] = frozenset(
    [
        "calendar_list",
        "calendar_create",
        "calendar_delete",
        "email_search",
        "email_send",
        "note_search",
        "note_create",
        "web_search",
    ]
)


def set_registry(registry: ToolRegistry) -> None:
    """Set the module-level ToolRegistry. Called at app startup."""
    global _registry  # noqa: PLW0603
    _registry = registry


def get_registry() -> ToolRegistry | None:
    """Get the current ToolRegistry (or None if not configured)."""
    return _registry


def set_gateway(gateway: ToolGateway) -> None:
    """Set the module-level ToolGateway. Called at app startup."""
    global _gateway  # noqa: PLW0603
    _gateway = gateway


def get_gateway() -> ToolGateway | None:
    """Get the current ToolGateway (or None if not configured)."""
    return _gateway


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Fallback tool executor. Patched in tests; real dispatch uses registry."""
    msg = "execute_tool requires real tool backends (not yet wired)"
    raise NotImplementedError(msg)


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Dispatch tool calls through the allowlist filter.

    Tool calls may use either format:
    - Registry format: {"tool": "calendar", "function": "list_events", "args": {...}}
    - Legacy format: {"name": "calendar_list", "arguments": {...}}

    When a ToolRegistry is configured (via set_registry), dispatch goes through
    the registry. Otherwise falls back to execute_tool + TOOL_ALLOWLIST.
    """
    tool_calls: list[dict[str, Any]] = state.get("tool_calls", [])
    current_rounds: int = state.get("tool_rounds", 0)

    if not tool_calls:
        return {"tool_results": []}

    results: list[dict[str, Any]] = []
    for call in tool_calls:
        # Support both registry-format and legacy-format tool calls.
        if "tool" in call and "function" in call:
            # Registry format: tool + function + args
            tool_name = call["tool"]
            function = call["function"]
            args = call.get("args", {})

            if _gateway is not None:
                result = await _dispatch_gateway(tool_name, function, args)
            else:
                result = await _dispatch_registry(tool_name, function, args)
            results.append({"name": f"{tool_name}.{function}", **result})
        else:
            # Legacy or LLM tool_use format:
            #   {"name": "web_search__web_search", "input": {...}}
            #   {"name": "calendar_list", "arguments": {...}}
            name = call.get("name", "")
            arguments = call.get("input") or call.get("arguments", {})

            # Parse tool__function naming from definitions
            from noa.tools.definitions import parse_tool_call_name
            parsed_tool, parsed_func = parse_tool_call_name(name)
            if parsed_tool != name and _gateway is not None:
                result = await _dispatch_gateway(
                    parsed_tool, parsed_func, arguments,
                )
                results.append({"name": name, **result})
                continue

            if _registry is not None:
                # Try to dispatch through registry with legacy name
                result = await _dispatch_registry_legacy(name, arguments)
                results.append({"name": name, **result})
            elif name not in TOOL_ALLOWLIST:
                results.append(
                    {
                        "name": name,
                        "error": f"Tool not allowed: {name}. "
                        "Denied by static allowlist.",
                    }
                )
            else:
                result = execute_tool(name, arguments)
                results.append({"name": name, **result})

    # Append tool results as messages so the LLM sees them
    import json as _json
    msgs = list(state.get("messages", []))
    for idx, res in enumerate(results):
        tool_call = tool_calls[idx] if idx < len(tool_calls) else {}
        content = res.get("error") or _json.dumps(
            {k: v for k, v in res.items() if k != "name"},
            default=str,
        )
        msgs.append({
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "name": res.get("name", ""),
            "content": content,
        })

    return {
        "tool_results": results,
        "tool_rounds": current_rounds + 1,
        "messages": msgs,
    }


async def _dispatch_registry(
    tool_name: str, function: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch through the ToolRegistry."""
    assert _registry is not None  # noqa: S101
    try:
        return await _registry.dispatch(name=tool_name, function=function, args=args)
    except KeyError:
        return {"error": f"Tool not allowed: {tool_name}. Not in registry."}


async def _dispatch_registry_legacy(
    name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch a legacy flat tool name through the registry.

    Maps flat names like "calendar_list" → tool="calendar", function="list_events"
    by checking each registered tool's risk_tiers for a matching function.
    """
    assert _registry is not None  # noqa: S101

    # Try direct dispatch: the name might be a tool name with function in arguments
    for tool_name in _registry.list_tools():
        try:
            tool = _registry.get(tool_name)
        except KeyError:
            continue
        # Check if the flat name matches any function in this tool's risk_tiers
        if name in tool.risk_tiers:
            return await _dispatch_registry(tool_name, name, arguments)

    return {"error": f"Tool not allowed: {name}. Not found in registry."}


async def _dispatch_gateway(
    tool_name: str, function: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch through the ToolGateway."""
    assert _gateway is not None  # noqa: S101
    req = ToolRequest(tool=tool_name, function=function, args=args)
    try:
        resp = await _gateway.dispatch(req)
        return _gateway_response_to_dict(resp)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _gateway_response_to_dict(resp: Any) -> dict[str, Any]:
    """Convert a ToolResponse to a plain dict for tool_results."""
    if resp.error:
        return {"error": resp.error}
    return resp.result or {}
