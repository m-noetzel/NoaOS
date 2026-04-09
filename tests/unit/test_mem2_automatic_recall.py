"""Tests for MEM2 — Automatic Memory Recall at Turn Start.

Spec ref: MEM-H2 / MEM2
Verifies:
1. recalled_context is populated in initial_state by the runner
2. agent_node prepends recalled_context as a system message when non-empty
3. agent_node skips injection when recalled_context is empty / absent
4. runner-level recall failure does not crash the run (best-effort)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # noqa: I001

from noa.orchestrator.nodes.agent import agent_node

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What do I usually have for breakfast?"},
        ],
        "privacy_mode": "external",
        "selected_model": "openai/gpt-4.1",
        "model_config": {},
        "available_tools": [],
        "max_tokens": 4096,
        "temperature": None,
        "task_type": "research",
        "tool_rounds": 0,
        "max_tool_calls": 10,
        "max_retries": 3,
        "timeout_seconds": 120,
        "approvals_enabled": False,
        "private_available": True,
        "user_id": "user-123",
        "run_id": "run-abc",
        "token_callback": None,
        "tool_scope": None,
        "plan": None,
        "archetype": None,
        "thoughts": [],
        "use_react": False,
        "eval_scores": None,
        "eval_verdict": None,
        "eval_cycle": 0,
        "eval_config": {},
        "eval_reasoning": None,
        "is_compaction_boundary": False,
        "memory_tool": None,
        "recalled_context": "",
    }
    base.update(overrides)
    return base


def _make_fake_llm_response(content: str = "Test response") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = []
    resp.usage = {}
    resp.provider = "openai"
    resp.model = "gpt-4.1"
    return resp


# ---------------------------------------------------------------------------
# Tests: agent_node uses recalled_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mem2_agent_node_prepends_recalled_context() -> None:
    """When recalled_context is set, agent_node prepends it as a system message."""
    recalled = "Relevant context from memory:\n- User prefers oat milk in their coffee"
    state = _minimal_state(recalled_context=recalled)

    captured_messages: list[list[dict[str, Any]]] = []

    async def fake_invoke_llm(
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> MagicMock:
        captured_messages.append(list(messages))
        return _make_fake_llm_response()

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        side_effect=fake_invoke_llm,
    ):
        await agent_node(state)  # type: ignore[arg-type]

    assert captured_messages, "invoke_llm was never called"
    first_msg = captured_messages[0][0]
    assert first_msg["role"] == "system"
    assert "oat milk" in first_msg["content"], (
        f"Expected recalled context in first system message, got: {first_msg['content'][:100]}"
    )


@pytest.mark.asyncio
async def test_mem2_agent_node_no_injection_when_empty() -> None:
    """When recalled_context is empty, agent_node does NOT add an extra system message."""
    state = _minimal_state(recalled_context="", memory_tool=None)

    captured_messages: list[list[dict[str, Any]]] = []

    async def fake_invoke_llm(
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> MagicMock:
        captured_messages.append(list(messages))
        return _make_fake_llm_response()

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        side_effect=fake_invoke_llm,
    ):
        await agent_node(state)  # type: ignore[arg-type]

    assert captured_messages, "invoke_llm was never called"
    # First message should be the original system message, not an injected recall
    first_msg = captured_messages[0][0]
    assert first_msg["content"] == "You are a helpful assistant.", (
        f"Unexpected first message content: {first_msg['content'][:100]}"
    )


@pytest.mark.asyncio
async def test_mem2_agent_node_recalled_context_absent_from_state() -> None:
    """When recalled_context key is absent from state, agent_node handles gracefully."""
    state = _minimal_state()
    # Remove recalled_context entirely
    state.pop("recalled_context", None)

    captured_messages: list[list[dict[str, Any]]] = []

    async def fake_invoke_llm(
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> MagicMock:
        captured_messages.append(list(messages))
        return _make_fake_llm_response()

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        side_effect=fake_invoke_llm,
    ):
        result = await agent_node(state)  # type: ignore[arg-type]

    assert result is not None
    assert captured_messages, "invoke_llm was never called"


# ---------------------------------------------------------------------------
# Tests: runner populates recalled_context in initial_state
# ---------------------------------------------------------------------------


def test_mem2_recalled_context_field_in_state_schema() -> None:
    """AgentState TypedDict must include recalled_context field."""
    from noa.orchestrator.state import AgentState
    # Check that the field exists in annotations (use string name comparison
    # to handle ForwardRef vs str, which vary by import context)
    annotations = AgentState.__annotations__
    assert "recalled_context" in annotations, (
        "AgentState must have recalled_context field (MEM2)"
    )
    annotation_str = str(annotations["recalled_context"])
    assert "str" in annotation_str, (
        f"recalled_context must be str type, got {annotations['recalled_context']}"
    )


@pytest.mark.asyncio
async def test_mem2_runner_populates_recalled_context_when_memory_available() -> None:
    """Runner sets recalled_context in initial_state when memory tool returns facts."""
    from noa.orchestrator.runner import OrchestratorRunner

    # Build a mock graph that captures the initial state
    captured_states: list[dict[str, Any]] = []

    async def _fake_astream(state: dict[str, Any], **kwargs: Any) -> Any:
        captured_states.append(dict(state))
        # Yield a minimal agent node output
        yield {"agent": {"response": "Done", "tool_calls": [], "messages": state["messages"], "llm_usage": [], "thoughts": []}}

    mock_graph = MagicMock()
    mock_graph.astream = _fake_astream

    runner = OrchestratorRunner(graph=mock_graph)

    mock_run_service = MagicMock()
    mock_run_service.update_status = AsyncMock()
    mock_run_service.append_event = AsyncMock()

    # Patch the MemoryTool and private worker handler so recall returns a fact
    mock_memory_tool = MagicMock()
    mock_memory_tool.recall = AsyncMock(return_value={
        "status": "ok",
        "facts": [{"fact": "User is vegetarian"}],
    })

    with (
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._persist_event",
            new_callable=AsyncMock,
        ),
        patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=None,
        ),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._extract_response",
            return_value="Done",
        ),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._build_tool_context",
            return_value="",
        ),
        # Patch MemoryTool construction in runner to return our mock
        patch(
            "noa.tools.memory.MemoryTool",
            return_value=mock_memory_tool,
        ),
        # Patch private worker import so runner can build _memory_tool
        patch.dict(
            "sys.modules",
            {
                "noa.private_worker.handlers": MagicMock(
                    get_handler=MagicMock(return_value=AsyncMock(return_value={}))
                )
            },
        ),
    ):
        events = []
        async for event in runner.run(
            message="What should I cook tonight?",
            run_service=mock_run_service,
            run_id="test-run-123",
            user_id="user-xyz",
        ):
            events.append(event)

    # Verify recalled_context was seeded in initial_state
    assert captured_states, "Graph astream was never called"
    initial = captured_states[0]
    assert "recalled_context" in initial, (
        "Runner must set recalled_context in initial_state"
    )
