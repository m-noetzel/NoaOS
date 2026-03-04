"""Responder node — formats final response and tracks cost.

Spec refs: SPEC.md S7.1 (responder node: cost, format).
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState

# Placeholder cost-per-invocation (will be model-aware in later phases).
_ESTIMATED_COST_PER_CALL = 0.001


def responder_node(state: AgentState) -> dict[str, Any]:
    """Format response and update cost. Pure function."""
    response = state.get("response") or ""

    # If no response yet, synthesize from the last assistant message.
    if not response:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                response = msg.get("content", "")
                break

    # If still empty, provide a fallback.
    if not response:
        response = "I'm sorry, I couldn't generate a response."

    # Cost tracking (S2.1 — cost and iteration limits are fixed).
    previous_cost: float = state.get("total_cost", 0.0)
    total_cost = previous_cost + _ESTIMATED_COST_PER_CALL

    return {
        "response": response,
        "total_cost": total_cost,
    }
