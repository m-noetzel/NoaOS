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
from noa.orchestrator.nodes.classifier import classifier_node
from noa.orchestrator.nodes.evaluator import evaluator_node
from noa.orchestrator.nodes.planner import planner_node
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

    Caps at max_retries from state (user-configured) or MAX_TOOL_ROUNDS as
    fallback, to enforce bounded autonomy (S2.2).

    If any tool result requires approval, stop the loop immediately and
    go to responder — the approval_requested SSE event will be emitted
    by the runner, preventing an infinite retry loop.
    """
    # Stop immediately if any tool needs approval
    tool_results = state.get("tool_results", [])
    for tr in tool_results:
        if isinstance(tr, dict) and tr.get("approval_required"):
            return "responder"

    tool_rounds = int(state.get("tool_rounds", 0))
    max_retries = int(state.get("max_retries") or MAX_TOOL_ROUNDS)
    if tool_rounds >= max_retries:
        return "responder"
    return "agent"


def route_after_evaluator(state: dict[str, Any]) -> str:
    """Decide next node after evaluator: __end__ or agent (reroute).

    - "pass" or "flag" -> __end__
    - "reroute" and eval_cycle < 2 -> "agent" (with feedback already injected)
    - "reroute" and eval_cycle >= 2 -> __end__ (max cycles reached)
    """
    verdict = state.get("eval_verdict", "pass")
    eval_cycle = int(state.get("eval_cycle") or 0)

    if verdict == "reroute" and eval_cycle < 2:
        return "agent"
    return "__end__"


def build_graph() -> StateGraph[AgentState]:
    """Build the orchestrator graph with conditional edges.

    Topology:
        __start__ -> router -> classifier -> planner -> agent
        agent --(conditional)--> tools | responder
        tools --(conditional)--> agent | responder
        responder -> evaluator
        evaluator --(conditional)--> __end__ | agent (reroute, max 2 cycles)
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("classifier", classifier_node)
    graph.add_node("planner", planner_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("responder", responder_node)
    graph.add_node("evaluator", evaluator_node)

    # Set entry point
    graph.set_entry_point("router")

    # Fixed edges: router -> classifier -> planner -> agent
    graph.add_edge("router", "classifier")
    graph.add_edge("classifier", "planner")
    graph.add_edge("planner", "agent")

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

    # Fixed edge: responder -> evaluator
    graph.add_edge("responder", "evaluator")

    # Conditional edge: evaluator -> __end__ or evaluator -> agent (reroute)
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"__end__": "__end__", "agent": "agent"},
    )

    return graph
