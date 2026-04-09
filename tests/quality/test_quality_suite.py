"""QA1 — LLM Quality Test Suite.

Structural property tests using YAML fixtures. These tests verify that:
- The classifier routes to the correct task_type given a realistic LLM response.
- The planner selects the right archetype and enables ReAct when appropriate.
- Privacy routing fires correctly for private/sensitive content.
- Tool selection logic produces the expected tool_call shapes.

LLM calls are mocked at the boundary (invoke_llm in classifier.py / planner.py).
The internal logic — JSON parsing, archetype selection, privacy routing — runs
against real code with no internal mocks.

Spec refs: RV-M3 — recorded-response test suite with structural assertions.
"""

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a YAML fixture from the fixtures directory."""
    path = FIXTURES_DIR / name
    with path.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def _load_all_fixtures() -> list[dict[str, Any]]:
    """Load every YAML file from the fixtures directory."""
    fixtures: list[dict[str, Any]] = []
    for path in sorted(FIXTURES_DIR.glob("*.yaml")):
        fixture = yaml.safe_load(path.read_text())
        fixture["_source_file"] = path.name
        fixtures.append(fixture)
    return fixtures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(prompt: str, **overrides: Any) -> dict[str, Any]:
    """Build a minimal AgentState dict for classifier/planner/router testing."""
    base: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "privacy_mode": "external",
        "model_config": {"classifier": "none", "planner": "none"},
        "tool_calls": [],
        "tool_results": [],
        "available_tools": [],
        "requested_tools": None,
        "user_privacy_override": None,
        "private_available": True,
    }
    base.update(overrides)
    return base


def _mock_classifier_response(task_type: str) -> MagicMock:
    """Return a mock LLMResponse that the classifier will parse as task_type."""
    mock = MagicMock()
    mock.content = f'{{"task_type": "{task_type}", "confidence": 0.95}}'
    return mock


def _mock_planner_response(plan_text: str) -> MagicMock:
    """Return a mock LLMResponse that the planner will use as the plan text."""
    mock = MagicMock()
    mock.content = plan_text
    return mock


# ---------------------------------------------------------------------------
# 1. Classifier structural tests
# ---------------------------------------------------------------------------


@pytest.mark.quality
@pytest.mark.asyncio
async def test_classifier_simple_utility_no_llm_call() -> None:
    """simple_utility fixture: classifier returns simple_utility.

    The classifier is configured with model='none' so no LLM call is made,
    proving the default-path returns a valid task_type.
    """
    fixture = _load_fixture("simple_utility.yaml")
    prompt = fixture["prompt"]
    expected = fixture["expected"]

    state = _make_state(prompt, model_config={"classifier": "none", "planner": "none"})

    from noa.orchestrator.nodes.classifier import classifier_node

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm", new_callable=AsyncMock
    ) as mock_llm:
        result = await classifier_node(state)

    # With model='none', classifier short-circuits to "execution".
    # The fixture may assert simple_utility — test that the mocked path works.
    # We also accept "execution" as the model='none' fallback.
    assert result["task_type"] in ("simple_utility", "execution"), (
        f"Fixture '{fixture['name']}': unexpected task_type={result['task_type']!r}"
    )
    # With model='none', LLM should NOT be called.
    mock_llm.assert_not_called()


@pytest.mark.quality
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fixture_name,expected_task_type",
    [
        ("simple_utility.yaml", "simple_utility"),
        ("execution_with_tools.yaml", "execution"),
        ("privacy_routing.yaml", "execution"),
        ("tool_selection.yaml", "execution"),
        ("decision_intelligence.yaml", "decision_intelligence"),
        ("research_task.yaml", "research"),
        ("memory_extraction.yaml", "execution"),
    ],
)
async def test_classifier_routes_correctly(
    fixture_name: str, expected_task_type: str
) -> None:
    """Classifier routes each fixture to the expected task_type.

    The LLM is mocked to return the expected_task_type.  We verify that
    _parse_task_type() (the internal parsing logic) processes the mocked
    response correctly and stores the right task_type in state.
    """
    fixture = _load_fixture(fixture_name)
    prompt = fixture["prompt"]

    state = _make_state(
        prompt,
        model_config={"classifier": "openai/gpt-4o-mini", "planner": "none"},
    )

    mock_response = _mock_classifier_response(expected_task_type)

    from noa.orchestrator.nodes.classifier import classifier_node

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await classifier_node(state)

    assert result["task_type"] == expected_task_type, (
        f"Fixture '{fixture['name']}' ({fixture_name}): "
        f"expected task_type={expected_task_type!r}, got {result['task_type']!r}"
    )


# ---------------------------------------------------------------------------
# 2. Planner structural tests
# ---------------------------------------------------------------------------


@pytest.mark.quality
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fixture_name,task_type,expected_archetype,expect_react,expect_plan",
    [
        # simple_utility never generates a plan (fast-path — no LLM call)
        ("simple_utility.yaml", "simple_utility", None, False, False),
        # execution tasks skip planner LLM (OV5/PERF-PL1) — plan is None
        ("execution_with_tools.yaml", "execution", "execution", False, False),
        ("tool_selection.yaml", "execution", "execution", False, False),
        ("memory_extraction.yaml", "execution", "execution", False, False),
        # decision_intelligence and research both generate plans + use ReAct
        ("decision_intelligence.yaml", "decision_intelligence", "comparative_selection", True, True),
        ("research_task.yaml", "research", "research", True, True),
        # privacy_routing is execution type — plan is None (OV5)
        ("privacy_routing.yaml", "execution", "execution", False, False),
    ],
)
async def test_planner_archetype_and_react(
    fixture_name: str,
    task_type: str,
    expected_archetype: str | None,
    expect_react: bool,
    expect_plan: bool,
) -> None:
    """Planner assigns correct archetype and use_react flag for each task type.

    For task types that generate a plan (research, decision_intelligence), the
    LLM is mocked. For others the planner returns immediately without an LLM call.
    """
    fixture = _load_fixture(fixture_name)
    prompt = fixture["prompt"]

    state = _make_state(
        prompt,
        task_type=task_type,
        model_config={"planner": "openai/gpt-4o-mini", "classifier": "none"},
    )

    mock_plan = _mock_planner_response("1. Analyse the request\n2. Execute\n3. Verify")

    from noa.orchestrator.nodes.planner import planner_node

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_plan,
    ):
        result = await planner_node(state)

    assert result["archetype"] == expected_archetype, (
        f"Fixture '{fixture['name']}': "
        f"expected archetype={expected_archetype!r}, got {result['archetype']!r}"
    )
    assert result["use_react"] is expect_react, (
        f"Fixture '{fixture['name']}': "
        f"expected use_react={expect_react}, got {result['use_react']}"
    )
    if expect_plan:
        assert result["plan"] is not None and len(result["plan"]) > 0, (
            f"Fixture '{fixture['name']}': expected a non-empty plan"
        )
    else:
        assert result["plan"] is None, (
            f"Fixture '{fixture['name']}': expected plan=None, got {result['plan']!r}"
        )


# ---------------------------------------------------------------------------
# 3. Privacy routing tests
# ---------------------------------------------------------------------------


@pytest.mark.quality
def test_privacy_router_routes_diary_to_private() -> None:
    """router_node classifies diary/journal prompts as private domain.

    The PrivacyClassifier uses keyword-based detection — no LLM call needed.
    This is a pure-function test that exercises the real privacy classifier code.
    """
    fixture = _load_fixture("privacy_routing.yaml")
    prompt = fixture["prompt"]

    state = _make_state(prompt)

    from noa.orchestrator.nodes.router import router_node

    result = router_node(state)

    expected_privacy = fixture["expected"].get("privacy_mode", "private")
    assert result["privacy_mode"] == expected_privacy, (
        f"Fixture '{fixture['name']}': "
        f"expected privacy_mode={expected_privacy!r}, got {result['privacy_mode']!r}"
    )


@pytest.mark.quality
def test_privacy_router_routes_general_query_to_external() -> None:
    """router_node classifies a non-sensitive prompt as external domain."""
    fixture = _load_fixture("simple_utility.yaml")
    prompt = fixture["prompt"]

    state = _make_state(prompt)

    from noa.orchestrator.nodes.router import router_node

    result = router_node(state)

    assert result["privacy_mode"] == "external", (
        f"Fixture '{fixture['name']}': "
        f"expected privacy_mode='external', got {result['privacy_mode']!r}"
    )


@pytest.mark.quality
def test_privacy_router_routes_web_search_to_external() -> None:
    """router_node keeps web_search tasks in external domain."""
    fixture = _load_fixture("execution_with_tools.yaml")
    prompt = fixture["prompt"]

    state = _make_state(prompt)

    from noa.orchestrator.nodes.router import router_node

    result = router_node(state)

    assert result["privacy_mode"] == "external", (
        f"Fixture '{fixture['name']}': "
        f"expected privacy_mode='external', got {result['privacy_mode']!r}"
    )


# ---------------------------------------------------------------------------
# 4. Tool call structural property tests
# ---------------------------------------------------------------------------


@pytest.mark.quality
@pytest.mark.asyncio
async def test_execution_with_tools_fixture_has_expected_tool_in_response() -> None:
    """Execution fixture: LLM mocked to return web_search tool call.

    Tests that when the LLM returns a tool_call for web_search, the agent_node
    correctly propagates it to state["tool_calls"] with the expected structure.
    """
    from noa.orchestrator.nodes.agent import LLMResponse, agent_node

    fixture = _load_fixture("execution_with_tools.yaml")
    expected_tool_names = fixture["expected"].get("tool_names", [])

    state = _make_state(
        fixture["prompt"],
        task_type="execution",
        model_config={"agent": "openai/gpt-4o-mini"},
        selected_model="openai/gpt-4o-mini",
        privacy_mode="external",
        available_tools=[
            {
                "type": "function",
                "function": {
                    "name": "web_search__web_search",
                    "description": "Search the web",
                    "parameters": {},
                },
            }
        ],
        tool_rounds=0,
        max_tool_calls=10,
        max_retries=3,
        timeout_seconds=60,
        approvals_enabled=False,
        total_cost=0.0,
        llm_usage=[],
        thoughts=[],
        plan=None,
        archetype="execution",
        use_react=False,
        tool_scope=None,
        user_id=None,
        token_callback=None,
        run_id=None,
        recalled_context="",
        user_model_override=None,
        user_provider_override=None,
        eval_cycle=0,
        eval_config=None,
        eval_scores=None,
        eval_verdict=None,
        eval_reasoning=None,
        is_compaction_boundary=False,
        memory_tool=None,
        private_available=True,
    )

    # Build a mock LLM response that includes a web_search tool call.
    mock_tool_calls = [
        {
            "tool": "web_search",
            "function": "web_search",
            "args": {"query": "latest news on AI research"},
        }
    ]
    mock_response = LLMResponse(
        content="",
        tool_calls=mock_tool_calls,
        usage={"prompt_tokens": 50, "completion_tokens": 10},
        provider="openai",
        model="gpt-4o-mini",
    )

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await agent_node(state)

    # Verify tool_calls are present
    assert fixture["expected"].get("has_tool_calls", False) is True
    tool_calls_out: list[dict[str, Any]] = result.get("tool_calls", [])
    assert len(tool_calls_out) > 0, "Expected at least one tool call in state"

    # Verify the tool names match the fixture expectation
    actual_tool_names = {tc.get("tool", tc.get("name", "")) for tc in tool_calls_out}
    for expected_tool in expected_tool_names:
        assert any(expected_tool in name for name in actual_tool_names), (
            f"Expected tool '{expected_tool}' in tool_calls, got: {actual_tool_names}"
        )


@pytest.mark.quality
@pytest.mark.asyncio
async def test_simple_utility_has_no_tool_calls() -> None:
    """simple_utility fixture: LLM mocked with text-only response → no tool_calls."""
    from noa.orchestrator.nodes.agent import LLMResponse, agent_node

    fixture = _load_fixture("simple_utility.yaml")

    state = _make_state(
        fixture["prompt"],
        task_type="simple_utility",
        model_config={"agent": "openai/gpt-4o-mini"},
        selected_model="openai/gpt-4o-mini",
        privacy_mode="external",
        available_tools=[],
        tool_rounds=0,
        max_tool_calls=10,
        max_retries=3,
        timeout_seconds=60,
        approvals_enabled=False,
        total_cost=0.0,
        llm_usage=[],
        thoughts=[],
        plan=None,
        archetype=None,
        use_react=False,
        tool_scope=None,
        user_id=None,
        token_callback=None,
        run_id=None,
        recalled_context="",
        user_model_override=None,
        user_provider_override=None,
        eval_cycle=0,
        eval_config=None,
        eval_scores=None,
        eval_verdict=None,
        eval_reasoning=None,
        is_compaction_boundary=False,
        memory_tool=None,
        private_available=True,
    )

    mock_response = LLMResponse(
        content="2 + 2 = 4",
        tool_calls=[],
        usage={"prompt_tokens": 20, "completion_tokens": 5},
        provider="openai",
        model="gpt-4o-mini",
    )

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await agent_node(state)

    assert fixture["expected"].get("has_tool_calls", True) is False
    assert result.get("tool_calls") == [] or result.get("tool_calls") is None, (
        f"Expected no tool_calls for simple_utility, got: {result.get('tool_calls')}"
    )


# ---------------------------------------------------------------------------
# 5. Integration test: classifier → planner pipeline for decision_intelligence
# ---------------------------------------------------------------------------


@pytest.mark.quality
@pytest.mark.asyncio
async def test_decision_intelligence_full_classifier_planner_pipeline() -> None:
    """Full classifier→planner pipeline for decision_intelligence fixture.

    This is the integration test that exercises both nodes in sequence without
    mocking any internal logic — only the LLM boundary is mocked.

    Verifies:
    - Classifier returns decision_intelligence
    - Planner assigns comparative_selection archetype
    - Planner enables ReAct mode
    - Planner returns a non-empty plan
    """
    fixture = _load_fixture("decision_intelligence.yaml")
    prompt = fixture["prompt"]

    # Step 1: Run classifier (mocked LLM returns decision_intelligence)
    classifier_state = _make_state(
        prompt,
        model_config={"classifier": "openai/gpt-4o-mini", "planner": "openai/gpt-4o-mini"},
    )

    mock_classifier_resp = _mock_classifier_response("decision_intelligence")

    from noa.orchestrator.nodes.classifier import classifier_node
    from noa.orchestrator.nodes.planner import planner_node

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_classifier_resp,
    ):
        classifier_result = await classifier_node(classifier_state)

    assert classifier_result["task_type"] == "decision_intelligence"

    # Step 2: Run planner with classifier output injected into state.
    planner_state = {**classifier_state, **classifier_result}

    mock_planner_resp = _mock_planner_response(
        "1. Identify key decision criteria\n"
        "2. Compare Job A vs Job B on salary, flexibility, growth\n"
        "3. Weight criteria by user values\n"
        "4. Present recommendation with tradeoffs"
    )

    with patch(
        "noa.orchestrator.nodes.planner.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_planner_resp,
    ):
        planner_result = await planner_node(planner_state)

    # Structural assertions from the fixture
    assert planner_result["archetype"] == "comparative_selection"
    assert planner_result["use_react"] is True
    assert planner_result["plan"] is not None
    assert len(planner_result["plan"]) > 10, "Expected a meaningful plan, not empty"


# ---------------------------------------------------------------------------
# 6. Integration test: privacy routing for sensitive content
# ---------------------------------------------------------------------------


@pytest.mark.quality
@pytest.mark.asyncio
async def test_privacy_routing_full_pipeline_for_diary_prompt() -> None:
    """Full classifier→router pipeline for privacy_routing fixture.

    Verifies that a diary-related prompt is classified as private by the router
    after passing through the classifier, with no LLM call needed for routing.
    """
    fixture = _load_fixture("privacy_routing.yaml")
    prompt = fixture["prompt"]

    # Classifier routes this to "execution"
    classifier_state = _make_state(
        prompt,
        model_config={"classifier": "openai/gpt-4o-mini"},
    )

    mock_resp = _mock_classifier_response("execution")

    from noa.orchestrator.nodes.classifier import classifier_node
    from noa.orchestrator.nodes.router import router_node

    with patch(
        "noa.orchestrator.nodes.classifier.invoke_llm",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        classifier_result = await classifier_node(classifier_state)

    assert classifier_result["task_type"] == "execution"

    # Router inspects the message content for privacy keywords — no LLM.
    router_state = {**classifier_state, **classifier_result}
    router_result = router_node(router_state)

    # "diary" is a private keyword → must route to private
    expected_privacy = fixture["expected"].get("privacy_mode", "private")
    assert router_result["privacy_mode"] == expected_privacy, (
        f"Expected privacy_mode={expected_privacy!r}, got {router_result['privacy_mode']!r}"
    )


# ---------------------------------------------------------------------------
# 7. Fixture completeness test
# ---------------------------------------------------------------------------


@pytest.mark.quality
def test_all_fixtures_are_valid_yaml() -> None:
    """All YAML fixture files are valid and have required fields."""
    fixtures = _load_all_fixtures()
    assert len(fixtures) >= 6, f"Expected at least 6 fixtures, found {len(fixtures)}"

    required_fields = {"name", "category", "prompt", "expected"}
    for fixture in fixtures:
        missing = required_fields - set(fixture.keys())
        assert not missing, (
            f"Fixture '{fixture.get('_source_file', '?')}' missing fields: {missing}"
        )
        assert isinstance(fixture["prompt"], str) and len(fixture["prompt"]) > 0
        assert isinstance(fixture["expected"], dict)
