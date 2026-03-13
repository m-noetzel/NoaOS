"""LangGraph state machine — deterministic outer shell.

Spec ref: SPEC.md S2.1 (workflow topology is fixed:
router -> agent -> tools -> responder).

MR9: Conditional edges replace fixed linear topology.
- agent -> tools (if tool_calls) or agent -> responder (if no tool_calls)
- tools -> agent (if tool_rounds < MAX_TOOL_ROUNDS) or tools -> responder (if done)

build_graph() returns an uncompiled StateGraph.
Callers compile it via graph.compile() before invocation.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph

from noa.orchestrator.nodes.agent import agent_node
from noa.orchestrator.nodes.responder import responder_node
from noa.orchestrator.nodes.router import router_node
from noa.orchestrator.nodes.tools import tool_node
from noa.orchestrator.state import AgentState

# Maximum tool-execution rounds before forcing termination (MR9).
MAX_TOOL_ROUNDS: int = 3


def route_after_agent(state: dict[str, Any]) -> str:
    """Decide next node after agent: tools (if tool_calls) or responder.

    Spec ref: SPEC.md S2.1 — skip tools when unnecessary.
    """
    tool_calls = state.get("tool_calls", [])
    if tool_calls:
        return "tools"
    return "responder"


def route_after_tools(state: dict[str, Any]) -> str:
    """Decide next node after tools: agent (for follow-up) or responder (if done).

    Caps at MAX_TOOL_ROUNDS to enforce bounded autonomy (S2.2).
    """
    tool_rounds: int = state.get("tool_rounds", 0)
    if tool_rounds >= MAX_TOOL_ROUNDS:
        return "responder"
    return "agent"


def build_graph() -> StateGraph[AgentState]:
    """Build the orchestrator graph with conditional edges.

    Topology:
        __start__ -> router -> agent --(conditional)--> tools | responder
        tools --(conditional)--> agent | responder
        responder -> __end__
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("responder", responder_node)

    # Set entry point
    graph.set_entry_point("router")

    # Fixed edge: router -> agent
    graph.add_edge("router", "agent")

    # Conditional edge: agent -> tools or agent -> responder
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "responder": "responder"},
    )

    # Conditional edge: tools -> agent or tools -> responder
    graph.add_conditional_edges(
        "tools",
        route_after_tools,
        {"agent": "agent", "responder": "responder"},
    )

    # Set finish point
    graph.set_finish_point("responder")

    return graph
