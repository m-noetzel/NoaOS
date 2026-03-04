"""LangGraph state machine — deterministic outer shell.

Spec ref: SPEC.md S2.1 (workflow topology is fixed:
router -> agent -> tools -> responder).

build_graph() returns an uncompiled StateGraph.
Callers compile it via graph.compile() before invocation.
"""

from __future__ import annotations

from langgraph.graph import StateGraph

from noa.orchestrator.nodes.agent import agent_node
from noa.orchestrator.nodes.responder import responder_node
from noa.orchestrator.nodes.router import router_node
from noa.orchestrator.nodes.tools import tool_node
from noa.orchestrator.state import AgentState


def build_graph() -> StateGraph[AgentState]:
    """Build the fixed-topology orchestrator graph.

    Topology: __start__ -> router -> agent -> tools -> responder -> __end__
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("responder", responder_node)

    # Set entry point
    graph.set_entry_point("router")

    # Fixed linear edges
    graph.add_edge("router", "agent")
    graph.add_edge("agent", "tools")
    graph.add_edge("tools", "responder")

    # Set finish point
    graph.set_finish_point("responder")

    return graph
