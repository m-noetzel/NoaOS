"""Tool node — dispatches tool calls through ToolGateway.

Spec refs: SPEC.md S2.1 (tool allowlists are static per workflow),
           SPEC.md S2.2 (LLM may NOT execute tools not in allowlist).

All tool dispatch flows through ToolGateway (set via set_gateway at startup).
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from noa.orchestrator.state import AgentState
from noa.tools.gateway import ToolGateway, ToolRequest
from noa.validation.content_filter import scan_output_recursive

logger = logging.getLogger(__name__)

# Max tool output size (1 MB) — matches validation pipeline default.
_MAX_TOOL_OUTPUT_BYTES = 1 * 1024 * 1024

# Doom loop detection: if the same (tool, args) signature appears this many
# times in the last _DOOM_LOOP_WINDOW tool results, break the loop.
_DOOM_LOOP_THRESHOLD = 3
_DOOM_LOOP_WINDOW = 6


class DoomLoopError(Exception):
    """Raised when the same tool+args signature repeats too many times."""


def _tool_signature(tool_name: str, args: dict[str, Any]) -> str:
    """Stable signature for a tool call (order-independent)."""
    return _json.dumps({"t": tool_name, "a": args}, sort_keys=True)


def _check_doom_loop(
    tool_name: str, args: dict[str, Any], prior_results: list[dict[str, Any]],
) -> None:
    """Raise DoomLoopError if the same signature appears >= threshold times."""
    sig = _tool_signature(tool_name, args)
    window = prior_results[-_DOOM_LOOP_WINDOW:]
    count = sum(1 for r in window if r.get("_signature") == sig)
    if count >= _DOOM_LOOP_THRESHOLD:
        raise DoomLoopError(
            f"Doom loop detected: tool '{tool_name}' called with identical "
            f"arguments {count} times in last {_DOOM_LOOP_WINDOW} calls. "
            f"Breaking loop."
        )

# Module-level gateway reference, set at startup via set_gateway().
_gateway: ToolGateway | None = None


def set_gateway(gateway: ToolGateway) -> None:
    """Set the module-level ToolGateway. Called at app startup."""
    global _gateway  # noqa: PLW0603
    _gateway = gateway


def get_gateway() -> ToolGateway | None:
    """Get the current ToolGateway (or None if not configured)."""
    return _gateway


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Dispatch tool calls through the ToolGateway.

    Tool calls may use either format:
    - Registry format: {"tool": "calendar", "function": "list_events", "args": {...}}
    - Legacy format: {"name": "web_search__web_search", "input": {...}}

    All dispatch flows through ToolGateway (set via set_gateway at startup).
    """
    tool_calls: list[dict[str, Any]] = state.get("tool_calls", [])
    current_rounds: int = state.get("tool_rounds", 0)
    # W22-H2: Read approvals_enabled from state (default True = enforce approvals)
    approvals_enabled: bool = bool(state.get("approvals_enabled", True))
    user_id: str | None = state.get("user_id")
    # CQ1: Task-level tool scope filtering
    tool_scope: str | None = state.get("tool_scope")

    if not tool_calls:
        return {"tool_results": []}

    # CQ1: Resolve scope allowlist if set
    scope_allowlist: set[str] | None = None
    if tool_scope is not None:
        from noa.tools.scopes import ToolScopeRegistry

        registry = ToolScopeRegistry()
        try:
            scope_tools = registry.get_scope(tool_scope)
            scope_allowlist = set(scope_tools)
        except KeyError:
            # Unknown scope: block all tools
            logger.warning(
                "Unknown tool_scope=%s — blocking all tool calls",
                tool_scope,
            )
            scope_allowlist = set()

    prior_results: list[dict[str, Any]] = list(state.get("tool_results", []))

    results: list[dict[str, Any]] = []
    for call in tool_calls:
        # Support both registry-format and legacy-format tool calls.
        if "tool" in call and "function" in call:
            # Registry format: tool + function + args
            tool_name = call["tool"]
            function = call["function"]
            args = call.get("args", {})

            # CQ1: Scope filtering — reject tools not in scope
            if scope_allowlist is not None:
                call_key = f"{tool_name}__{function}"
                if call_key not in scope_allowlist:
                    results.append({
                        "name": f"{tool_name}.{function}",
                        "error": (
                            f"Tool {tool_name}.{function} "
                            f"not allowed in scope '{tool_scope}'."
                        ),
                    })
                    continue

            # CX1: Doom loop detection
            qualified = f"{tool_name}.{function}"
            try:
                _check_doom_loop(qualified, args, prior_results)
            except DoomLoopError as e:
                sig = _tool_signature(qualified, args)
                results.append({"name": qualified, "error": str(e), "_signature": sig})
                continue

            if _gateway is not None:
                result = await _dispatch_gateway(
                    tool_name, function, args,
                    approvals_enabled=approvals_enabled,
                    user_id=user_id,
                )
            else:
                result = {
                    "error": "ToolGateway not configured"
                    " — check app startup wiring",
                }
            sig = _tool_signature(qualified, args)
            results.append({"name": qualified, "_signature": sig, **result})
            prior_results.append({"name": qualified, "_signature": sig})
        else:
            # Legacy or LLM tool_use format:
            #   {"name": "web_search__web_search", "input": {...}}
            #   {"name": "calendar_list", "arguments": {...}}
            name = call.get("name", "")
            arguments = call.get("input") or call.get("arguments", {})

            # CQ1: Scope filtering for legacy format
            if scope_allowlist is not None and name not in scope_allowlist:
                results.append({
                    "name": name,
                    "error": f"Tool {name} not allowed in scope '{tool_scope}'.",
                })
                continue

            # CX1: Doom loop detection for legacy format
            try:
                _check_doom_loop(name, arguments, prior_results)
            except DoomLoopError as e:
                sig = _tool_signature(name, arguments)
                results.append({"name": name, "error": str(e), "_signature": sig})
                continue

            # Parse tool__function naming from definitions
            from noa.tools.definitions import parse_tool_call_name
            parsed_tool, parsed_func = parse_tool_call_name(name)
            if parsed_tool != name and _gateway is not None:
                result = await _dispatch_gateway(
                    parsed_tool, parsed_func, arguments,
                    approvals_enabled=approvals_enabled,
                    user_id=user_id,
                )
                results.append({"name": name, **result})
                continue

            # No gateway configured — cannot dispatch
            results.append({
                "name": name,
                "error": f"Tool not registered: {name}. ToolGateway not configured.",
            })

    # Validate and append tool results as messages so the LLM sees them
    msgs = list(state.get("messages", []))
    for idx, res in enumerate(results):
        tool_call = tool_calls[idx] if idx < len(tool_calls) else {}
        tool_name = res.get("name", "")

        # Skip validation for error responses (nothing to filter)
        if not res.get("error"):
            res = _validate_tool_output(res, tool_name)
            results[idx] = res

        content = res.get("error") or _json.dumps(
            {k: v for k, v in res.items() if k != "name"},
            default=str,
        )
        msgs.append({
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "name": tool_name,
            "content": content,
        })

    return {
        "tool_results": results,
        "tool_rounds": current_rounds + 1,
        "messages": msgs,
    }


def _validate_tool_output(
    result: dict[str, Any], tool_name: str,
) -> dict[str, Any]:
    """Validate tool output for size and malicious content.

    Returns the original result if clean, or an error dict if blocked.
    """
    # Size check
    try:
        size = len(_json.dumps(result, default=str))
    except (TypeError, ValueError):
        size = 0
    if size > _MAX_TOOL_OUTPUT_BYTES:
        logger.warning(
            "Tool %s output blocked: %d bytes exceeds %d limit",
            tool_name, size, _MAX_TOOL_OUTPUT_BYTES,
        )
        return {
            "name": result.get("name", tool_name),
            "error": (
                f"Tool output too large ({size} bytes). "
                f"Limit is {_MAX_TOOL_OUTPUT_BYTES}."
            ),
        }

    # Content filter — prompt injection, exfiltration URLs, system prompt leaks
    filter_result = scan_output_recursive(result)
    if not filter_result.passed:
        issues = "; ".join(filter_result.issues)
        logger.warning(
            "Tool %s output blocked by content filter: %s", tool_name, issues,
        )
        return {
            "name": result.get("name", tool_name),
            "error": f"Tool output blocked by content filter: {issues}",
        }

    return result


async def _dispatch_gateway(
    tool_name: str,
    function: str,
    args: dict[str, Any],
    *,
    approvals_enabled: bool = True,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Dispatch through the ToolGateway."""
    import uuid as _uuid

    assert _gateway is not None  # noqa: S101
    req = ToolRequest(
        tool=tool_name,
        function=function,
        args=args,
        user_id=_uuid.UUID(user_id) if user_id else None,
    )
    try:
        resp = await _gateway.dispatch(req, approvals_enabled=approvals_enabled)
        return _gateway_response_to_dict(resp)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _gateway_response_to_dict(resp: Any) -> dict[str, Any]:
    """Convert a ToolResponse to a plain dict for tool_results."""
    if resp.error:
        result = resp.result
        # Approval required — pass through the approval details
        if isinstance(result, dict) and result.get("approval_required"):
            return {"approval_required": True, **result, "error": resp.error}
        return {"error": resp.error}
    result = resp.result
    if result is None:
        return {}
    # If the tool returns a list (e.g. search results), wrap it
    if isinstance(result, list):
        return {"results": result}
    if isinstance(result, dict):
        return result
    return {"value": result}
