"""LangGraph state machine — deterministic outer shell.

Spec ref: SPEC.md S2.1 (workflow topology is fixed:
router -> agent -> tools -> evaluator).

MR9: Conditional edges replace fixed linear topology.
- agent -> tools (if tool_calls) or agent -> evaluator (if no tool_calls)
- tools -> agent (if tool_rounds < MAX_TOOL_ROUNDS) or tools -> evaluator (if done)

OV3: Responder node removed. Cost summation and response fallback moved to
runner._extract_response() and computed after graph loop completes.

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
from noa.orchestrator.nodes.router import router_node
from noa.orchestrator.nodes.tools import tool_node
from noa.orchestrator.state import AgentState

# Maximum tool-execution rounds before forcing termination (MR9).
MAX_TOOL_ROUNDS: int = 3


def route_after_classifier(state: dict[str, Any]) -> str:
    """Decide next node after classifier: agent (simple_utility) or planner.

    OV5/PERF-CL1: simple_utility tasks skip the planner entirely to avoid
    an unnecessary LLM call.  All other task types go through the planner.
    """
    task_type = state.get("task_type", "")
    if task_type == "simple_utility":
        return "agent"
    return "planner"


def route_after_agent(state: dict[str, Any]) -> str:
    """Decide next node after agent: tools (if tool_calls) or evaluator.

    Spec ref: SPEC.md S2.1 — skip tools when unnecessary.
    OV3: Routes directly to evaluator instead of responder.
    """
    tool_calls = state.get("tool_calls", [])
    if tool_calls:
        return "tools"
    return "evaluator"


def route_after_tools(state: dict[str, Any]) -> str:
    """Decide next node after tools: agent (for follow-up) or evaluator (if done).

    Caps at max_retries from state (user-configured) or MAX_TOOL_ROUNDS as
    fallback, to enforce bounded autonomy (S2.2).

    OV2: The approval_required branch is removed.  interrupt() in tool_node
    pauses the graph natively before routing occurs.  The graph only reaches
    this function after the interrupt resolves (approved or denied).

    OV3: Routes directly to evaluator instead of responder when done.
    """
    tool_rounds = int(state.get("tool_rounds", 0))
    max_retries = int(state.get("max_retries") or MAX_TOOL_ROUNDS)
    if tool_rounds >= max_retries:
        return "evaluator"
    return "agent"


def route_after_evaluator(state: dict[str, Any]) -> str:
    """Decide next node after evaluator: __end__ or agent (reroute).

    - "pass" or "flag" -> __end__
    - "reroute" and eval_cycle < max_cycles -> "agent" (feedback already injected)
    - "reroute" and eval_cycle >= max_cycles -> __end__ (max cycles reached)

    max_cycles is read from eval_config so it stays consistent with the
    evaluator's own cycle-cap logic (OV4).
    """
    verdict = state.get("eval_verdict", "pass")
    eval_cycle = int(state.get("eval_cycle") or 0)
    eval_config = state.get("eval_config") or {}
    max_cycles = int(eval_config.get("max_cycles") or 2)

    if verdict == "reroute" and eval_cycle < max_cycles:
        return "agent"
    return "__end__"


def build_graph() -> StateGraph[AgentState]:
    """Build the orchestrator graph with conditional edges.

    Topology:
        __start__ -> router -> classifier --(conditional)--> planner | agent
        planner -> agent
        agent --(conditional)--> tools | evaluator
        tools --(conditional)--> agent | evaluator
        evaluator --(conditional)--> __end__ | agent (reroute, max 2 cycles)

    OV5: classifier routes simple_utility directly to agent (skip planner).

    OV3: Responder node removed. Agent routes directly to evaluator.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("classifier", classifier_node)
    graph.add_node("planner", planner_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("evaluator", evaluator_node)

    # Set entry point
    graph.set_entry_point("router")

    # Fixed edges: router -> classifier, planner -> agent
    graph.add_edge("router", "classifier")
    graph.add_edge("planner", "agent")

    # Conditional edge: classifier -> agent (simple_utility) or planner (OV5)
    graph.add_conditional_edges(
        "classifier",
        route_after_classifier,
        {"agent": "agent", "planner": "planner"},
    )

    # Conditional edge: agent -> tools or agent -> evaluator (OV3: was responder)
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "evaluator": "evaluator"},
    )

    # Conditional edge: tools -> agent or tools -> evaluator (OV3: was responder)
    graph.add_conditional_edges(
        "tools",
        route_after_tools,
        {"agent": "agent", "evaluator": "evaluator"},
    )

    # Conditional edge: evaluator -> __end__ or evaluator -> agent (reroute)
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"__end__": "__end__", "agent": "agent"},
    )

    return graph
