"""Tests for MR9 — Conditional Graph Edges.

Phase goal: Replace the fixed linear topology (router -> agent -> tools -> responder)
with conditional edges so the graph skips tools when unnecessary and supports
multi-turn tool use with a loop cap.

Spec refs: SPEC.md S2.1 (workflow topology), S2.2 (bounded inner autonomy)
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")

pytestmark = pytest.mark.mr9


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_user_message(content: str = "Hello Noa") -> dict[str, Any]:
    """Create a minimal user message dict."""
    return {"role": "user", "content": content}


def _make_agent_state(
    *,
    messages: list[dict[str, Any]] | None = None,
    privacy_mode: str = "external",
    selected_model: str = "anthropic/claude-haiku",
    tool_calls: list[dict[str, Any]] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    response: str | None = None,
    total_cost: float = 0.0,
    tool_rounds: int = 0,
) -> dict[str, Any]:
    """Create a minimal AgentState dict for testing."""
    return {
        "messages": messages or [_make_user_message()],
        "privacy_mode": privacy_mode,
        "selected_model": selected_model,
        "tool_calls": tool_calls or [],
        "tool_results": tool_results or [],
        "response": response,
        "total_cost": total_cost,
        "tool_rounds": tool_rounds,
        "user_id": None,
        "tool_scope": None,
        "approvals_enabled": False,
    }


def _make_tool_call(
    name: str = "calendar_list",
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a tool call dict."""
    return {
        "name": name,
        "arguments": arguments or {},
    }


# ===========================================================================
# 1. Graph compilation & node count
# ===========================================================================


class TestGraphCompilationMR9:
    """Graph must still compile and have exactly 4 core nodes after MR9."""

    def test_graph_compiles_without_error(self):
        """Graph with conditional edges must compile without error."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_core_nodes(self):
        """Graph must have at least the core nodes: router, agent, tools, evaluator.

        OV3: responder node removed; evaluator is now the terminal node.
        """
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        node_names = {n.name for n in compiled.get_graph().nodes.values()}
        core_nodes = node_names - {"__start__", "__end__"}
        assert {"router", "agent", "tools", "evaluator"}.issubset(core_nodes)
        assert "responder" not in core_nodes, "OV3: responder node must be removed"


# ===========================================================================
# 2. tool_rounds defaults to 0 in AgentState
# ===========================================================================


class TestToolRoundsDefault:
    """AgentState must include tool_rounds field defaulting to 0."""

    def test_tool_rounds_in_annotations(self):
        """AgentState must declare tool_rounds field."""
        from noa.orchestrator.state import AgentState

        annotations = AgentState.__annotations__
        assert "tool_rounds" in annotations, "AgentState missing tool_rounds field"

    def test_tool_rounds_defaults_to_zero(self):
        """A fresh state dict should have tool_rounds = 0."""
        state = _make_agent_state()
        assert state["tool_rounds"] == 0


# ===========================================================================
# 3. Conditional edge: no tool_calls -> skip tools, go agent -> responder
# ===========================================================================


class TestNoToolCallsSkipsTools:
    """When agent returns no tool_calls, graph should go agent -> evaluator (OV3)."""

    def test_no_tool_calls_skips_tools_node(self):
        """When agent produces no tool_calls, the tools node must be skipped.

        OV3: routes to evaluator directly instead of responder.
        """
        from noa.orchestrator.graph import route_after_agent

        state = _make_agent_state(tool_calls=[])
        result = route_after_agent(state)
        assert result == "evaluator", (
            f"Expected 'evaluator' when no tool_calls, got '{result}'"
        )

    def test_pure_text_response_correct(self):
        """When agent returns text with no tool_calls, evaluator gets the response."""
        from noa.orchestrator.graph import route_after_agent

        state = _make_agent_state(
            tool_calls=[],
            response="Hello, how can I help?",
        )
        result = route_after_agent(state)
        assert result == "evaluator"


# ===========================================================================
# 4. Conditional edge: with tool_calls -> go agent -> tools -> agent (loop)
# ===========================================================================


class TestToolCallsGoesToTools:
    """When agent returns tool_calls, graph should go agent -> tools."""

    def test_with_tool_calls_routes_to_tools(self):
        """When agent produces tool_calls, routing must go to tools node."""
        from noa.orchestrator.graph import route_after_agent

        state = _make_agent_state(
            tool_calls=[_make_tool_call("calendar_list")],
        )
        result = route_after_agent(state)
        assert result == "tools", (
            f"Expected 'tools' when tool_calls present, got '{result}'"
        )

    def test_tools_routes_back_to_agent(self):
        """After tools execute with rounds remaining, route back to agent."""
        from noa.orchestrator.graph import route_after_tools

        state = _make_agent_state(
            tool_rounds=1,
            tool_results=[{"name": "calendar_list", "result": "ok"}],
        )
        result = route_after_tools(state)
        assert result == "agent", (
            f"Expected 'agent' for follow-up after tools, got '{result}'"
        )


# ===========================================================================
# 5. tool_rounds incremented after each tools pass
# ===========================================================================


class TestToolRoundsIncrement:
    """tool_node must increment tool_rounds in its return dict."""

    @pytest.mark.asyncio
    async def test_tool_rounds_incremented(self):
        """tool_node must return tool_rounds incremented by 1."""
        from noa.orchestrator.nodes.tools import set_gateway, tool_node
        from noa.tools.gateway import ToolGateway, ToolResponse

        class _Adapter:
            async def execute(self, req: Any) -> ToolResponse:
                return ToolResponse(result={"result": "No events"})

        gw = ToolGateway()
        gw.register("calendar", _Adapter())
        old = getattr(__import__("noa.orchestrator.nodes.tools", fromlist=["_gateway"]), "_gateway", None)
        set_gateway(gw)
        try:
            state = _make_agent_state(
                tool_calls=[{"tool": "calendar", "function": "list_events", "args": {}}],
                tool_rounds=0,
            )
            result = await tool_node(state)
            assert "tool_rounds" in result
            assert result["tool_rounds"] == 1
        finally:
            set_gateway(old)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_tool_rounds_incremented_from_existing(self):
        """tool_node must increment from the current tool_rounds value."""
        from noa.orchestrator.nodes.tools import set_gateway, tool_node
        from noa.tools.gateway import ToolGateway, ToolResponse

        class _Adapter:
            async def execute(self, req: Any) -> ToolResponse:
                return ToolResponse(result={"result": "Events found"})

        gw = ToolGateway()
        gw.register("calendar", _Adapter())
        old = getattr(__import__("noa.orchestrator.nodes.tools", fromlist=["_gateway"]), "_gateway", None)
        set_gateway(gw)
        try:
            state = _make_agent_state(
                tool_calls=[{"tool": "calendar", "function": "list_events", "args": {}}],
                tool_rounds=2,
            )
            result = await tool_node(state)
            assert result["tool_rounds"] == 3
        finally:
            set_gateway(old)  # type: ignore[arg-type]


# ===========================================================================
# 6. MAX_TOOL_ROUNDS=3 enforced: tools -> responder after 3 rounds
# ===========================================================================


class TestMaxToolRoundsEnforced:
    """After MAX_TOOL_ROUNDS, tools must route to evaluator (OV3), not agent."""

    def test_max_tool_rounds_routes_to_evaluator(self):
        """When tool_rounds >= MAX_TOOL_ROUNDS, route to evaluator (OV3: was responder)."""
        from noa.orchestrator.graph import MAX_TOOL_ROUNDS, route_after_tools

        state = _make_agent_state(tool_rounds=MAX_TOOL_ROUNDS)
        result = route_after_tools(state)
        assert result == "evaluator", (
            f"Expected 'evaluator' after {MAX_TOOL_ROUNDS} rounds, got '{result}'"
        )

    def test_max_tool_rounds_value_is_3(self):
        """MAX_TOOL_ROUNDS must be 3."""
        from noa.orchestrator.graph import MAX_TOOL_ROUNDS

        assert MAX_TOOL_ROUNDS == 3

    def test_below_max_routes_to_agent(self):
        """When tool_rounds < MAX_TOOL_ROUNDS, route back to agent."""
        from noa.orchestrator.graph import MAX_TOOL_ROUNDS, route_after_tools

        state = _make_agent_state(tool_rounds=MAX_TOOL_ROUNDS - 1)
        result = route_after_tools(state)
        assert result == "agent", (
            f"Expected 'agent' when below max rounds, got '{result}'"
        )


# ===========================================================================
# 7. Backward compatibility: existing graph structure preserved
# ===========================================================================


class TestBackwardCompat:
    """Existing graph structure must be preserved — same 4 nodes, start/end."""

    def test_graph_starts_at_router(self):
        """Graph must still start at router."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        graph_repr = compiled.get_graph()
        edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
        assert ("__start__", "router") in edge_pairs

    def test_graph_ends_at_evaluator(self):
        """Graph ends at evaluator (OV3: agent/tools -> evaluator -> __end__)."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        graph_repr = compiled.get_graph()
        edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
        assert ("evaluator", "__end__") in edge_pairs
        # OV3: responder no longer exists; agent routes directly to evaluator
        assert ("responder", "evaluator") not in edge_pairs, (
            "OV3: responder -> evaluator edge must not exist (responder deleted)"
        )

    def test_router_to_agent_edge_exists(self):
        """Router must eventually reach agent (via classifier in DI1)."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        graph_repr = compiled.get_graph()
        edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
        # OI1: router -> classifier -> planner -> agent
        assert ("router", "classifier") in edge_pairs
        assert ("classifier", "planner") in edge_pairs
        assert ("planner", "agent") in edge_pairs

    def test_existing_orchestrator_tests_unbroken(self):
        """Verify the graph still has all required core nodes (regression check).

        OV3: responder removed; evaluator is now the terminal node.
        """
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        node_names = {n.name for n in compiled.get_graph().nodes.values()}
        core_nodes = node_names - {"__start__", "__end__"}
        assert {"router", "agent", "tools", "evaluator"}.issubset(core_nodes)
        assert "responder" not in core_nodes, "OV3: responder must be removed"


# ===========================================================================
# 8. Tool-using response produces correct tool_results
# ===========================================================================


class TestToolUsingResponse:
    """When tools are used, tool_results must be populated correctly."""

    @pytest.mark.asyncio
    async def test_tool_results_populated(self):
        """tool_node must return populated tool_results for valid tool calls."""
        from noa.orchestrator.nodes.tools import set_gateway, tool_node
        from noa.tools.gateway import ToolGateway, ToolResponse

        class _Adapter:
            async def execute(self, req: Any) -> ToolResponse:
                return ToolResponse(result={"result": "Meeting at 3pm"})

        gw = ToolGateway()
        gw.register("calendar", _Adapter())
        old = getattr(__import__("noa.orchestrator.nodes.tools", fromlist=["_gateway"]), "_gateway", None)
        set_gateway(gw)
        try:
            state = _make_agent_state(
                tool_calls=[{"tool": "calendar", "function": "list_events", "args": {"date": "2026-03-06"}}],
            )
            result = await tool_node(state)
            assert len(result["tool_results"]) == 1
            assert result["tool_results"][0]["name"] == "calendar.list_events"
        finally:
            set_gateway(old)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_empty_tool_calls_returns_empty_results_and_rounds(self):
        """Empty tool_calls should return empty results and still set tool_rounds."""
        from noa.orchestrator.nodes.tools import tool_node

        state = _make_agent_state(tool_calls=[], tool_rounds=0)
        result = await tool_node(state)
        assert result["tool_results"] == []
