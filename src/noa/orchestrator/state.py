"""AgentState schema for the LangGraph orchestrator.

Spec ref: SPEC.md S2.1 -- state carried through every node.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Typed state dict flowing through every graph node.

    Fields:
        messages: Conversation history (user + assistant messages).
        privacy_mode: "private" or "external" -- set by router.
        selected_model: Model identifier chosen by router.
        tool_calls: Tool invocations requested by the agent node.
        tool_results: Results returned by the tools node.
        response: Final formatted response string.
        total_cost: Cumulative cost tracker (USD estimate).
        tool_rounds: Number of tool-execution rounds completed (MR9 loop cap).
    """

    messages: list[dict[str, Any]]
    privacy_mode: str
    selected_model: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    response: str | None
    total_cost: float
    tool_rounds: int
