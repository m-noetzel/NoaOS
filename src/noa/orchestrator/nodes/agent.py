"""Agent node — invokes LLM with bounded autonomy.

Spec refs: SPEC.md S2.2 (bounded inner autonomy, max tool calls).

invoke_llm is a module-level function so tests can patch it easily.
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState

# Maximum tool calls the agent will forward per step (S2.1 cost/iteration limits).
MAX_TOOL_CALLS = 10


def invoke_llm(model: str, messages: list[dict[str, Any]]) -> Any:  # noqa: ARG001
    """Invoke the LLM. Patched in tests; real implementation in later phase."""
    msg = "invoke_llm requires a real LLM backend (not yet wired)"
    raise NotImplementedError(msg)


def agent_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM and return tool_calls / response. Pure function."""
    messages = state.get("messages", [])
    model = state.get("selected_model", "anthropic/claude-haiku")

    response = invoke_llm(model, messages)

    raw_tool_calls: list[dict[str, Any]] = getattr(response, "tool_calls", []) or []
    # Enforce bounded autonomy: cap tool calls.
    tool_calls = raw_tool_calls[:MAX_TOOL_CALLS]

    content: str = getattr(response, "content", "") or ""

    result: dict[str, Any] = {"tool_calls": tool_calls}

    if not tool_calls and content:
        result["response"] = content

    # Append assistant message to conversation.
    new_message: dict[str, Any] = {"role": "assistant", "content": content}
    result["messages"] = list(messages) + [new_message]

    return result
