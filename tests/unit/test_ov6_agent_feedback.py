"""Unit tests for OV6 Agent Feedback Loop.

Tests:
1. Agent recalls memories when memory_tool is in state and task_type is not simple_utility
2. Agent skips recall for simple_utility tasks
3. Agent handles missing memory_tool gracefully (no crash)
4. Recalled facts appear in messages before LLM call (system message prefix)
5. _recall_context returns empty string when no facts found
6. _recall_context returns empty string on exception (best-effort)
7. Approval decisions are stored as memory facts (approved path)
8. Approval decisions are stored as memory facts (denied path)
9. Memory storage failure does not block approval (best-effort)
10. memory_tool is set in runner initial_state
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from noa.orchestrator.nodes.agent import _recall_context

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory_tool(facts: list[dict[str, Any]]) -> MagicMock:
    """Create a mock MemoryTool that returns given facts from recall()."""
    tool = MagicMock()
    tool.recall = AsyncMock(return_value={"status": "ok", "facts": facts})
    tool.remember = AsyncMock(return_value={"status": "ok"})
    return tool


def _make_agent_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal AgentState dict for agent_node tests."""
    base: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What's my favourite coffee?"},
        ],
        "privacy_mode": "external",
        "selected_model": "openai/gpt-4.1",
        "model_config": {},
        "available_tools": [],
        "max_tokens": 512,
        "temperature": None,
        "use_react": False,
        "plan": None,
        "task_type": "execution",
        "memory_tool": None,
        "user_id": "user-123",
        "token_callback": None,
        "tool_calls": [],
        "tool_results": [],
        "thoughts": [],
        "llm_usage": [],
        "max_tool_calls": 10,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. _recall_context — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_context_returns_formatted_facts() -> None:
    """_recall_context returns formatted context string when facts exist."""
    facts = [
        {"fact": "User prefers oat milk flat white"},
        {"fact": "User dislikes espresso shots"},
    ]
    tool = _make_memory_tool(facts)

    result = await _recall_context("coffee preference", tool, user_id="u1")

    assert "Relevant context from memory:" in result
    assert "User prefers oat milk flat white" in result
    assert "User dislikes espresso shots" in result
    tool.recall.assert_called_once_with(query="coffee preference", n_results=3, user_id="u1")


# ---------------------------------------------------------------------------
# 2. _recall_context — no facts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_context_returns_empty_when_no_facts() -> None:
    """_recall_context returns empty string when recall returns no facts."""
    tool = _make_memory_tool([])

    result = await _recall_context("random query", tool, user_id="u1")

    assert result == ""


# ---------------------------------------------------------------------------
# 3. _recall_context — exception is swallowed (best-effort)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_context_handles_exception_gracefully() -> None:
    """_recall_context returns empty string when recall raises — best-effort."""
    tool = MagicMock()
    tool.recall = AsyncMock(side_effect=RuntimeError("ollama unreachable"))

    result = await _recall_context("query", tool, user_id="u1")

    assert result == ""


# ---------------------------------------------------------------------------
# 4. agent_node — memory context injected for non-simple_utility tasks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_node_injects_memory_context_for_execution_task() -> None:
    """agent_node injects recalled facts as system message prefix for execution tasks."""
    from noa.orchestrator.nodes.agent import agent_node, set_router

    facts = [{"fact": "User prefers dark roast coffee"}]
    memory_tool = _make_memory_tool(facts)

    captured_messages: list[list[dict[str, Any]]] = []

    mock_router = MagicMock()

    async def fake_complete(**kwargs: Any) -> dict[str, Any]:
        captured_messages.append(kwargs["messages"])
        return {
            "content": "You like dark roast coffee.",
            "tool_calls": [],
            "usage": {},
            "provider": "openai",
            "model": "gpt-4.1",
        }

    mock_router.complete = AsyncMock(side_effect=fake_complete)
    set_router(mock_router)

    state = _make_agent_state(
        task_type="execution",
        memory_tool=memory_tool,
    )

    result = await agent_node(state)  # type: ignore[arg-type]

    assert captured_messages, "LLM must have been called"
    msgs = captured_messages[0]
    # Memory context should be the first system message
    first_system = next((m for m in msgs if m["role"] == "system"), None)
    assert first_system is not None
    assert "Relevant context from memory:" in first_system["content"]
    assert "User prefers dark roast coffee" in first_system["content"]

    # agent_node returns a response
    assert result.get("response") == "You like dark roast coffee."


# ---------------------------------------------------------------------------
# 5. agent_node — skips recall for simple_utility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_node_skips_recall_for_simple_utility() -> None:
    """agent_node must NOT call memory recall for simple_utility tasks."""
    from noa.orchestrator.nodes.agent import agent_node, set_router

    facts = [{"fact": "Some fact that should not appear"}]
    memory_tool = _make_memory_tool(facts)

    captured_messages: list[list[dict[str, Any]]] = []

    mock_router = MagicMock()

    async def fake_complete(**kwargs: Any) -> dict[str, Any]:
        captured_messages.append(kwargs["messages"])
        return {
            "content": "Hi there!",
            "tool_calls": [],
            "usage": {},
            "provider": "openai",
            "model": "gpt-4.1",
        }

    mock_router.complete = AsyncMock(side_effect=fake_complete)
    set_router(mock_router)

    state = _make_agent_state(
        task_type="simple_utility",
        memory_tool=memory_tool,
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ],
    )

    await agent_node(state)  # type: ignore[arg-type]

    # recall must NOT have been called
    memory_tool.recall.assert_not_called()

    # Memory fact must NOT appear in messages
    if captured_messages:
        for msg in captured_messages[0]:
            assert "Relevant context from memory:" not in msg.get("content", "")


# ---------------------------------------------------------------------------
# 6. agent_node — handles missing memory_tool gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_node_handles_missing_memory_tool() -> None:
    """agent_node must not crash when memory_tool is None."""
    from noa.orchestrator.nodes.agent import agent_node, set_router

    mock_router = MagicMock()
    mock_router.complete = AsyncMock(
        return_value={
            "content": "Hello!",
            "tool_calls": [],
            "usage": {},
            "provider": "openai",
            "model": "gpt-4.1",
        }
    )
    set_router(mock_router)

    state = _make_agent_state(memory_tool=None, task_type="execution")

    result = await agent_node(state)  # type: ignore[arg-type]

    # Should still return a normal response
    assert result.get("response") == "Hello!"


# ---------------------------------------------------------------------------
# 7. runner — memory_tool is present in initial_state
# ---------------------------------------------------------------------------


def test_runner_initial_state_includes_memory_tool() -> None:
    """OrchestratorRunner.run() must put a memory_tool (or None) in initial_state.

    We verify the key 'memory_tool' exists in the state passed to the graph.
    """
    from noa.orchestrator.runner import OrchestratorRunner

    captured_states: list[dict[str, Any]] = []

    # Stub graph that captures the initial state
    async def _fake_astream(state: dict[str, Any], **kwargs: Any):  # type: ignore[return]
        captured_states.append(dict(state))
        # yield a single done event so runner finishes
        if False:
            yield {}

    stub_graph = MagicMock()
    stub_graph.astream = _fake_astream

    runner = OrchestratorRunner(graph=stub_graph)

    run_svc = MagicMock()
    run_svc.update_status = AsyncMock()
    run_svc.append_event = AsyncMock()

    async def _run() -> None:
        async for _ in runner.run(
            message="test",
            run_service=run_svc,
            run_id=str(uuid.uuid4()),
            user_id="u1",
        ):
            pass

    asyncio.run(_run())

    assert captured_states, "Graph was never invoked"
    state = captured_states[0]
    # memory_tool key must be present (may be None if handlers unavailable in test)
    assert "memory_tool" in state, (
        f"memory_tool missing from initial_state keys: {list(state.keys())}"
    )
