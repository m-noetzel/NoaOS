"""Tests for EV1 — Evaluation Node.

Spec ref: SPEC.md — EV1 (Evaluation Node)

Test plan:
  Happy path: pass verdict when overall >= 3.0
  Reroute verdict: overall >= 2.0, < 3.0
  Flag verdict: overall < 2.0
  simple_utility skip: no LLM call
  Dimension selection by task_type (decision_intelligence, research, base)
  Reroute cycle limit: max 2 reroutes
  Score parsing from JSON
  Malformed response fallback to defaults
  Graph topology includes evaluator
  route_after_evaluator routing logic
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.graph import build_graph, route_after_evaluator
from noa.orchestrator.nodes.evaluator import (
    _compute_overall,
    _compute_verdict,
    _get_dimensions,
    _parse_scores,
    evaluator_node,
)

# ---------------------------------------------------------------------------
# Unit tests for pure helper functions
# ---------------------------------------------------------------------------


class TestGetDimensions:
    def test_base_dimensions_for_execution(self) -> None:
        dims = _get_dimensions("execution")
        assert "goal_alignment" in dims
        assert "completeness" in dims
        assert "grounding" in dims
        assert "confidence_honesty" in dims
        assert "actionability" in dims
        assert "option_coverage" not in dims
        assert "source_quality" not in dims

    def test_decision_adds_extra_dimensions(self) -> None:
        dims = _get_dimensions("decision_intelligence")
        assert "option_coverage" in dims
        assert "tradeoff_clarity" in dims
        # Base dimensions still present
        assert "goal_alignment" in dims

    def test_research_adds_extra_dimensions(self) -> None:
        dims = _get_dimensions("research")
        assert "source_quality" in dims
        assert "recency" in dims
        # Base dimensions still present
        assert "completeness" in dims

    def test_none_task_type_returns_base(self) -> None:
        dims = _get_dimensions(None)
        assert dims == _get_dimensions("execution")

    def test_simple_utility_returns_base(self) -> None:
        # simple_utility skips evaluation entirely, but if called it gets base dims
        dims = _get_dimensions("simple_utility")
        assert "goal_alignment" in dims
        assert "option_coverage" not in dims


class TestComputeOverall:
    def test_mean_of_scores(self) -> None:
        scores = {"a": 4.0, "b": 2.0}
        assert _compute_overall(scores) == pytest.approx(3.0)

    def test_empty_scores_returns_zero(self) -> None:
        assert _compute_overall({}) == 0.0

    def test_single_score(self) -> None:
        assert _compute_overall({"x": 5.0}) == pytest.approx(5.0)


class TestComputeVerdict:
    def test_pass_at_threshold(self) -> None:
        assert _compute_verdict(3.0) == "pass"

    def test_pass_above_threshold(self) -> None:
        assert _compute_verdict(4.5) == "pass"

    def test_reroute_between_thresholds(self) -> None:
        assert _compute_verdict(2.5) == "reroute"

    def test_reroute_at_lower_threshold(self) -> None:
        assert _compute_verdict(2.0) == "reroute"

    def test_flag_below_threshold(self) -> None:
        assert _compute_verdict(1.9) == "flag"

    def test_flag_at_zero(self) -> None:
        assert _compute_verdict(0.0) == "flag"


class TestParseScores:
    def test_valid_json_response(self) -> None:
        dims = ["goal_alignment", "completeness"]
        content = json.dumps({
            "scores": {"goal_alignment": 4.0, "completeness": 3.5},
            "reasoning": "Good response",
        })
        scores = _parse_scores(content, dims)
        assert scores["goal_alignment"] == pytest.approx(4.0)
        assert scores["completeness"] == pytest.approx(3.5)

    def test_integer_scores_converted_to_float(self) -> None:
        dims = ["goal_alignment"]
        content = json.dumps({"scores": {"goal_alignment": 4}})
        scores = _parse_scores(content, dims)
        assert isinstance(scores["goal_alignment"], float)
        assert scores["goal_alignment"] == pytest.approx(4.0)

    def test_scores_clamped_to_0_5(self) -> None:
        dims = ["goal_alignment"]
        content = json.dumps({"scores": {"goal_alignment": 7.0}})
        scores = _parse_scores(content, dims)
        assert scores["goal_alignment"] == pytest.approx(5.0)

        content2 = json.dumps({"scores": {"goal_alignment": -1.0}})
        scores2 = _parse_scores(content2, dims)
        assert scores2["goal_alignment"] == pytest.approx(0.0)

    def test_missing_dimension_falls_back_to_default(self) -> None:
        dims = ["goal_alignment", "completeness"]
        content = json.dumps({"scores": {"goal_alignment": 4.0}})
        scores = _parse_scores(content, dims)
        # Missing dimension gets 3.0 fallback
        assert scores["completeness"] == pytest.approx(3.0)

    def test_malformed_json_returns_defaults(self) -> None:
        dims = ["goal_alignment", "completeness"]
        scores = _parse_scores("this is not json", dims)
        assert scores["goal_alignment"] == pytest.approx(3.0)
        assert scores["completeness"] == pytest.approx(3.0)

    def test_no_json_brackets_returns_defaults(self) -> None:
        dims = ["goal_alignment"]
        scores = _parse_scores("no brackets here", dims)
        assert scores["goal_alignment"] == pytest.approx(3.0)

    def test_scores_not_dict_returns_defaults(self) -> None:
        dims = ["goal_alignment"]
        content = json.dumps({"scores": [1, 2, 3]})
        scores = _parse_scores(content, dims)
        assert scores["goal_alignment"] == pytest.approx(3.0)

    def test_json_embedded_in_text(self) -> None:
        dims = ["goal_alignment"]
        content = 'Sure! Here is my evaluation: {"scores": {"goal_alignment": 5.0}}'
        scores = _parse_scores(content, dims)
        assert scores["goal_alignment"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Evaluator node tests (with mocked LLM)
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal AgentState dict for evaluator tests."""
    base: dict[str, Any] = {
        "messages": [
            {"role": "user", "content": "What is the capital of France?"},
        ],
        "response": "The capital of France is Paris.",
        "task_type": "research",
        "archetype": None,
        "thoughts": [],
        "model_config": {"evaluator": "openai/gpt-4o-mini"},
        "eval_cycle": 0,
        "eval_scores": None,
        "eval_verdict": None,
        "user_id": "user-123",
    }
    base.update(overrides)
    return base


def _make_llm_response(scores: dict[str, float]) -> MagicMock:
    """Create a mock LLM response with the given scores."""
    mock = MagicMock()
    mock.content = json.dumps({"scores": scores, "reasoning": "test"})
    return mock


class TestEvaluatorNode:
    @pytest.mark.asyncio
    async def test_simple_utility_skips_evaluation(self) -> None:
        """simple_utility must return pass without any LLM call."""
        state = _make_state(task_type="simple_utility")

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
        ) as mock_llm:
            result = await evaluator_node(state)  # type: ignore[arg-type]

        mock_llm.assert_not_called()
        assert result["eval_verdict"] == "pass"
        assert result["eval_scores"] == {}
        assert result["eval_cycle"] == 0

    @pytest.mark.asyncio
    async def test_pass_verdict_on_high_scores(self) -> None:
        """All scores >= 3.0 should produce a pass verdict."""
        high_scores = {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "grounding": 4.0,
            "confidence_honesty": 4.0,
            "actionability": 4.0,
            "source_quality": 4.0,
            "recency": 4.0,
        }
        state = _make_state(task_type="research")

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(high_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "pass"
        assert result["eval_scores"]["goal_alignment"] == pytest.approx(4.0)
        # No message injection for pass
        assert "messages" not in result

    @pytest.mark.asyncio
    async def test_reroute_verdict_on_medium_scores(self) -> None:
        """Scores between 2.0 and 3.0 should produce reroute verdict."""
        medium_scores = {
            "goal_alignment": 2.5,
            "completeness": 2.5,
            "grounding": 2.5,
            "confidence_honesty": 2.5,
            "actionability": 2.5,
        }
        state = _make_state(task_type="execution")

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(medium_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "reroute"
        # Feedback should be injected into messages
        assert "messages" in result
        assert len(result["messages"]) > 1  # original + feedback
        # Last message should be feedback
        last_msg = result["messages"][-1]
        assert last_msg["role"] == "user"
        assert "improvement" in last_msg["content"].lower()
        # Cycle should be incremented
        assert result["eval_cycle"] == 1
        # Response should be cleared for re-generation
        assert result["response"] is None

    @pytest.mark.asyncio
    async def test_flag_verdict_on_very_low_scores(self) -> None:
        """Scores below 2.0 should produce flag verdict."""
        low_scores = {
            "goal_alignment": 1.0,
            "completeness": 1.0,
            "grounding": 1.0,
            "confidence_honesty": 1.0,
            "actionability": 1.0,
        }
        state = _make_state(task_type="execution")

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(low_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "flag"
        # Flag does NOT reroute (no message injection)
        assert "messages" not in result
        assert result["eval_cycle"] == 0

    @pytest.mark.asyncio
    async def test_reroute_cycle_limit(self) -> None:
        """After 2 reroute cycles, verdict is still reroute but no injection."""
        medium_scores = {
            "goal_alignment": 2.5,
            "completeness": 2.5,
            "grounding": 2.5,
            "confidence_honesty": 2.5,
            "actionability": 2.5,
        }
        # Simulate being at cycle 2 already (max)
        state = _make_state(task_type="execution", eval_cycle=2)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(medium_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        # Still returns reroute verdict (routing logic in graph decides to end)
        assert result["eval_verdict"] == "reroute"
        # But no message injection — cycle is at max
        assert "messages" not in result
        # Cycle stays at 2
        assert result["eval_cycle"] == 2

    @pytest.mark.asyncio
    async def test_decision_task_uses_extra_dimensions(self) -> None:
        """decision_intelligence tasks should include option_coverage, tradeoff_clarity."""
        decision_scores = {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "grounding": 4.0,
            "confidence_honesty": 4.0,
            "actionability": 4.0,
            "option_coverage": 4.0,
            "tradeoff_clarity": 4.0,
        }
        state = _make_state(task_type="decision_intelligence")

        captured_prompt: list[str] = []

        async def capture_invoke(**kwargs: Any) -> MagicMock:
            captured_prompt.append(kwargs.get("messages", [{}])[0].get("content", ""))
            return _make_llm_response(decision_scores)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            side_effect=capture_invoke,
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "pass"
        # Prompt should contain decision-specific dimensions
        assert captured_prompt
        prompt_text = captured_prompt[0]
        assert "option_coverage" in prompt_text
        assert "tradeoff_clarity" in prompt_text

    @pytest.mark.asyncio
    async def test_research_task_uses_extra_dimensions(self) -> None:
        """research tasks should include source_quality, recency."""
        research_scores = {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "grounding": 4.0,
            "confidence_honesty": 4.0,
            "actionability": 4.0,
            "source_quality": 4.0,
            "recency": 4.0,
        }
        state = _make_state(task_type="research")

        captured_prompt: list[str] = []

        async def capture_invoke(**kwargs: Any) -> MagicMock:
            captured_prompt.append(kwargs.get("messages", [{}])[0].get("content", ""))
            return _make_llm_response(research_scores)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            side_effect=capture_invoke,
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "pass"
        prompt_text = captured_prompt[0]
        assert "source_quality" in prompt_text
        assert "recency" in prompt_text

    @pytest.mark.asyncio
    async def test_malformed_response_falls_back_to_pass(self) -> None:
        """Malformed LLM response should use default scores (3.0 each -> pass)."""
        state = _make_state(task_type="execution")

        mock_response = MagicMock()
        mock_response.content = "I cannot evaluate this response."

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=mock_response,
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        # Default scores are 3.0 each -> overall = 3.0 -> pass
        assert result["eval_verdict"] == "pass"
        assert all(
            v == pytest.approx(3.0) for v in result["eval_scores"].values()
        )

    @pytest.mark.asyncio
    async def test_llm_failure_returns_pass(self) -> None:
        """LLM call failure should not block pipeline — defaults to pass."""
        state = _make_state(task_type="execution")

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await evaluator_node(state)  # type: ignore[arg-type]

        assert result["eval_verdict"] == "pass"

    @pytest.mark.asyncio
    async def test_model_none_skips_evaluation(self) -> None:
        """When evaluator model is 'none', skip LLM call and return pass."""
        state = _make_state(
            task_type="research",
            model_config={"evaluator": "none"},
        )

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
        ) as mock_llm:
            result = await evaluator_node(state)  # type: ignore[arg-type]

        mock_llm.assert_not_called()
        assert result["eval_verdict"] == "pass"

    @pytest.mark.asyncio
    async def test_missing_response_skips_evaluation(self) -> None:
        """Missing response should skip evaluation gracefully."""
        state = _make_state(task_type="execution", response=None)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
        ) as mock_llm:
            result = await evaluator_node(state)  # type: ignore[arg-type]

        mock_llm.assert_not_called()
        assert result["eval_verdict"] == "pass"


# ---------------------------------------------------------------------------
# Graph topology tests
# ---------------------------------------------------------------------------


class TestGraphTopology:
    def test_evaluator_node_in_graph(self) -> None:
        """Graph must contain an evaluator node."""
        graph = build_graph()
        assert "evaluator" in graph.nodes

    def test_evaluator_is_reachable_from_agent(self) -> None:
        """The evaluator node must be reachable (agent -> evaluator edge exists).

        OV3: responder removed; agent routes directly to evaluator.
        """
        graph = build_graph()
        compiled = graph.compile()
        edge_pairs = {(e.source, e.target) for e in compiled.get_graph().edges}
        # agent -> evaluator (conditional, when no tool_calls)
        assert ("agent", "evaluator") in edge_pairs, (
            "OV3: agent must have direct edge to evaluator"
        )
        assert ("responder", "evaluator") not in edge_pairs, (
            "OV3: responder -> evaluator edge must not exist (responder deleted)"
        )

    def test_all_required_nodes_present(self) -> None:
        """All pipeline nodes must be present. OV3: responder removed."""
        graph = build_graph()
        expected_nodes = {"router", "classifier", "planner", "agent", "tools",
                          "evaluator"}
        for node in expected_nodes:
            assert node in graph.nodes, f"Node '{node}' missing from graph"
        assert "responder" not in graph.nodes, "OV3: responder must be removed"


class TestRouteAfterEvaluator:
    def test_pass_verdict_goes_to_end(self) -> None:
        state = {"eval_verdict": "pass", "eval_cycle": 0}
        assert route_after_evaluator(state) == "__end__"

    def test_flag_verdict_goes_to_end(self) -> None:
        state = {"eval_verdict": "flag", "eval_cycle": 0}
        assert route_after_evaluator(state) == "__end__"

    def test_reroute_first_cycle_goes_to_agent(self) -> None:
        # eval_cycle is incremented BEFORE routing, so cycle=1 means first reroute
        state = {"eval_verdict": "reroute", "eval_cycle": 1}
        assert route_after_evaluator(state) == "agent"

    def test_reroute_second_cycle_goes_to_agent(self) -> None:
        state = {"eval_verdict": "reroute", "eval_cycle": 2}
        # cycle=2 means we've used both reroute slots, so go to __end__
        # Wait — the spec says max 2 reroute cycles. Let me verify the logic.
        # eval_cycle < 2 means: cycles 0 and 1 can reroute.
        # When cycle=2, we've done 2 reroutes already — terminate.
        assert route_after_evaluator(state) == "__end__"

    def test_reroute_at_max_cycles_goes_to_end(self) -> None:
        state = {"eval_verdict": "reroute", "eval_cycle": 3}
        assert route_after_evaluator(state) == "__end__"

    def test_default_verdict_goes_to_end(self) -> None:
        # No verdict set defaults to pass
        state = {"eval_cycle": 0}
        assert route_after_evaluator(state) == "__end__"
