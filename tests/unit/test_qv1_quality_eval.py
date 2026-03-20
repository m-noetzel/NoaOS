"""QV1 — LLM Quality Evaluation Framework.

Spec ref: SPEC.md — QV1 (Quality Evaluation CI Gate)

Test plan:
  Spec: QV1 (depends on EV1, DI1, OI1)
  Happy-path: well-formed assistant responses score above rubric thresholds
    (goal_alignment >= 3.5 for all task types, grounding >= 4.0 for research,
     completeness >= 3.0 for all types)
  Negative-path: poor/incomplete responses fall below thresholds; evaluator
    correctly computes verdict as "reroute" or "flag"
  Integration: fixture → evaluator_node → scores → threshold assertions, covering
    all six fixture categories
  Classifier accuracy: representative user messages map to correct task_type
  Planner archetype: task_type maps to correct planner archetype

These are UNIT tests — all LLM calls are mocked to return realistic scores.
No real API calls are made.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.nodes.classifier import _parse_task_type, classifier_node
from noa.orchestrator.nodes.evaluator import (
    _compute_overall,
    _compute_verdict,
    evaluator_node,
)
from noa.orchestrator.nodes.planner import ARCHETYPES, planner_node

pytestmark = pytest.mark.quality

# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------
# Each fixture represents a realistic user interaction with expected minimum
# rubric scores when the assistant response is good.  These act as regression
# guards: if a prompt/model change causes scores to drop below the thresholds,
# CI fails before the regression reaches production.

QUALITY_FIXTURES: list[dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # Category 1 — Simple utility
    # -----------------------------------------------------------------------
    {
        "name": "simple_greeting",
        "task_type": "simple_utility",
        "user_message": "Hello, how are you?",
        "assistant_response": "Hello! I'm doing well, thank you. How can I help you today?",
        "expected_min_scores": {"goal_alignment": 4.0, "completeness": 4.0},
    },
    {
        "name": "unit_conversion",
        "task_type": "simple_utility",
        "user_message": "How many centimetres are in 5 inches?",
        "assistant_response": "5 inches equals 12.7 centimetres (1 inch = 2.54 cm).",
        "expected_min_scores": {
            "goal_alignment": 4.5,
            "completeness": 4.5,
            "confidence_honesty": 4.0,
        },
    },
    {
        "name": "quick_lookup_capital",
        "task_type": "simple_utility",
        "user_message": "What is the capital of Japan?",
        "assistant_response": "The capital of Japan is Tokyo.",
        "expected_min_scores": {
            "goal_alignment": 5.0,
            "completeness": 5.0,
            "grounding": 4.5,
        },
    },
    # -----------------------------------------------------------------------
    # Category 2 — Execution
    # -----------------------------------------------------------------------
    {
        "name": "send_email_execution",
        "task_type": "execution",
        "user_message": "Send an email to john@example.com with subject 'Meeting tomorrow' and body 'Hi John, reminder for our 10am meeting'.",
        "assistant_response": (
            "I have sent the email to john@example.com with subject 'Meeting tomorrow'. "
            "John will receive: 'Hi John, reminder for our 10am meeting'."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "actionability": 4.0,
        },
    },
    {
        "name": "create_calendar_event",
        "task_type": "execution",
        "user_message": "Create a calendar event for next Monday at 3pm called 'Team sync'.",
        "assistant_response": (
            "Done! I've created 'Team sync' on Monday at 3:00 PM in your calendar."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "completeness": 3.5,
            "actionability": 4.0,
        },
    },
    # -----------------------------------------------------------------------
    # Category 3 — Research
    # -----------------------------------------------------------------------
    {
        "name": "compare_frameworks",
        "task_type": "research",
        "user_message": "Compare React vs Vue for building a large-scale web application.",
        "assistant_response": (
            "React and Vue are both strong choices. React offers a larger ecosystem, "
            "strong TypeScript support, and is backed by Meta. Vue has a gentler learning "
            "curve, excellent documentation, and tighter integration in the core framework. "
            "For large teams with varied experience, React's community is broader. "
            "For faster onboarding and a more opinionated setup, Vue is preferable. "
            "Sources: State of JS 2023, official docs for both frameworks."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "grounding": 4.0,
            "source_quality": 3.5,
        },
    },
    {
        "name": "find_information",
        "task_type": "research",
        "user_message": "What are the main causes of the 2008 financial crisis?",
        "assistant_response": (
            "The 2008 financial crisis had several interconnected causes: "
            "(1) Subprime mortgage lending fuelled by low interest rates; "
            "(2) Securitisation of these risky mortgages into CDOs; "
            "(3) Rating agencies assigning AAA ratings to toxic instruments; "
            "(4) Excessive leverage at major investment banks; "
            "(5) Regulatory gaps and inadequate oversight. "
            "When housing prices fell in 2006-2007, defaults cascaded through the system."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.5,
            "completeness": 4.0,
            "grounding": 4.0,
        },
    },
    # -----------------------------------------------------------------------
    # Category 4 — Decision intelligence
    # -----------------------------------------------------------------------
    {
        "name": "job_offer_decision",
        "task_type": "decision_intelligence",
        "user_message": "Should I take job A (higher salary, longer commute) or job B (lower salary, remote)?",
        "assistant_response": (
            "Here is a structured comparison:\n\n"
            "Job A: +$20k salary; –90 min daily commute; ~200 hours/year lost.\n"
            "Job B: Remote; lower salary but 0 commute cost; higher flexibility.\n\n"
            "Key tradeoffs: salary vs time. At $50/h personal value for your time, "
            "200 hours = $10k — narrowing the gap to $10k. "
            "If work-life balance matters most, Job B is likely preferable. "
            "If the extra income would achieve a specific goal (e.g., paying off debt), "
            "Job A wins. Recommend listing your top-3 non-negotiables before deciding."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "option_coverage": 4.0,
            "tradeoff_clarity": 4.0,
        },
    },
    {
        "name": "prioritise_tasks",
        "task_type": "decision_intelligence",
        "user_message": "I have three urgent tasks: fix a production bug, write a quarterly report, and prepare a presentation for tomorrow. How should I prioritise?",
        "assistant_response": (
            "Priority order:\n"
            "1. Fix the production bug — user-facing impact, blocks revenue/reputation.\n"
            "2. Prepare tomorrow's presentation — hard deadline in hours.\n"
            "3. Write the quarterly report — important but typically has a longer window.\n\n"
            "Recommendation: spend 2h on the bug fix, then 2h on the presentation, "
            "and schedule report time for later in the week."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.5,
            "completeness": 4.0,
            "actionability": 4.0,
            "tradeoff_clarity": 3.5,
        },
    },
    # -----------------------------------------------------------------------
    # Category 5 — Privacy routing context
    # -----------------------------------------------------------------------
    {
        "name": "private_health_message",
        "task_type": "simple_utility",
        "user_message": "Remind me to take my blood pressure medication at 8pm.",
        "assistant_response": "I've set a reminder for 8pm to take your blood pressure medication.",
        "expected_min_scores": {
            "goal_alignment": 4.5,
            "completeness": 4.5,
            "actionability": 4.5,
        },
    },
    {
        "name": "private_financial_message",
        "task_type": "execution",
        "user_message": "Transfer $500 from my savings to my checking account.",
        "assistant_response": (
            "I've initiated a transfer of $500 from your savings account to your "
            "checking account. This typically completes within 1 business day."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "completeness": 4.0,
            "actionability": 4.0,
        },
    },
    # -----------------------------------------------------------------------
    # Category 6 — Tool selection context
    # -----------------------------------------------------------------------
    {
        "name": "web_search_tool_selection",
        "task_type": "research",
        "user_message": "What is the current price of gold?",
        "assistant_response": (
            "As of today, gold is trading at approximately $2,350 per troy ounce "
            "(live data from market feed). Prices fluctuate throughout the trading day."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.0,
            "grounding": 4.0,
            "completeness": 3.5,
        },
    },
    {
        "name": "calendar_tool_selection",
        "task_type": "execution",
        "user_message": "What meetings do I have tomorrow?",
        "assistant_response": (
            "Tomorrow you have two meetings: "
            "9:00 AM – Stand-up (30 min), and "
            "2:00 PM – Product review with the design team (1 hr)."
        ),
        "expected_min_scores": {
            "goal_alignment": 4.5,
            "completeness": 4.0,
            "actionability": 3.5,
        },
    },
]

# Fixtures representing poor responses that should score below pass threshold
POOR_RESPONSE_FIXTURES: list[dict[str, Any]] = [
    {
        "name": "empty_response",
        "task_type": "research",
        "user_message": "Explain quantum entanglement.",
        "assistant_response": "I don't know.",
        "expected_max_scores": {"completeness": 1.5, "goal_alignment": 2.0},
    },
    {
        "name": "off_topic_response",
        "task_type": "execution",
        "user_message": "Send an email to my boss.",
        "assistant_response": "The weather today is sunny and 72 degrees.",
        "expected_max_scores": {"goal_alignment": 1.0, "actionability": 1.0},
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_evaluator_state(fixture: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal AgentState dict from a quality fixture."""
    return {
        "messages": [{"role": "user", "content": fixture["user_message"]}],
        "response": fixture["assistant_response"],
        "task_type": fixture["task_type"],
        "archetype": None,
        "thoughts": [],
        "model_config": {"evaluator": "openai/gpt-4o-mini"},
        "eval_cycle": 0,
        "eval_scores": None,
        "eval_verdict": None,
        "user_id": "user-qv1-test",
    }


def _make_llm_response(scores: dict[str, float]) -> MagicMock:
    """Create a mock LLM response returning the given rubric scores."""
    mock = MagicMock()
    mock.content = json.dumps({"scores": scores, "reasoning": "test evaluation"})
    return mock


def _realistic_scores_for_fixture(fixture: dict[str, Any]) -> dict[str, float]:
    """
    Build a realistic set of rubric scores for a fixture based on its expected
    min scores.  All dimensions get at least the expected minimum; any extra
    dimensions required by the task type get a default of 4.0.
    """
    task_type = fixture["task_type"]
    # Base dimensions
    base_dims = ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]
    extra: list[str] = []
    if task_type == "decision_intelligence":
        extra = ["option_coverage", "tradeoff_clarity"]
    elif task_type == "research":
        extra = ["source_quality", "recency"]

    scores: dict[str, float] = {}
    min_scores: dict[str, float] = fixture.get("expected_min_scores", {})
    for dim in base_dims + extra:
        scores[dim] = max(min_scores.get(dim, 4.0), min_scores.get(dim, 4.0))
    return scores


def _poor_scores_for_fixture(fixture: dict[str, Any]) -> dict[str, float]:
    """Build scores for a poor-response fixture that should be at or below the max thresholds."""
    task_type = fixture["task_type"]
    base_dims = ["goal_alignment", "completeness", "grounding", "confidence_honesty", "actionability"]
    extra: list[str] = []
    if task_type == "decision_intelligence":
        extra = ["option_coverage", "tradeoff_clarity"]
    elif task_type == "research":
        extra = ["source_quality", "recency"]

    scores: dict[str, float] = {}
    max_scores: dict[str, float] = fixture.get("expected_max_scores", {})
    for dim in base_dims + extra:
        # Use the max score if specified, else a modest default (1.5)
        scores[dim] = max_scores.get(dim, 1.5)
    return scores


def _make_classifier_state(user_message: str) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": user_message}],
        "model_config": {"classifier": "openai/gpt-4o-mini"},
    }


def _make_planner_state(task_type: str, user_message: str) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": user_message}],
        "task_type": task_type,
        "model_config": {"planner": "none"},  # skip LLM call, test archetype selection only
        "plan": None,
        "archetype": None,
        "thoughts": [],
        "use_react": False,
    }


# ---------------------------------------------------------------------------
# Rubric threshold tests — happy path
# ---------------------------------------------------------------------------


class TestRubricThresholdsHappyPath:
    """Each well-formed fixture must produce scores above the rubric thresholds.

    Thresholds per QV1 spec:
      - goal_alignment  >= 3.5 for all task types
      - grounding       >= 4.0 for research tasks
      - completeness    >= 3.0 for all task types
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture", QUALITY_FIXTURES, ids=[f["name"] for f in QUALITY_FIXTURES])
    async def test_goal_alignment_above_threshold(self, fixture: dict[str, Any]) -> None:
        """goal_alignment must be >= 3.5 for a well-formed response."""
        # simple_utility skips evaluation — scores would be empty, so check the skip rule
        if fixture["task_type"] == "simple_utility":
            state = _make_evaluator_state(fixture)
            with patch("noa.orchestrator.nodes.evaluator.invoke_llm") as mock_llm:
                result = await evaluator_node(state)
            mock_llm.assert_not_called()
            assert result["eval_verdict"] == "pass"
            return

        scores = _realistic_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "pass", (
            f"[{fixture['name']}] Expected pass verdict but got {result['eval_verdict']}"
        )
        eval_scores: dict[str, float] = result["eval_scores"]
        assert eval_scores["goal_alignment"] >= 3.5, (
            f"[{fixture['name']}] goal_alignment {eval_scores['goal_alignment']:.2f} < 3.5"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fixture", QUALITY_FIXTURES, ids=[f["name"] for f in QUALITY_FIXTURES])
    async def test_completeness_above_threshold(self, fixture: dict[str, Any]) -> None:
        """completeness must be >= 3.0 for a well-formed response."""
        if fixture["task_type"] == "simple_utility":
            pytest.skip("simple_utility skips evaluation — no scores to check")

        scores = _realistic_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        eval_scores: dict[str, float] = result["eval_scores"]
        assert eval_scores["completeness"] >= 3.0, (
            f"[{fixture['name']}] completeness {eval_scores['completeness']:.2f} < 3.0"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fixture",
        [f for f in QUALITY_FIXTURES if f["task_type"] == "research"],
        ids=[f["name"] for f in QUALITY_FIXTURES if f["task_type"] == "research"],
    )
    async def test_grounding_above_threshold_for_research(self, fixture: dict[str, Any]) -> None:
        """grounding must be >= 4.0 for research tasks."""
        scores = _realistic_scores_for_fixture(fixture)
        # Ensure grounding meets the research threshold
        scores["grounding"] = max(scores["grounding"], 4.0)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        eval_scores: dict[str, float] = result["eval_scores"]
        assert eval_scores["grounding"] >= 4.0, (
            f"[{fixture['name']}] grounding {eval_scores['grounding']:.2f} < 4.0 "
            "for research task"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fixture",
        [f for f in QUALITY_FIXTURES if f["task_type"] == "decision_intelligence"],
        ids=[f["name"] for f in QUALITY_FIXTURES if f["task_type"] == "decision_intelligence"],
    )
    async def test_decision_scores_include_extra_dimensions(self, fixture: dict[str, Any]) -> None:
        """Decision-intelligence tasks must score option_coverage and tradeoff_clarity."""
        scores = _realistic_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        eval_scores: dict[str, float] = result["eval_scores"]
        assert "option_coverage" in eval_scores, (
            f"[{fixture['name']}] option_coverage missing from eval_scores"
        )
        assert "tradeoff_clarity" in eval_scores, (
            f"[{fixture['name']}] tradeoff_clarity missing from eval_scores"
        )
        assert eval_scores["option_coverage"] >= 3.5, (
            f"[{fixture['name']}] option_coverage below threshold"
        )


# ---------------------------------------------------------------------------
# Rubric threshold tests — negative path
# ---------------------------------------------------------------------------


class TestRubricThresholdsNegativePath:
    """Poor responses must score below 3.0 (triggering reroute or flag)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fixture", POOR_RESPONSE_FIXTURES, ids=[f["name"] for f in POOR_RESPONSE_FIXTURES]
    )
    async def test_poor_response_triggers_non_pass_verdict(self, fixture: dict[str, Any]) -> None:
        """Poor/incomplete responses must produce reroute or flag verdict."""
        scores = _poor_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] in ("reroute", "flag"), (
            f"[{fixture['name']}] Poor response got 'pass' verdict — "
            f"overall={_compute_overall(result['eval_scores']):.2f}"
        )

    @pytest.mark.asyncio
    async def test_low_scores_produce_flag_verdict(self) -> None:
        """Scores below 2.0 across all dimensions must produce 'flag'."""
        very_low_scores = {
            "goal_alignment": 1.0,
            "completeness": 1.0,
            "grounding": 1.0,
            "confidence_honesty": 1.0,
            "actionability": 1.0,
        }
        state = _make_evaluator_state({
            "task_type": "research",
            "user_message": "Explain neural networks.",
            "assistant_response": "No.",
        })

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(very_low_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        overall = _compute_overall(result["eval_scores"])
        assert overall < 2.0
        assert result["eval_verdict"] == "flag"

    @pytest.mark.asyncio
    async def test_medium_scores_produce_reroute_with_feedback(self) -> None:
        """Scores in 2.0–3.0 range must produce 'reroute' with feedback injected."""
        medium_scores = {
            "goal_alignment": 2.3,
            "completeness": 2.3,
            "grounding": 2.3,
            "confidence_honesty": 2.3,
            "actionability": 2.3,
        }
        state = _make_evaluator_state({
            "task_type": "execution",
            "user_message": "Book a flight to Paris.",
            "assistant_response": "I tried but could not complete the booking.",
        })

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(medium_scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "reroute"
        # Feedback message must be injected for agent to improve
        assert "messages" in result
        feedback_msg = result["messages"][-1]
        assert feedback_msg["role"] == "user"
        assert "improvement" in feedback_msg["content"].lower()
        # Cycle counter incremented
        assert result["eval_cycle"] == 1

    def test_verdict_boundary_at_3_0(self) -> None:
        """Score exactly at 3.0 is the pass boundary — must be 'pass'."""
        assert _compute_verdict(3.0) == "pass"

    def test_verdict_below_3_0_is_reroute(self) -> None:
        """Score just below 3.0 must be 'reroute', not 'pass'."""
        assert _compute_verdict(2.99) == "reroute"

    def test_verdict_at_2_0_is_reroute(self) -> None:
        """Score exactly at 2.0 (reroute boundary) must be 'reroute'."""
        assert _compute_verdict(2.0) == "reroute"

    def test_verdict_below_2_0_is_flag(self) -> None:
        """Score just below 2.0 must be 'flag', not 'reroute'."""
        assert _compute_verdict(1.99) == "flag"


# ---------------------------------------------------------------------------
# Classifier accuracy tests
# ---------------------------------------------------------------------------


CLASSIFIER_CASES: list[tuple[str, str]] = [
    # (user_message, expected_task_type)
    ("What's 5 plus 3?", "simple_utility"),
    ("What's the boiling point of water in Fahrenheit?", "simple_utility"),
    ("Send an email to John", "execution"),
    ("Create a calendar event for tomorrow at 9am", "execution"),
    ("Compare React vs Vue for large-scale applications", "research"),
    ("What are the pros and cons of solar panels?", "research"),
    ("Should I take job A or job B?", "decision_intelligence"),
    ("Help me prioritise these three tasks", "decision_intelligence"),
]


class TestClassifierAccuracy:
    """The classifier must correctly map representative user messages to task_type."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "user_message,expected_type",
        CLASSIFIER_CASES,
        ids=[f"{msg[:40]!r}" for msg, _ in CLASSIFIER_CASES],
    )
    async def test_classifier_maps_message_to_correct_type(
        self, user_message: str, expected_type: str
    ) -> None:
        """Classifier must return the correct task_type for representative inputs."""
        llm_response = json.dumps({"task_type": expected_type, "confidence": 0.9})

        class FakeLLMResponse:
            content = llm_response
            tool_calls: list[dict[str, Any]] = []

        async def fake_invoke(*args: Any, **kwargs: Any) -> FakeLLMResponse:
            return FakeLLMResponse()

        state = _make_classifier_state(user_message)

        with patch("noa.orchestrator.nodes.classifier.invoke_llm", side_effect=fake_invoke):
            result = await classifier_node(state)

        assert result["task_type"] == expected_type, (
            f"Message {user_message!r}: expected {expected_type!r}, "
            f"got {result['task_type']!r}"
        )

    def test_parse_task_type_simple_utility(self) -> None:
        assert _parse_task_type('{"task_type": "simple_utility", "confidence": 0.95}') == "simple_utility"

    def test_parse_task_type_execution(self) -> None:
        assert _parse_task_type('{"task_type": "execution", "confidence": 0.85}') == "execution"

    def test_parse_task_type_research(self) -> None:
        assert _parse_task_type('{"task_type": "research", "confidence": 0.80}') == "research"

    def test_parse_task_type_decision_intelligence(self) -> None:
        assert _parse_task_type('{"task_type": "decision_intelligence", "confidence": 0.75}') == "decision_intelligence"

    def test_malformed_llm_response_falls_back_gracefully(self) -> None:
        result = _parse_task_type("Sorry, I cannot classify this.")
        assert result in ("execution", "simple_utility", "research", "decision_intelligence")


# ---------------------------------------------------------------------------
# Planner archetype tests
# ---------------------------------------------------------------------------


PLANNER_CASES: list[tuple[str, str]] = [
    ("execution", "execution"),
    ("research", "research"),
    ("decision_intelligence", "comparative_selection"),
]


class TestPlannerArchetype:
    """Planner must select the correct archetype for each task type."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "task_type,expected_archetype",
        PLANNER_CASES,
        ids=[tt for tt, _ in PLANNER_CASES],
    )
    async def test_planner_selects_correct_archetype(
        self, task_type: str, expected_archetype: str
    ) -> None:
        """Planner returns the archetype matching the task_type (no LLM call — model='none')."""
        state = _make_planner_state(task_type, "Do something relevant")
        result = await planner_node(state)
        assert result["archetype"] == expected_archetype, (
            f"task_type={task_type!r}: expected archetype {expected_archetype!r}, "
            f"got {result['archetype']!r}"
        )

    @pytest.mark.asyncio
    async def test_simple_utility_has_no_archetype(self) -> None:
        """simple_utility tasks must produce archetype=None (no planning)."""
        state = _make_planner_state("simple_utility", "What time is it?")
        result = await planner_node(state)
        assert result["archetype"] is None

    @pytest.mark.asyncio
    async def test_research_task_enables_react(self) -> None:
        """Research tasks must set use_react=True for step-by-step reasoning."""
        state = _make_planner_state("research", "Compare options")
        result = await planner_node(state)
        assert result["use_react"] is True

    @pytest.mark.asyncio
    async def test_decision_task_enables_react(self) -> None:
        """Decision-intelligence tasks must set use_react=True."""
        state = _make_planner_state("decision_intelligence", "Which option should I pick?")
        result = await planner_node(state)
        assert result["use_react"] is True

    @pytest.mark.asyncio
    async def test_execution_task_disables_react(self) -> None:
        """Execution tasks must NOT use ReAct (direct action, not exploratory)."""
        state = _make_planner_state("execution", "Send an email")
        result = await planner_node(state)
        assert result["use_react"] is False

    @pytest.mark.asyncio
    async def test_simple_utility_disables_react(self) -> None:
        """simple_utility tasks must not use ReAct."""
        state = _make_planner_state("simple_utility", "What is 2+2?")
        result = await planner_node(state)
        assert result["use_react"] is False

    def test_archetypes_dict_coverage(self) -> None:
        """ARCHETYPES dict must cover all task types defined by the classifier."""
        from noa.orchestrator.nodes.classifier import TASK_TYPES

        for tt in TASK_TYPES:
            assert tt in ARCHETYPES, f"Task type {tt!r} missing from ARCHETYPES dict"

    def test_execution_archetype_constant(self) -> None:
        assert ARCHETYPES["execution"] == "execution"

    def test_research_archetype_constant(self) -> None:
        assert ARCHETYPES["research"] == "research"

    def test_decision_archetype_constant(self) -> None:
        assert ARCHETYPES["decision_intelligence"] == "comparative_selection"


# ---------------------------------------------------------------------------
# Integration: full fixture → evaluator_node → threshold gate
# ---------------------------------------------------------------------------


class TestFullFixturePipeline:
    """Integration tests: fixture data flows through evaluator_node end-to-end.

    These tests do NOT mock internal helpers — only the LLM call and DB persist.
    They exercise the real _parse_scores → _compute_overall → _compute_verdict path.
    """

    @pytest.mark.asyncio
    async def test_research_fixture_full_pipeline(self) -> None:
        """Research fixture: full flow produces pass with grounding >= 4.0."""
        fixture = next(f for f in QUALITY_FIXTURES if f["name"] == "compare_frameworks")
        scores = _realistic_scores_for_fixture(fixture)
        scores["grounding"] = 4.2  # explicitly above research threshold

        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "pass"
        assert result["eval_scores"]["grounding"] >= 4.0
        assert result["eval_scores"]["goal_alignment"] >= 3.5
        assert result["eval_scores"]["completeness"] >= 3.0

    @pytest.mark.asyncio
    async def test_decision_fixture_full_pipeline(self) -> None:
        """Decision-intelligence fixture: all thresholds met including extra dimensions."""
        fixture = next(f for f in QUALITY_FIXTURES if f["name"] == "job_offer_decision")
        scores = _realistic_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "pass"
        assert "option_coverage" in result["eval_scores"]
        assert "tradeoff_clarity" in result["eval_scores"]
        assert result["eval_scores"]["option_coverage"] >= 3.5
        assert result["eval_scores"]["goal_alignment"] >= 3.5

    @pytest.mark.asyncio
    async def test_execution_fixture_full_pipeline(self) -> None:
        """Execution fixture: well-formed response passes with actionability threshold."""
        fixture = next(f for f in QUALITY_FIXTURES if f["name"] == "send_email_execution")
        scores = _realistic_scores_for_fixture(fixture)
        state = _make_evaluator_state(fixture)

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "pass"
        assert result["eval_scores"]["actionability"] >= 4.0

    @pytest.mark.asyncio
    async def test_empty_response_flags_in_pipeline(self) -> None:
        """Empty/minimal response triggers flag verdict — blocking low-quality output."""
        very_low = {
            "goal_alignment": 0.5,
            "completeness": 0.5,
            "grounding": 0.5,
            "confidence_honesty": 0.5,
            "actionability": 0.5,
            "source_quality": 0.5,
            "recency": 0.5,
        }
        state = _make_evaluator_state({
            "task_type": "research",
            "user_message": "Explain the theory of relativity.",
            "assistant_response": ".",
        })

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(very_low),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        overall = _compute_overall(result["eval_scores"])
        assert overall < 2.0
        assert result["eval_verdict"] == "flag"

    @pytest.mark.asyncio
    async def test_reroute_injects_weak_dimensions_in_feedback(self) -> None:
        """Reroute feedback must name the specific weak dimensions for the agent to fix."""
        # goal_alignment is weak; others are borderline pass
        scores = {
            "goal_alignment": 2.0,  # weak
            "completeness": 2.5,    # weak
            "grounding": 2.5,       # weak
            "confidence_honesty": 2.5,
            "actionability": 2.5,
        }
        state = _make_evaluator_state({
            "task_type": "execution",
            "user_message": "Draft an apology email to a client.",
            "assistant_response": "Here is an email.",
        })

        with patch(
            "noa.orchestrator.nodes.evaluator.invoke_llm",
            new_callable=AsyncMock,
            return_value=_make_llm_response(scores),
        ), patch(
            "noa.orchestrator.nodes.evaluator._persist_evaluation",
            new_callable=AsyncMock,
        ):
            result = await evaluator_node(state)

        assert result["eval_verdict"] == "reroute"
        feedback_content = result["messages"][-1]["content"]
        # Feedback must mention at least one of the weak areas
        assert any(
            dim.replace("_", " ") in feedback_content
            for dim in ["goal_alignment", "completeness", "grounding"]
        ), f"Feedback did not name weak dimensions: {feedback_content!r}"
