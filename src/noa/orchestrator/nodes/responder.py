"""Responder node — formats final response and tracks cost.

Spec refs: SPEC.md S7.1 (responder node: cost, format).
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState


def responder_node(state: AgentState) -> dict[str, Any]:
    """Format response and update cost. Pure function."""
    response = state.get("response") or ""

    # If no response yet, synthesize from the last assistant message.
    if not response:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                candidate = msg.get("content", "")
                if candidate:
                    response = candidate
                    break

    # If still empty after tool rounds, check if tool results contain
    # useful content we can summarize (the LLM returned empty content
    # after processing tool results — this is the actual bug scenario).
    if not response:
        tool_results = state.get("tool_results", [])
        if tool_results:
            # The LLM processed tools but produced no text.
            # Rather than showing "I'm sorry", indicate what happened.
            tool_names = [
                r.get("name", "unknown") for r in tool_results
            ]
            response = (
                f"I completed the requested actions using "
                f"{', '.join(tool_names)}, but wasn't able to "
                f"formulate a summary. Please ask me to elaborate "
                f"on the results."
            )

    # Last resort fallback.
    if not response:
        response = "I'm sorry, I couldn't generate a response."

    # Sum real cost from accumulated llm_usage records.
    llm_usage: list[dict[str, Any]] = state.get("llm_usage", [])
    total_cost = sum(entry.get("cost_usd", 0.0) for entry in llm_usage)

    return {
        "response": response,
        "total_cost": total_cost,
    }
