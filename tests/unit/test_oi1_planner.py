"""Tests for OI1: Planning Node + ReAct Execution.

Covers:
- Archetype selection for each task_type
- simple_utility skips planning (no LLM call)
- ReAct thought parsing from agent response
- Plan injection into agent system message
- Graph topology (6 nodes: router, classifier, planner, agent, tools, responder)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from noa.orchestrator.nodes.agent import _parse_react_thoughts, agent_node
from noa.orchestrator.nodes.planner import (
    ARCHETYPES,
    planner_node,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs: Any) -> dict[str, Any]:
    """Return a minimal AgentState dict with sensible defaults."""
    defaults: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Test request"}],
        "privacy_mode": "external",
        "selected_model": "openai/gpt-4.1",
        "user_model_override": None,
        "user_provider_override": None,
        "user_privacy_override": None,
        "requested_tools": None,
        "tool_calls": [],
        "tool_results": [],
        "response": None,
        "total_cost": 0.0,
        "model_config": {},
        "tool_rounds": 0,
        "llm_usage": [],
        "available_tools": [],
        "max_tool_calls": 10,
        "max_retries": 3,
        "timeout_seconds": 120,
        "approvals_enabled": True,
        "private_available": True,
        "user_id": None,
        "tool_scope": None,
        "task_type": "execution",
        "plan": None,
        "archetype": None,
        "thoughts": [],
        "use_react": False,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Planner node tests
# ---------------------------------------------------------------------------

class TestArchetypeSelection:
    """Test that each task_type maps to the correct archetype."""

    def test_simple_utility_maps_to_none(self) -> None:
        assert ARCHETYPES["simple_utility"] is None

    def test_execution_maps_to_execution(self) -> None:
        assert ARCHETYPES["execution"] == "execution"

    def test_research_maps_to_research(self) -> None:
        assert ARCHETYPES["research"] == "research"

    def test_decision_intelligence_maps_to_comparative_selection(self) -> None:
        assert ARCHETYPES["decision_intelligence"] == "comparative_selection"


class TestSimpleUtilitySkipsPlanning:
    """simple_utility must return immediately without invoking the LLM."""

    @pytest.mark.asyncio
    async def test_simple_utility_returns_no_plan(self) -> None:
        state = _make_state(task_type="simple_utility")
        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
        ) as mock_invoke:
            result = await planner_node(state)  # type: ignore[arg-type]

        mock_invoke.assert_not_called()
        assert result["plan"] is None
        assert result["archetype"] is None
        assert result["use_react"] is False
        assert result["thoughts"] == []

    @pytest.mark.asyncio
    async def test_simple_utility_no_llm_call_regardless_of_messages(self) -> None:
        state = _make_state(
            task_type="simple_utility",
            messages=[{"role": "user", "content": "Hello"}],
        )
        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
        ) as mock_invoke:
            await planner_node(state)  # type: ignore[arg-type]
        mock_invoke.assert_not_called()


class TestPlannerGeneratesPlan:
    """Non-simple_utility tasks should invoke LLM and return plan."""

    @pytest.mark.asyncio
    async def test_execution_generates_plan(self) -> None:
        state = _make_state(task_type="execution")
        mock_resp = AsyncMock()
        mock_resp.content = "1. Verify action\n2. Execute\n3. Confirm"

        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await planner_node(state)  # type: ignore[arg-type]

        assert result["plan"] == "1. Verify action\n2. Execute\n3. Confirm"
        assert result["archetype"] == "execution"
        assert result["use_react"] is False

    @pytest.mark.asyncio
    async def test_research_sets_use_react_true(self) -> None:
        state = _make_state(task_type="research")
        mock_resp = AsyncMock()
        mock_resp.content = "1. Search\n2. Synthesize"

        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await planner_node(state)  # type: ignore[arg-type]

        assert result["use_react"] is True
        assert result["archetype"] == "research"

    @pytest.mark.asyncio
    async def test_decision_intelligence_sets_use_react_true(self) -> None:
        state = _make_state(task_type="decision_intelligence")
        mock_resp = AsyncMock()
        mock_resp.content = "1. Identify options\n2. Compare\n3. Recommend"

        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            result = await planner_node(state)  # type: ignore[arg-type]

        assert result["use_react"] is True
        assert result["archetype"] == "comparative_selection"

    @pytest.mark.asyncio
    async def test_planner_uses_planner_model_config(self) -> None:
        """Planner should prefer 'planner' key in model_config."""
        state = _make_state(
            task_type="research",
            model_config={"planner": "openai/gpt-4o-mini", "classifier": "other/model"},
        )
        mock_resp = AsyncMock()
        mock_resp.content = "1. Step one"
        captured_models: list[str] = []

        async def _fake_invoke(model: str, **kwargs: Any) -> Any:
            captured_models.append(model)
            return mock_resp

        with patch("noa.orchestrator.nodes.planner.invoke_llm", side_effect=_fake_invoke):
            await planner_node(state)  # type: ignore[arg-type]

        assert captured_models[0] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_planner_fallback_to_classifier_model(self) -> None:
        """Falls back to 'classifier' key when 'planner' is absent."""
        state = _make_state(
            task_type="research",
            model_config={"classifier": "openai/gpt-4o-mini"},
        )
        mock_resp = AsyncMock()
        mock_resp.content = "1. Step"
        captured_models: list[str] = []

        async def _fake_invoke(model: str, **kwargs: Any) -> Any:
            captured_models.append(model)
            return mock_resp

        with patch("noa.orchestrator.nodes.planner.invoke_llm", side_effect=_fake_invoke):
            await planner_node(state)  # type: ignore[arg-type]

        assert captured_models[0] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_planner_llm_failure_returns_no_plan(self) -> None:
        """LLM failure must not raise — planner returns gracefully without plan."""
        state = _make_state(task_type="execution")

        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = await planner_node(state)  # type: ignore[arg-type]

        assert result["plan"] is None
        assert result["archetype"] == "execution"  # archetype still set

    @pytest.mark.asyncio
    async def test_model_none_skips_llm_call(self) -> None:
        """When model is 'none', skip LLM call but return archetype."""
        state = _make_state(
            task_type="execution",
            model_config={"planner": "none"},
        )
        with patch(
            "noa.orchestrator.nodes.planner.invoke_llm",
            new_callable=AsyncMock,
        ) as mock_invoke:
            result = await planner_node(state)  # type: ignore[arg-type]

        mock_invoke.assert_not_called()
        assert result["plan"] is None
        assert result["archetype"] == "execution"


# ---------------------------------------------------------------------------
# ReAct thought parsing tests
# ---------------------------------------------------------------------------

class TestReActThoughtParsing:
    """Test _parse_react_thoughts extracts Thought lines correctly."""

    def test_parses_single_thought(self) -> None:
        content = "Thought: I should search for current data.\nLet me do that."
        thoughts = _parse_react_thoughts(content, [])
        assert len(thoughts) == 1
        assert thoughts[0]["text"] == "I should search for current data."
        assert thoughts[0]["step"] == 1
        assert thoughts[0]["action"] is None

    def test_parses_multiple_thoughts(self) -> None:
        content = (
            "Thought: First I'll check the calendar.\n"
            "Some action happens here.\n"
            "Thought: Now I'll summarize the results."
        )
        thoughts = _parse_react_thoughts(content, [])
        assert len(thoughts) == 2
        assert thoughts[0]["text"] == "First I'll check the calendar."
        assert thoughts[1]["text"] == "Now I'll summarize the results."

    def test_no_thoughts_returns_existing(self) -> None:
        content = "Here is my answer with no thought markers."
        existing = [{"step": 1, "text": "Prior thought", "action": None}]
        thoughts = _parse_react_thoughts(content, existing)
        assert len(thoughts) == 1
        assert thoughts[0]["text"] == "Prior thought"

    def test_appends_to_existing_thoughts(self) -> None:
        content = "Thought: New thought after tool call."
        existing = [{"step": 1, "text": "Old thought", "action": None}]
        thoughts = _parse_react_thoughts(content, existing)
        assert len(thoughts) == 2
        assert thoughts[0]["text"] == "Old thought"
        assert thoughts[1]["text"] == "New thought after tool call."

    def test_step_offset_based_on_existing(self) -> None:
        content = "Thought: Step three."
        existing = [
            {"step": 1, "text": "One", "action": None},
            {"step": 2, "text": "Two", "action": None},
        ]
        thoughts = _parse_react_thoughts(content, existing)
        # step offset = 2 (len of existing), line index = 0, so step = 2 + 0 + 1 = 3
        assert thoughts[2]["step"] == 3

    def test_empty_content_returns_existing(self) -> None:
        existing = [{"step": 1, "text": "prev", "action": None}]
        thoughts = _parse_react_thoughts("", existing)
        assert thoughts == existing


# ---------------------------------------------------------------------------
# Agent node plan injection tests
# ---------------------------------------------------------------------------

class TestAgentNodePlanInjection:
    """Test that plan and ReAct instruction are injected into the system message."""

    @pytest.mark.asyncio
    async def test_plan_injected_into_existing_system_message(self) -> None:
        """When plan is set, it should appear in the system message sent to LLM."""
        captured_msgs: list[list[dict[str, Any]]] = []

        async def _fake_invoke(
            model: str,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> Any:
            captured_msgs.append(messages)
            resp = AsyncMock()
            resp.content = "Done"
            resp.tool_calls = []
            resp.usage = {}
            resp.provider = ""
            resp.model = ""
            return resp

        state = _make_state(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Help me decide between A and B."},
            ],
            plan="1. Identify options\n2. Compare\n3. Recommend",
            use_react=False,
        )

        with (
            patch("noa.orchestrator.nodes.agent.invoke_llm", side_effect=_fake_invoke),
            patch("noa.orchestrator.nodes.agent._stream_callback", None),
        ):
            await agent_node(state)  # type: ignore[arg-type]

        assert captured_msgs, "invoke_llm was not called"
        sent_messages = captured_msgs[0]
        system_msg = next(m for m in sent_messages if m["role"] == "system")
        assert "Plan:" in system_msg["content"]
        assert "1. Identify options" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_react_instruction_injected_when_use_react_true(self) -> None:
        """When use_react is True, ReAct instruction should appear in system message."""
        captured_msgs: list[list[dict[str, Any]]] = []

        async def _fake_invoke(
            model: str,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> Any:
            captured_msgs.append(messages)
            resp = AsyncMock()
            resp.content = "Thought: I need to search.\nHere is my answer."
            resp.tool_calls = []
            resp.usage = {}
            resp.provider = ""
            resp.model = ""
            return resp

        state = _make_state(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Research quantum computing."},
            ],
            use_react=True,
            plan=None,
        )

        with (
            patch("noa.orchestrator.nodes.agent.invoke_llm", side_effect=_fake_invoke),
            patch("noa.orchestrator.nodes.agent._stream_callback", None),
        ):
            result = await agent_node(state)  # type: ignore[arg-type]

        assert captured_msgs
        system_msg = next(
            m for m in captured_msgs[0] if m["role"] == "system"
        )
        assert "Thought:" in system_msg["content"] or "step by step" in system_msg["content"]

        # Thoughts should be parsed and stored in result
        assert "thoughts" in result
        assert any("search" in t["text"].lower() for t in result["thoughts"])

    @pytest.mark.asyncio
    async def test_no_injection_when_no_plan_and_no_react(self) -> None:
        """Messages should pass through unchanged when neither plan nor use_react."""
        captured_msgs: list[list[dict[str, Any]]] = []
        original_system = "You are helpful."

        async def _fake_invoke(
            model: str,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> Any:
            captured_msgs.append(messages)
            resp = AsyncMock()
            resp.content = "Answer"
            resp.tool_calls = []
            resp.usage = {}
            resp.provider = ""
            resp.model = ""
            return resp

        state = _make_state(
            messages=[
                {"role": "system", "content": original_system},
                {"role": "user", "content": "Hello"},
            ],
            use_react=False,
            plan=None,
        )

        with (
            patch("noa.orchestrator.nodes.agent.invoke_llm", side_effect=_fake_invoke),
            patch("noa.orchestrator.nodes.agent._stream_callback", None),
        ):
            await agent_node(state)  # type: ignore[arg-type]

        assert captured_msgs
        system_msg = next(m for m in captured_msgs[0] if m["role"] == "system")
        assert system_msg["content"] == original_system


# ---------------------------------------------------------------------------
# Graph topology test
# ---------------------------------------------------------------------------

class TestGraphTopology:
    """Test that build_graph produces the correct 6-node topology."""

    def test_graph_has_six_nodes(self) -> None:
        from noa.orchestrator.graph import build_graph
        graph = build_graph()
        # LangGraph StateGraph nodes include __start__ and __end__ as well as
        # the explicitly added nodes.
        node_names = set(graph.nodes.keys())
        expected = {"router", "classifier", "planner", "agent", "tools", "responder"}
        assert expected.issubset(node_names), (
            f"Missing nodes: {expected - node_names}"
        )

    def test_planner_in_graph(self) -> None:
        """planner node must be present in the compiled graph."""
        from noa.orchestrator.graph import build_graph
        graph = build_graph()
        assert "planner" in graph.nodes

    def test_graph_compiles_without_error(self) -> None:
        """build_graph().compile() must not raise."""
        from noa.orchestrator.graph import build_graph
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None
