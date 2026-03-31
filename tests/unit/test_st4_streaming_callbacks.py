"""ST4: Verify per-run token callback isolation (no module-global race).

Resolves W24-M1 (concurrent token draining) and W24-M2 (per-request stream callback).
"""

from __future__ import annotations

from typing import Any

import pytest


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Create a minimal state dict with defaults."""
    base: dict[str, Any] = {
        "messages": [],
        "privacy_mode": "external",
        "selected_model": "gpt-4o",
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
        "timeout_seconds": 300,
        "approvals_enabled": True,
        "private_available": True,
        "user_id": "test-user",
        "tool_scope": None,
        "task_type": "execution",
        "plan": None,
        "archetype": "execution",
        "thoughts": [],
        "use_react": False,
        "token_callback": None,
        "run_id": None,
        "eval_scores": None,
        "eval_verdict": None,
        "eval_cycle": 0,
        "is_compaction_boundary": False,
    }
    base.update(overrides)
    return base


class TestTokenCallbackInState:
    """Verify token_callback field exists in AgentState."""

    def test_token_callback_field_exists(self) -> None:
        state = _make_state()
        assert "token_callback" in state

    def test_token_callback_is_callable(self) -> None:
        async def my_cb(token: str) -> None:
            pass

        state = _make_state(token_callback=my_cb)
        assert state["token_callback"] is my_cb


class TestCallbackIsolation:
    """Verify two concurrent runs have independent callbacks."""

    @pytest.mark.asyncio
    async def test_concurrent_runs_dont_cross_contaminate(self) -> None:
        """Simulate two runs with different callbacks — tokens stay isolated."""
        run_a_tokens: list[str] = []
        run_b_tokens: list[str] = []

        async def cb_a(token: str) -> None:
            run_a_tokens.append(token)

        async def cb_b(token: str) -> None:
            run_b_tokens.append(token)

        state_a = _make_state(token_callback=cb_a, run_id="run-a")
        state_b = _make_state(token_callback=cb_b, run_id="run-b")

        # Simulate agent node reading callback from state
        callback_a = state_a.get("token_callback")
        callback_b = state_b.get("token_callback")

        assert callback_a is not callback_b

        # Simulate token delivery
        await callback_a("hello")  # type: ignore[misc]
        await callback_b("world")  # type: ignore[misc]
        await callback_a(" from A")  # type: ignore[misc]

        assert run_a_tokens == ["hello", " from A"]
        assert run_b_tokens == ["world"]


class TestAgentNodeReadsFromState:
    """Verify agent.py reads callback from state, not just module global."""

    def test_agent_node_uses_state_callback(self) -> None:
        import inspect

        from noa.orchestrator.nodes.agent import agent_node

        source = inspect.getsource(agent_node)
        assert "token_callback" in source

    @pytest.mark.asyncio
    async def test_agent_node_calls_state_token_callback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """agent_node uses token_callback from state, not just module global.

        Verifies that when state["token_callback"] is set and available_tools=[],
        agent_node calls invoke_llm_stream with that callback — proving per-run
        isolation (the state callback is preferred over the module global).
        """
        from noa.orchestrator.nodes import agent as agent_mod
        from noa.orchestrator.nodes.agent import LLMResponse, agent_node

        received_callbacks: list[object] = []

        async def fake_invoke_llm_stream(
            model: str,
            messages: list,
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            temperature: object = None,
            token_callback: object = None,
        ) -> LLMResponse:
            received_callbacks.append(token_callback)
            return LLMResponse(
                content="Hello from streaming",
                tool_calls=[],
                usage={"prompt_tokens": 5, "completion_tokens": 10},
                provider="openai",
                model="gpt-4o",
            )

        monkeypatch.setattr(agent_mod, "invoke_llm_stream", fake_invoke_llm_stream)

        tokens_received: list[str] = []

        async def my_callback(token: str) -> None:
            tokens_received.append(token)

        state = _make_state(
            token_callback=my_callback,
            available_tools=[],  # No tools — enables streaming path
            selected_model="openai/gpt-4o",
            messages=[
                {"role": "system", "content": "You are an assistant."},
                {"role": "user", "content": "Say hello."},
            ],
        )
        from noa.orchestrator.state import AgentState

        result = await agent_node(AgentState(**state))  # type: ignore[typeddict-item]

        # Streaming path was taken — invoke_llm_stream was called
        assert len(received_callbacks) == 1, (
            "Expected invoke_llm_stream to be called exactly once"
        )
        # The callback passed to invoke_llm_stream must be our per-run callback
        assert received_callbacks[0] is my_callback, (
            "agent_node must pass the per-run state callback to invoke_llm_stream, "
            f"got {received_callbacks[0]!r} instead"
        )
        assert result["response"] == "Hello from streaming"

    @pytest.mark.asyncio
    async def test_agent_node_no_callback_uses_non_streaming_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When token_callback is None and no module global, agent_node uses invoke_llm."""
        from noa.orchestrator.nodes import agent as agent_mod
        from noa.orchestrator.nodes.agent import LLMResponse, agent_node

        stream_call_count = [0]
        llm_call_count = [0]

        async def fake_invoke_llm_stream(*args: object, **kwargs: object) -> LLMResponse:
            stream_call_count[0] += 1
            return LLMResponse(content="streaming", tool_calls=[], usage={})

        async def fake_invoke_llm(
            model: str,
            messages: list,
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            tools: object = None,
            temperature: object = None,
        ) -> LLMResponse:
            llm_call_count[0] += 1
            return LLMResponse(
                content="Non-streaming reply",
                tool_calls=[],
                usage={"prompt_tokens": 3, "completion_tokens": 7},
                provider="openai",
                model="gpt-4o",
            )

        monkeypatch.setattr(agent_mod, "invoke_llm_stream", fake_invoke_llm_stream)
        monkeypatch.setattr(agent_mod, "invoke_llm", fake_invoke_llm)
        # Ensure module global is also None
        monkeypatch.setattr(agent_mod, "_stream_callback", None)

        state = _make_state(
            token_callback=None,
            available_tools=[],
            selected_model="openai/gpt-4o",
            messages=[{"role": "user", "content": "Hello."}],
        )
        from noa.orchestrator.state import AgentState

        result = await agent_node(AgentState(**state))  # type: ignore[typeddict-item]

        assert stream_call_count[0] == 0, "invoke_llm_stream must NOT be called when no callback"
        assert llm_call_count[0] == 1, "invoke_llm must be called on non-streaming path"
        assert result["response"] == "Non-streaming reply"


class TestRunnerPassesCallbackInState:
    """Verify runner.py injects token_callback into initial_state."""

    def test_runner_sets_token_callback_in_state(self) -> None:
        import inspect

        from noa.orchestrator.runner import OrchestratorRunner

        source = inspect.getsource(OrchestratorRunner.run)
        assert '"token_callback"' in source


class TestNoModuleGlobalCleanup:
    """Verify runner no longer calls set_stream_callback(None) for cleanup."""

    def test_no_set_stream_callback_none_in_runner(self) -> None:
        import inspect

        from noa.orchestrator.runner import OrchestratorRunner

        source = inspect.getsource(OrchestratorRunner.run)
        assert "set_stream_callback(None)" not in source
        assert "set_stream_callback(_token_cb)" not in source
