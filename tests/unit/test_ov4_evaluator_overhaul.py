"""Unit tests for OV4 Evaluator Overhaul.

Tests:
1. Execution tasks use only goal_alignment + actionability (lightweight rubric)
2. Research tasks include source_quality + recency + reasoning_coherence
3. Decision_intelligence tasks include option_coverage + tradeoff_clarity + reasoning_coherence
4. Unknown/None task types use full 5-dimension base rubric
5. Anchor examples appear in evaluator prompt (dimension rubric text)
6. Reroute feedback uses role "developer" (not "user")
7. Reasoning field is returned by evaluator in state update
8. Custom thresholds from eval_config are used (pass/reroute/max_cycles)
9. Default thresholds work when eval_config is missing or empty
10. EvalConfig Pydantic model validates correctly
11. Settings service round-trips eval_config through JSON serialization
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.nodes.evaluator import (
    _DEFAULT_MAX_REROUTE_CYCLES,
    _DEFAULT_PASS_THRESHOLD,
    _DEFAULT_REROUTE_THRESHOLD,
    _build_dimensions_list,
    _compute_verdict,
    _get_dimensions,
    _parse_scores,
    evaluator_node,
)

# ---------------------------------------------------------------------------
# 1-4: Dimension sets per task type
# ---------------------------------------------------------------------------


def test_execution_task_uses_lightweight_dimensions() -> None:
    """Execution tasks must use only goal_alignment + actionability (OV4 / ARCH-EV2)."""
    dims = _get_dimensions("execution")
    assert dims == ["goal_alignment", "actionability"], (
        f"execution task got unexpected dimensions: {dims}"
    )
    # Must NOT include base rubric dimensions like completeness
    assert "completeness" not in dims
    assert "grounding" not in dims
    assert "confidence_honesty" not in dims


def test_research_task_includes_extra_dimensions() -> None:
    """Research tasks include base rubric + source_quality + recency + reasoning_coherence."""
    dims = _get_dimensions("research")
    # All base dimensions present
    for base in ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]:
        assert base in dims, f"research task missing base dimension: {base}"
    # Research extras
    assert "source_quality" in dims
    assert "recency" in dims
    assert "reasoning_coherence" in dims
    # Decision-specific extras NOT present
    assert "option_coverage" not in dims
    assert "tradeoff_clarity" not in dims


def test_decision_intelligence_task_includes_extra_dimensions() -> None:
    """Decision tasks include base rubric + option_coverage + tradeoff_clarity + reasoning_coherence."""
    dims = _get_dimensions("decision_intelligence")
    # All base dimensions present
    for base in ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]:
        assert base in dims, f"decision task missing base dimension: {base}"
    # Decision extras
    assert "option_coverage" in dims
    assert "tradeoff_clarity" in dims
    assert "reasoning_coherence" in dims
    # Research-specific extras NOT present
    assert "source_quality" not in dims
    assert "recency" not in dims


def test_unknown_task_type_uses_full_base_rubric() -> None:
    """None/unknown task type uses full 5-dimension base rubric."""
    for task_type in [None, "unknown_type", ""]:
        dims = _get_dimensions(task_type)
        expected = ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]
        assert dims == expected, f"task_type={task_type!r} got unexpected dimensions: {dims}"


# ---------------------------------------------------------------------------
# 5: Anchor examples in rubric
# ---------------------------------------------------------------------------


def test_anchor_examples_appear_in_dimensions_list() -> None:
    """_build_dimensions_list must include anchor examples for each dimension (ARCH-EV2)."""
    dims = ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]
    text = _build_dimensions_list(dims)

    # Each dimension should have its anchor examples present
    assert "Response ignores user's request entirely" in text  # goal_alignment 1
    assert "Fully addresses every aspect" in text  # goal_alignment 5
    assert "Response is a single sentence with no detail" in text  # completeness 1
    assert "Comprehensive coverage" in text  # completeness 5
    assert "Contains fabricated facts or hallucinations" in text  # grounding 1
    assert "All claims supported by evidence" in text  # grounding 5
    assert "Presents uncertain info as absolute fact" in text  # confidence_honesty 1
    assert "User cannot act on this response" in text  # actionability 1
    assert "Clear, specific next steps" in text  # actionability 5


def test_research_dimensions_have_anchor_examples() -> None:
    """Research-specific dimensions must have anchor examples."""
    dims = _get_dimensions("research")
    text = _build_dimensions_list(dims)
    assert "No sources cited or all sources are unreliable" in text  # source_quality 1
    assert "All information is current" in text  # recency 5
    assert "Reasoning is contradictory or internally inconsistent" in text  # reasoning_coherence 1


def test_decision_dimensions_have_anchor_examples() -> None:
    """Decision-specific dimensions must have anchor examples."""
    dims = _get_dimensions("decision_intelligence")
    text = _build_dimensions_list(dims)
    assert "Only one option presented when multiple clearly exist" in text  # option_coverage 1
    assert "No tradeoffs mentioned" in text  # tradeoff_clarity 1


# ---------------------------------------------------------------------------
# 6: Reroute feedback uses role "developer"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reroute_feedback_uses_developer_role() -> None:
    """On reroute, feedback message must use role 'developer' (ARCH-EV1)."""
    # LLM returns a score that triggers reroute (all dimensions = 2.5)
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 2.5, "actionability": 2.5},
        "reasoning": "response was incomplete",
    })

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        "eval_config": {},
        "response": "I'll do that for you.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Please schedule a meeting"}],
        "model_config": {},
        "run_id": "test-run-001",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    # Should reroute (mean 2.5 < pass threshold 3.0, >= reroute threshold 2.0)
    assert result["eval_verdict"] == "reroute"

    # The new feedback message must use role "developer"
    new_messages = result["messages"]
    feedback_message = new_messages[-1]
    assert feedback_message["role"] == "developer", (
        f"Expected role 'developer', got {feedback_message['role']!r} (ARCH-EV1)"
    )
    assert "needs improvement" in feedback_message["content"]


@pytest.mark.asyncio
async def test_reroute_feedback_not_role_user() -> None:
    """Reroute feedback must NOT use role 'user' (impersonation risk — ARCH-EV1)."""
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 2.0, "completeness": 2.0, "grounding": 2.0,
                   "confidence_honesty": 2.0, "actionability": 2.0},
        "reasoning": "poor response",
    })

    state: dict[str, Any] = {
        "task_type": None,
        "eval_cycle": 0,
        "eval_config": {},
        "response": "Not helpful at all.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Explain quantum computing"}],
        "model_config": {},
        "run_id": "test-run-002",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    assert result["eval_verdict"] == "reroute"
    new_messages = result["messages"]
    # Check no message with role "user" was injected (only original user message)
    injected = [m for m in new_messages[1:] if m.get("role") == "user"]
    assert len(injected) == 0, "Reroute feedback must not inject role='user' messages"


# ---------------------------------------------------------------------------
# 7: Reasoning field returned in state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reasoning_field_returned_in_state() -> None:
    """Evaluator must return 'eval_reasoning' in state update (ARCH-EV1)."""
    reasoning_text = "The response fully addressed the user's question."
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 4.0, "actionability": 4.0},
        "reasoning": reasoning_text,
    })

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        "eval_config": {},
        "response": "Meeting scheduled for 3pm tomorrow.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Schedule a meeting"}],
        "model_config": {},
        "run_id": "test-run-003",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    assert "eval_reasoning" in result, "eval_reasoning must be in state update"
    assert result["eval_reasoning"] == reasoning_text


@pytest.mark.asyncio
async def test_reasoning_empty_string_on_parse_failure() -> None:
    """When LLM returns no JSON, eval_reasoning must be empty string (not None/absent)."""
    mock_llm_result = MagicMock()
    mock_llm_result.content = "not valid json at all"

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        "eval_config": {},
        "response": "Done.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Do something"}],
        "model_config": {},
        "run_id": "test-run-004",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    assert "eval_reasoning" in result
    assert result["eval_reasoning"] == ""


# ---------------------------------------------------------------------------
# 8: Custom thresholds from eval_config
# ---------------------------------------------------------------------------


def test_compute_verdict_uses_custom_thresholds() -> None:
    """_compute_verdict must use supplied thresholds (UX-EV1)."""
    # With raised pass_threshold, a 3.0 score should reroute
    assert _compute_verdict(3.0, pass_threshold=4.0, reroute_threshold=2.0) == "reroute"
    # With lowered pass_threshold, a 2.5 score should pass
    assert _compute_verdict(2.5, pass_threshold=2.0, reroute_threshold=1.0) == "pass"
    # With raised reroute_threshold, a 2.0 score should flag
    assert _compute_verdict(2.0, pass_threshold=3.0, reroute_threshold=2.5) == "flag"


@pytest.mark.asyncio
async def test_custom_thresholds_applied_in_evaluator_node() -> None:
    """eval_config thresholds from state must be used in evaluator_node (UX-EV1)."""
    # With pass_threshold=4.5, a score of 4.0 should reroute
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 4.0, "actionability": 4.0},
        "reasoning": "good but not excellent",
    })

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        "eval_config": {"pass_threshold": 4.5, "reroute_threshold": 3.0, "max_cycles": 3},
        "response": "Meeting scheduled.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Schedule a meeting"}],
        "model_config": {},
        "run_id": "test-run-005",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    # 4.0 < 4.5 pass_threshold → reroute (not pass)
    assert result["eval_verdict"] == "reroute", (
        f"Expected 'reroute' with pass_threshold=4.5 and score=4.0, got {result['eval_verdict']!r}"
    )


@pytest.mark.asyncio
async def test_custom_max_cycles_respected() -> None:
    """eval_config max_cycles must limit rerouting (UX-EV1)."""
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 2.5, "actionability": 2.5},
        "reasoning": "incomplete",
    })

    # eval_cycle=1 with max_cycles=1 → should NOT reroute (cycle already reached limit)
    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 1,
        "eval_config": {"max_cycles": 1},
        "response": "Done.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Do the thing"}],
        "model_config": {},
        "run_id": "test-run-006",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    # Should still be reroute verdict, but no new messages injected (cycle limit)
    assert result["eval_verdict"] == "reroute"
    assert "messages" not in result, (
        "No messages should be injected when max_cycles is reached"
    )


# ---------------------------------------------------------------------------
# 9: Default thresholds when eval_config is missing
# ---------------------------------------------------------------------------


def test_default_threshold_constants() -> None:
    """Default threshold constants must have expected values."""
    assert _DEFAULT_PASS_THRESHOLD == 3.0
    assert _DEFAULT_REROUTE_THRESHOLD == 2.0
    assert _DEFAULT_MAX_REROUTE_CYCLES == 2


@pytest.mark.asyncio
async def test_default_thresholds_when_eval_config_absent() -> None:
    """evaluator_node works with default thresholds when eval_config is absent."""
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 3.5, "actionability": 3.5},
        "reasoning": "adequate response",
    })

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        # eval_config intentionally absent (simulates old state without the field)
        "response": "Meeting scheduled.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Schedule meeting"}],
        "model_config": {},
        "run_id": "test-run-007",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    # 3.5 >= 3.0 default pass_threshold → pass
    assert result["eval_verdict"] == "pass"


@pytest.mark.asyncio
async def test_default_thresholds_when_eval_config_empty_dict() -> None:
    """evaluator_node uses defaults when eval_config is an empty dict."""
    mock_llm_result = MagicMock()
    mock_llm_result.content = json.dumps({
        "scores": {"goal_alignment": 1.5, "actionability": 1.5},
        "reasoning": "very poor",
    })

    state: dict[str, Any] = {
        "task_type": "execution",
        "eval_cycle": 0,
        "eval_config": {},  # empty, not None
        "response": "I dunno.",
        "archetype": None,
        "messages": [{"role": "user", "content": "Help me"}],
        "model_config": {},
        "run_id": "test-run-008",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_llm_result,
    ), patch(
        "noa.orchestrator.nodes.evaluator._persist_evaluation",
        new_callable=AsyncMock,
    ):
        result = await evaluator_node(state)

    # 1.5 < 2.0 default reroute_threshold → flag
    assert result["eval_verdict"] == "flag"


# ---------------------------------------------------------------------------
# 10: EvalConfig Pydantic model
# ---------------------------------------------------------------------------


def test_eval_config_pydantic_defaults() -> None:
    """EvalConfig must have correct default values."""
    from noa.api.v1.settings import EvalConfig

    cfg = EvalConfig()
    assert cfg.pass_threshold == 3.0
    assert cfg.reroute_threshold == 2.0
    assert cfg.max_cycles == 2


def test_eval_config_pydantic_validation() -> None:
    """EvalConfig must enforce valid ranges."""
    from pydantic import ValidationError

    from noa.api.v1.settings import EvalConfig

    # Valid custom values
    cfg = EvalConfig(pass_threshold=4.0, reroute_threshold=2.5, max_cycles=5)
    assert cfg.pass_threshold == 4.0

    # Out-of-range pass_threshold (>5)
    with pytest.raises(ValidationError):
        EvalConfig(pass_threshold=6.0)

    # max_cycles=0 is invalid (ge=1)
    with pytest.raises(ValidationError):
        EvalConfig(max_cycles=0)


def test_eval_config_in_update_settings_request() -> None:
    """UpdateSettingsRequest must accept eval_config field."""
    from noa.api.v1.settings import EvalConfig, UpdateSettingsRequest

    req = UpdateSettingsRequest(
        eval_config=EvalConfig(pass_threshold=3.5, reroute_threshold=2.0, max_cycles=3)
    )
    dumped = req.model_dump(exclude_unset=True)
    assert "eval_config" in dumped
    assert dumped["eval_config"]["pass_threshold"] == 3.5


# ---------------------------------------------------------------------------
# 11: Settings service eval_config serialization
# ---------------------------------------------------------------------------


def test_parse_scores_returns_reasoning() -> None:
    """_parse_scores must return (scores, reasoning) tuple."""
    dims = ["goal_alignment", "completeness"]
    content = json.dumps({
        "scores": {"goal_alignment": 4.0, "completeness": 3.0},
        "reasoning": "solid response",
    })

    scores, reasoning = _parse_scores(content, dims)
    assert scores["goal_alignment"] == 4.0
    assert scores["completeness"] == 3.0
    assert reasoning == "solid response"


def test_parse_scores_empty_reasoning_on_missing() -> None:
    """_parse_scores returns empty string when reasoning field absent."""
    dims = ["goal_alignment"]
    content = json.dumps({"scores": {"goal_alignment": 3.0}})

    scores, reasoning = _parse_scores(content, dims)
    assert scores["goal_alignment"] == 3.0
    assert reasoning == ""


def test_parse_scores_fallback_on_bad_json() -> None:
    """_parse_scores returns default scores and empty reasoning on bad JSON."""
    dims = ["goal_alignment", "actionability"]
    scores, reasoning = _parse_scores("not json", dims)
    assert scores == {"goal_alignment": 3.0, "actionability": 3.0}
    assert reasoning == ""


# ---------------------------------------------------------------------------
# Integration: simple_utility still skips evaluation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simple_utility_skips_evaluation() -> None:
    """simple_utility tasks must skip evaluation (no LLM call)."""
    state: dict[str, Any] = {
        "task_type": "simple_utility",
        "eval_cycle": 0,
        "eval_config": {},
        "response": "Hello!",
        "archetype": None,
        "messages": [{"role": "user", "content": "Hi"}],
        "model_config": {},
        "run_id": "test-run-999",
    }

    with patch(
        "noa.orchestrator.nodes.evaluator.invoke_llm",
        new_callable=AsyncMock,
    ) as mock_llm:
        result = await evaluator_node(state)

    mock_llm.assert_not_called()
    assert result["eval_verdict"] == "pass"
    assert result["eval_scores"] == {}
    assert result["eval_reasoning"] == ""
