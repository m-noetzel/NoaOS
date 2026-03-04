"""Tool node — enforces static allowlist and dispatches tools.

Spec refs: SPEC.md S2.1 (tool allowlists are static per workflow),
           SPEC.md S2.2 (LLM may NOT execute tools not in allowlist).

execute_tool is a module-level function so tests can patch it easily.
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState

# Static tool allowlist (S2.1).
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


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Execute a tool by name. Patched in tests; real dispatch in later phase."""
    msg = "execute_tool requires real tool backends (not yet wired)"
    raise NotImplementedError(msg)


def tool_node(state: AgentState) -> dict[str, Any]:
    """Dispatch tool calls through the allowlist filter. Pure function."""
    tool_calls: list[dict[str, Any]] = state.get("tool_calls", [])

    if not tool_calls:
        return {"tool_results": []}

    results: list[dict[str, Any]] = []
    for call in tool_calls:
        name = call.get("name", "")
        arguments = call.get("arguments", {})

        if name not in TOOL_ALLOWLIST:
            results.append(
                {
                    "name": name,
                    "error": f"Tool not allowed: {name}. Denied by static allowlist.",
                }
            )
        else:
            result = execute_tool(name, arguments)
            results.append({"name": name, **result})

    return {"tool_results": results}
