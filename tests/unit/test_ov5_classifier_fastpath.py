"""Unit tests for OV5: Classifier Fast-Path & Planner-as-Tool.

Tests:
1. _is_obvious_simple returns True for greetings (hi, hey, hello)
2. _is_obvious_simple returns True for single emojis
3. _is_obvious_simple returns True for ack phrases (thanks, ok, yes, no, bye)
4. _is_obvious_simple returns True for very short messages with greeting words
5. _is_obvious_simple returns False for real queries
6. classifier_node returns simple_utility without LLM call for obvious messages
7. classifier_node still calls LLM for non-obvious messages
8. route_after_classifier routes simple_utility -> agent, others -> planner
9. planner_node skips LLM for execution tasks (returns archetype only)
10. planner_node calls LLM for research tasks
11. planner_node calls LLM for decision_intelligence tasks
12. planner_node guard: simple_utility still returns None archetype
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.graph import route_after_classifier
from noa.orchestrator.nodes.classifier import _is_obvious_simple, classifier_node
from noa.orchestrator.nodes.planner import planner_node

# ---------------------------------------------------------------------------
# 1-5: _is_obvious_simple heuristic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "hi",
        "Hi",
        "HI",
        "hey",
        "Hey!",
        "hello",
        "Hello.",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "no",
        "bye",
        "goodbye",
        "thanks a lot",
        "thank you so much",
        # Greeting within short message
        "hi there",
        "hey!",
        # Emoji
        "😊",
        "👍",
        "\U0001F600",
    ],
)
def test_is_obvious_simple_true(message: str) -> None:
    """Obvious greetings, acks, and emojis must return True (PERF-CL1)."""
    assert _is_obvious_simple(message) is True, (
        f"Expected _is_obvious_simple({message!r}) to be True"
    )


@pytest.mark.parametrize(
    "message",
    [
        "What is the weather in Berlin today?",
        "Send an email to Alice about the meeting",
        "Compare Python and Go for backend development",
        "Create a calendar event for Monday at 9am",
        "What are the pros and cons of solar panels?",
        "Hello, can you help me write a resignation letter?",  # greeting + real task
        "Please remind me to call mom at 5pm",
        "Translate this paragraph into French",
    ],
)
def test_is_obvious_simple_false(message: str) -> None:
    """Real queries must not be flagged as obvious simple (PERF-CL1)."""
    assert _is_obvious_simple(message) is False, (
        f"Expected _is_obvious_simple({message!r}) to be False"
    )


def test_is_obvious_simple_empty() -> None:
    """Empty / whitespace-only messages return False (no false positives)."""
    assert _is_obvious_simple("") is False
    assert _is_obvious_simple("   ") is False


# ---------------------------------------------------------------------------
# 6-7: classifier_node fast-path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_skips_llm_for_obvious_simple() -> None:
    """classifier_node must return simple_utility without an LLM call for obvious messages."""
    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "hi"}],
    }

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm", new_callable=AsyncMock
    ) as mock_llm:
        result = await classifier_node(state)

    assert result["task_type"] == "simple_utility"
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_classifier_calls_llm_for_real_query() -> None:
    """classifier_node must call the LLM for non-trivial messages."""
    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
    }

    mock_response = MagicMock()
    mock_response.content = '{"task_type": "simple_utility", "confidence": 0.9}'

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_llm:
        result = await classifier_node(state)

    mock_llm.assert_called_once()
    assert result["task_type"] == "simple_utility"


# ---------------------------------------------------------------------------
# 8: route_after_classifier
# ---------------------------------------------------------------------------


def test_route_after_classifier_simple_utility_goes_to_agent() -> None:
    """simple_utility must route directly to agent, skipping planner (PERF-CL1)."""
    state: dict[str, Any] = {"task_type": "simple_utility"}
    assert route_after_classifier(state) == "agent"


@pytest.mark.parametrize("task_type", ["execution", "research", "decision_intelligence"])
def test_route_after_classifier_non_simple_goes_to_planner(task_type: str) -> None:
    """Non-simple task types must route to planner."""
    state: dict[str, Any] = {"task_type": task_type}
    assert route_after_classifier(state) == "planner"


def test_route_after_classifier_missing_task_type_goes_to_planner() -> None:
    """Missing task_type must default to planner (safe fallback)."""
    assert route_after_classifier({}) == "planner"


# ---------------------------------------------------------------------------
# 9-12: planner_node LLM skip for execution tasks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_skips_llm_for_execution_task() -> None:
    """planner_node must NOT call LLM for execution tasks (PERF-PL1)."""
    state: dict[str, Any] = {
        "task_type": "execution",
        "messages": [{"role": "user", "content": "Create a calendar event for Monday"}],
    }

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm", new_callable=AsyncMock
    ) as mock_llm:
        result = await planner_node(state)

    mock_llm.assert_not_called()
    assert result["archetype"] == "execution"
    assert result["plan"] is None
    assert result["use_react"] is False


@pytest.mark.asyncio
async def test_planner_calls_llm_for_research_task() -> None:
    """planner_node must call LLM for research tasks (PERF-PL1)."""
    state: dict[str, Any] = {
        "task_type": "research",
        "messages": [{"role": "user", "content": "Compare Python and Go for web APIs"}],
        "model_config": {"planner": "openai/gpt-4o-mini"},
    }

    mock_response = MagicMock()
    mock_response.content = "1. Gather sources\n2. Synthesise\n3. Present"

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_llm:
        result = await planner_node(state)

    mock_llm.assert_called_once()
    assert result["archetype"] == "research"
    assert result["use_react"] is True
    assert result["plan"] is not None


@pytest.mark.asyncio
async def test_planner_calls_llm_for_decision_intelligence_task() -> None:
    """planner_node must call LLM for decision_intelligence tasks (PERF-PL1)."""
    state: dict[str, Any] = {
        "task_type": "decision_intelligence",
        "messages": [{"role": "user", "content": "Should I switch to a standing desk?"}],
        "model_config": {"planner": "openai/gpt-4o-mini"},
    }

    mock_response = MagicMock()
    mock_response.content = "1. Identify options\n2. Tradeoffs\n3. Recommend"

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_llm:
        result = await planner_node(state)

    mock_llm.assert_called_once()
    assert result["archetype"] == "comparative_selection"
    assert result["use_react"] is True


@pytest.mark.asyncio
async def test_planner_guard_simple_utility_returns_none_archetype() -> None:
    """planner_node guard for simple_utility must return no archetype and no LLM call."""
    state: dict[str, Any] = {
        "task_type": "simple_utility",
        "messages": [{"role": "user", "content": "hi"}],
    }

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm", new_callable=AsyncMock
    ) as mock_llm:
        result = await planner_node(state)

    mock_llm.assert_not_called()
    assert result["archetype"] is None
    assert result["plan"] is None
    assert result["use_react"] is False
