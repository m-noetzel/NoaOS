"""Tests for OV3 — Remove Responder Node.

Phase goal: Delete the responder node entirely. Agent routes directly to
evaluator. Runner computes total_cost and response after graph loop.

Spec refs: SPEC.md S2.1 (workflow topology), S7.1 (cost, format)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")

pytestmark = pytest.mark.ov3


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_agent_state(**kwargs: Any) -> dict[str, Any]:
    """Create a minimal AgentState dict for testing."""
    base: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Hello"}],
        "privacy_mode": "external",
        "selected_model": "openai/gpt-4.1-mini",
        "tool_calls": [],
        "tool_results": [],
        "response": None,
        "total_cost": 0.0,
        "tool_rounds": 0,
        "llm_usage": [],
        "user_id": None,
        "tool_scope": None,
        "approvals_enabled": False,
        "max_retries": 3,
    }
    base.update(kwargs)
    return base


# ===========================================================================
# 1. Graph has no responder node
# ===========================================================================


class TestGraphNoResponder:
    """OV3: Graph must not contain a responder node."""

    def test_responder_node_not_in_graph(self) -> None:
        """Compiled graph must NOT contain the responder node."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        compiled = graph.compile()
        node_names = {n.name for n in compiled.get_graph().nodes.values()}
        assert "responder" not in node_names, (
            "OV3: responder node must be deleted from the graph"
        )

    def test_responder_module_deleted(self) -> None:
        """responder.py module must not be importable."""
        import importlib

        with pytest.raises(ImportError):
            importlib.import_module("noa.orchestrator.nodes.responder")

    def test_evaluator_present(self) -> None:
        """Evaluator node must still be present in the graph."""
        from noa.orchestrator.graph import build_graph

        graph = build_graph()
        assert "evaluator" in graph.nodes

    def test_graph_compiles(self) -> None:
        """Graph must compile successfully without the responder node."""
        from noa.orchestrator.graph import build_graph

        compiled = build_graph().compile()
        assert compiled is not None


# ===========================================================================
# 2. Agent -> evaluator routing when no tool_calls
# ===========================================================================


class TestAgentToEvaluatorRouting:
    """OV3: When agent produces no tool_calls, route to evaluator (not responder)."""

    def test_route_after_agent_no_tool_calls_goes_to_evaluator(self) -> None:
        """route_after_agent returns 'evaluator' when tool_calls is empty."""
        from noa.orchestrator.graph import route_after_agent

        state = _make_agent_state(tool_calls=[])
        result = route_after_agent(state)
        assert result == "evaluator", (
            f"Expected 'evaluator', got '{result}'"
        )

    def test_route_after_agent_with_tool_calls_goes_to_tools(self) -> None:
        """route_after_agent returns 'tools' when tool_calls is non-empty."""
        from noa.orchestrator.graph import route_after_agent

        state = _make_agent_state(
            tool_calls=[{"name": "web_search", "args": {"query": "python"}}],
        )
        result = route_after_agent(state)
        assert result == "tools", f"Expected 'tools', got '{result}'"

    def test_agent_evaluator_edge_in_compiled_graph(self) -> None:
        """Compiled graph must have an agent -> evaluator conditional edge."""
        from noa.orchestrator.graph import build_graph

        compiled = build_graph().compile()
        edge_pairs = {(e.source, e.target) for e in compiled.get_graph().edges}
        assert ("agent", "evaluator") in edge_pairs, (
            "OV3: agent must have direct conditional edge to evaluator"
        )


# ===========================================================================
# 3. Tools -> evaluator routing when max retries reached
# ===========================================================================


class TestToolsToEvaluatorRouting:
    """OV3: When tool_rounds >= max_retries, route to evaluator (not responder)."""

    def test_route_after_tools_max_retries_goes_to_evaluator(self) -> None:
        """route_after_tools returns 'evaluator' when tool_rounds >= max_retries."""
        from noa.orchestrator.graph import MAX_TOOL_ROUNDS, route_after_tools

        state = _make_agent_state(tool_rounds=MAX_TOOL_ROUNDS)
        result = route_after_tools(state)
        assert result == "evaluator", (
            f"Expected 'evaluator' after max rounds, got '{result}'"
        )

    def test_route_after_tools_below_max_goes_to_agent(self) -> None:
        """route_after_tools returns 'agent' when tool_rounds < max_retries."""
        from noa.orchestrator.graph import MAX_TOOL_ROUNDS, route_after_tools

        state = _make_agent_state(tool_rounds=MAX_TOOL_ROUNDS - 1)
        result = route_after_tools(state)
        assert result == "agent", (
            f"Expected 'agent' below max rounds, got '{result}'"
        )

    def test_tools_evaluator_edge_in_compiled_graph(self) -> None:
        """Compiled graph must have a tools -> evaluator conditional edge."""
        from noa.orchestrator.graph import build_graph

        compiled = build_graph().compile()
        edge_pairs = {(e.source, e.target) for e in compiled.get_graph().edges}
        assert ("tools", "evaluator") in edge_pairs, (
            "OV3: tools must have direct conditional edge to evaluator"
        )


# ===========================================================================
# 4. Runner computes total_cost from llm_usage
# ===========================================================================


class TestRunnerCostComputation:
    """OV3: Runner computes total_cost from llm_usage after graph loop."""

    def test_extract_response_with_direct_response(self) -> None:
        """_extract_response returns response field when non-empty."""
        from noa.orchestrator.runner import OrchestratorRunner

        result = {"response": "Hello there!", "messages": [], "llm_usage": []}
        assert OrchestratorRunner._extract_response(result) == "Hello there!"

    def test_total_cost_summed_from_llm_usage(self) -> None:
        """Runner sums cost_usd from all llm_usage entries."""
        # Verify the logic: sum of cost_usd fields
        llm_usage = [
            {"node": "classifier", "cost_usd": 0.001},
            {"node": "agent", "cost_usd": 0.005},
            {"node": "evaluator", "cost_usd": 0.002},
        ]
        total = sum(entry.get("cost_usd", 0.0) for entry in llm_usage)
        assert abs(total - 0.008) < 1e-9

    def test_total_cost_zero_when_no_usage(self) -> None:
        """Total cost is 0.0 when llm_usage is empty."""
        llm_usage: list[dict[str, Any]] = []
        total = sum(entry.get("cost_usd", 0.0) for entry in llm_usage)
        assert total == 0.0

    @pytest.mark.asyncio
    async def test_runner_emits_result_ready_with_cost(self) -> None:
        """Runner emits result_ready with computed total_cost after graph loop."""
        from noa.orchestrator.runner import OrchestratorRunner

        async def _fake_astream(state: Any, config: Any = None) -> Any:
            yield {
                "agent": {
                    "response": "The answer is 42.",
                    "llm_usage": [
                        {"node": "agent", "cost_usd": 0.003},
                        {"node": "evaluator", "cost_usd": 0.001},
                    ],
                    "tool_calls": [],
                    "tool_results": [],
                    "eval_scores": None,
                    "eval_verdict": "pass",
                    "eval_cycle": 0,
                    "messages": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.run(
            message="What is 6*7?",
            run_service=mock_run_service,
            run_id="test-ov3-cost",
        ):
            events.append(event)

        result_ready_events = [e for e in events if e["event_type"] == "result_ready"]
        assert len(result_ready_events) == 1, (
            f"Expected 1 result_ready, got {len(result_ready_events)}. "
            f"Event types: {[e['event_type'] for e in events]}"
        )
        payload = result_ready_events[0]["payload"]
        assert payload["response"] == "The answer is 42."
        assert abs(payload["total_cost"] - 0.004) < 1e-9


# ===========================================================================
# 5. Runner extracts response with fallback logic
# ===========================================================================


class TestRunnerExtractResponse:
    """OV3: _extract_response() implements the fallback chain from deleted responder."""

    def test_uses_response_field_when_present(self) -> None:
        """Returns result['response'] when non-empty."""
        from noa.orchestrator.runner import OrchestratorRunner

        result = {
            "response": "Direct response.",
            "messages": [{"role": "assistant", "content": "Alt content"}],
        }
        assert OrchestratorRunner._extract_response(result) == "Direct response."

    def test_falls_back_to_last_assistant_message(self) -> None:
        """Falls back to last non-empty assistant message when response is None."""
        from noa.orchestrator.runner import OrchestratorRunner

        result = {
            "response": None,
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "First response."},
                {"role": "assistant", "content": "Second response."},
            ],
        }
        # Last non-empty assistant message wins
        assert OrchestratorRunner._extract_response(result) == "Second response."

    def test_skips_empty_assistant_messages(self) -> None:
        """Skips assistant messages with empty content when building fallback."""
        from noa.orchestrator.runner import OrchestratorRunner

        result = {
            "response": "",
            "messages": [
                {"role": "user", "content": "Run this tool"},
                {"role": "assistant", "content": ""},  # tool-call message
                {"role": "tool", "content": "result data"},
                {"role": "assistant", "content": "Tool completed."},
            ],
        }
        assert OrchestratorRunner._extract_response(result) == "Tool completed."

    def test_last_resort_fallback(self) -> None:
        """Returns 'I'm sorry...' when no response and no non-empty assistant messages."""
        from noa.orchestrator.runner import OrchestratorRunner

        result = {
            "response": None,
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": ""},
            ],
        }
        response = OrchestratorRunner._extract_response(result)
        assert response == "I'm sorry, I couldn't generate a response."

    def test_no_tool_name_synthesis(self) -> None:
        """OV3: Does NOT synthesize tool-name messages (ARCH-RS1 fix).

        The old responder generated 'I completed the requested actions using
        {tool_names}' which was false/misleading. _extract_response must not
        produce this kind of fabricated message.
        """
        from noa.orchestrator.runner import OrchestratorRunner

        result = {
            "response": None,
            "messages": [
                {"role": "user", "content": "Search for news"},
                {"role": "assistant", "content": ""},
            ],
            "tool_results": [{"name": "web_search", "result": "some data"}],
        }
        response = OrchestratorRunner._extract_response(result)
        # Should NOT contain fabricated tool-name message
        assert "completed the requested actions" not in response
        assert "web_search" not in response
        # Should be the last-resort fallback
        assert response == "I'm sorry, I couldn't generate a response."


# ===========================================================================
# 6. result_ready event emitted after graph loop completes
# ===========================================================================


class TestResultReadyAfterGraphLoop:
    """OV3: result_ready is emitted by runner after graph loop, not by a node."""

    @pytest.mark.asyncio
    async def test_result_ready_emitted_once(self) -> None:
        """Runner emits exactly one result_ready event."""
        from noa.orchestrator.runner import OrchestratorRunner

        async def _fake_astream(state: Any, config: Any = None) -> Any:
            yield {
                "agent": {
                    "response": "Done.",
                    "llm_usage": [],
                    "tool_calls": [],
                    "tool_results": [],
                    "eval_scores": None,
                    "eval_verdict": "pass",
                    "eval_cycle": 0,
                    "messages": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.run(
            message="hello",
            run_service=mock_run_service,
            run_id="test-ov3-rr",
        ):
            events.append(event)

        result_ready = [e for e in events if e["event_type"] == "result_ready"]
        assert len(result_ready) == 1, (
            f"Expected exactly 1 result_ready, got {len(result_ready)}"
        )

    @pytest.mark.asyncio
    async def test_result_ready_payload_structure(self) -> None:
        """result_ready payload has response, total_cost, and llm_usage keys."""
        from noa.orchestrator.runner import OrchestratorRunner

        async def _fake_astream(state: Any, config: Any = None) -> Any:
            yield {
                "agent": {
                    "response": "Answer here.",
                    "llm_usage": [{"node": "agent", "cost_usd": 0.002}],
                    "tool_calls": [],
                    "tool_results": [],
                    "eval_scores": None,
                    "eval_verdict": "pass",
                    "eval_cycle": 0,
                    "messages": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.run(
            message="hi",
            run_service=mock_run_service,
            run_id="test-ov3-payload",
        ):
            events.append(event)

        rr = next(e for e in events if e["event_type"] == "result_ready")
        payload = rr["payload"]
        assert "response" in payload
        assert "total_cost" in payload
        assert "llm_usage" in payload
        assert payload["response"] == "Answer here."
        assert abs(payload["total_cost"] - 0.002) < 1e-9
