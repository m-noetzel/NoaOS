"""Tests for TS1 — Concurrent Token Delivery.

Verifies that token_stream SSE events are emitted in real-time as the LLM
generates them, not batched after node completion.

Test plan:
- Happy path: runner emits token_stream events BEFORE the step_started event
  for the same node (proves concurrent delivery, not post-node drain)
- Timing test: token callback fires mid-execution, tokens appear before result_ready
- Final response correctness: accumulated content matches after streaming
- Multiple tokens: all tokens arrive in order and before the final node event
- Integration: token_callback is set in state and fires from agent_node
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest  # noqa: F401

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _collect_events(
    runner: Any, **kwargs: Any
) -> list[dict[str, Any]]:
    """Collect all events from runner.run() into a list."""
    events = []
    async for event in runner.run(**kwargs):
        events.append(event)
    return events


def _make_mock_run_service() -> Any:
    svc = MagicMock()
    svc.update_status = AsyncMock()
    svc.append_event = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# TS1-1: Tokens arrive BEFORE node-completion step_started event (core test)
# ---------------------------------------------------------------------------


class TestConcurrentTokenDelivery:
    """TS1 core: tokens emitted concurrently, not post-node."""

    @pytest.mark.asyncio
    async def test_tokens_arrive_before_step_started(self):
        """TS1: token_stream events precede step_started for the agent node.

        This is the definitive test of concurrent delivery. In the old burst
        delivery model, tokens were drained AFTER the node completed, so they
        appeared after (or just before) step_started in the same batch. In the
        new concurrent model, token_stream events interleave with or precede
        the step_started for the agent node.

        The mock graph calls the token_callback during node execution, so tokens
        enter the event queue before the node-completion chunk is published.
        """
        from noa.orchestrator.runner import OrchestratorRunner

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            cb = initial_state.get("token_callback")
            if cb is not None:
                # Fire tokens during node execution (before node completes)
                await cb("Hello")
                await cb(", ")
                await cb("world")
                # Small yield to let event loop process tokens
                await asyncio.sleep(0)

            yield {
                "agent": {
                    "response": "Hello, world",
                    "tool_calls": [],
                    "messages": initial_state.get("messages", []),
                    "llm_usage": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_graph_astream

        runner = OrchestratorRunner(graph=mock_graph)
        events = await _collect_events(
            runner,
            message="test",
            run_service=_make_mock_run_service(),
            run_id="ts1-test-run",
        )

        event_types = [e["event_type"] for e in events]

        # All 3 tokens must appear
        token_events = [e for e in events if e["event_type"] == "token_stream"]
        assert len(token_events) == 3, (
            f"Expected 3 token_stream events, got {len(token_events)}. "
            f"Event types: {event_types}"
        )

        # Token content must be in correct order
        tokens = [e["payload"]["token"] for e in token_events]
        assert tokens == ["Hello", ", ", "world"]

        # token_stream events must appear BEFORE result_ready
        result_idx = event_types.index("result_ready")
        for te in token_events:
            te_idx = events.index(te)
            assert te_idx < result_idx, (
                f"token_stream must precede result_ready: "
                f"token at {te_idx}, result_ready at {result_idx}"
            )

    @pytest.mark.asyncio
    async def test_tokens_arrive_before_step_started_for_agent_node(self):
        """Token events arrive before the agent node's step_started.

        This distinguishes concurrent delivery (tokens queued first) from
        burst delivery (tokens drained after node completes, in same batch).
        """
        from noa.orchestrator.runner import OrchestratorRunner

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            cb = initial_state.get("token_callback")
            if cb is not None:
                # Fire tokens during node execution
                await cb("first")
                await cb("second")

            yield {
                "agent": {
                    "response": "firstsecond",
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_graph_astream
        runner = OrchestratorRunner(graph=mock_graph)

        events = await _collect_events(
            runner,
            message="hi",
            run_service=_make_mock_run_service(),
            run_id="ts1-order-test",
        )

        # Find the agent step_started event
        step_events = [
            (i, e) for i, e in enumerate(events)
            if e["event_type"] == "step_started"
            and e.get("payload", {}).get("step") == "agent"
        ]
        token_events = [
            (i, e) for i, e in enumerate(events)
            if e["event_type"] == "token_stream"
        ]

        assert len(token_events) == 2
        assert step_events, "Expected at least one step_started for agent node"

        agent_step_idx = step_events[0][0]
        # In concurrent delivery, tokens are in the queue before the chunk
        # is published, so they should appear before or at step_started.
        for tok_idx, _ in token_events:
            assert tok_idx < agent_step_idx, (
                f"token_stream at index {tok_idx} must precede "
                f"agent step_started at {agent_step_idx}. "
                f"Events: {[e['event_type'] for e in events]}"
            )

    @pytest.mark.asyncio
    async def test_final_response_correct_after_streaming(self):
        """Final response content is correct after streaming completes."""
        from noa.orchestrator.runner import OrchestratorRunner

        expected_response = "The answer is 42."

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            cb = initial_state.get("token_callback")
            if cb is not None:
                for word in ["The", " answer", " is", " 42."]:
                    await cb(word)

            yield {
                "agent": {
                    "response": expected_response,
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [
                        {
                            "provider": "openai",
                            "model": "gpt-4.1",
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cost_usd": 0.001,
                        }
                    ],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_graph_astream
        runner = OrchestratorRunner(graph=mock_graph)

        events = await _collect_events(
            runner,
            message="what is the answer?",
            run_service=_make_mock_run_service(),
            run_id="ts1-content-test",
        )

        # Verify token count
        token_events = [e for e in events if e["event_type"] == "token_stream"]
        assert len(token_events) == 4

        # Verify result_ready carries the full assembled response
        result_events = [e for e in events if e["event_type"] == "result_ready"]
        assert len(result_events) == 1
        assert result_events[0]["payload"]["response"] == expected_response

    @pytest.mark.asyncio
    async def test_no_tokens_when_callback_not_called(self):
        """No token_stream events if the callback is never invoked."""
        from noa.orchestrator.runner import OrchestratorRunner

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            # Node does NOT call token_callback (non-streaming path)
            yield {
                "agent": {
                    "response": "direct response",
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_graph_astream
        runner = OrchestratorRunner(graph=mock_graph)

        events = await _collect_events(
            runner,
            message="test",
            run_service=_make_mock_run_service(),
            run_id="ts1-no-tokens",
        )

        token_events = [e for e in events if e["event_type"] == "token_stream"]
        assert len(token_events) == 0

        # Response still arrives correctly
        result_events = [e for e in events if e["event_type"] == "result_ready"]
        assert len(result_events) == 1
        assert result_events[0]["payload"]["response"] == "direct response"


# ---------------------------------------------------------------------------
# TS1-2: token_callback is per-run (isolated between concurrent runs)
# ---------------------------------------------------------------------------


class TestTokenCallbackIsolation:
    """Each run gets its own token_callback — no cross-run pollution."""

    @pytest.mark.asyncio
    async def test_each_run_gets_own_callback(self):
        """Concurrent runs use isolated token callbacks via state injection."""
        from noa.orchestrator.runner import OrchestratorRunner

        run_a_tokens: list[str] = []
        run_b_tokens: list[str] = []

        async def mock_graph_astream_a(initial_state: dict) -> AsyncGenerator:
            cb = initial_state.get("token_callback")
            if cb is not None:
                await cb("run_a_token")
            yield {
                "agent": {
                    "response": "run_a",
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [],
                }
            }

        async def mock_graph_astream_b(initial_state: dict) -> AsyncGenerator:
            cb = initial_state.get("token_callback")
            if cb is not None:
                await cb("run_b_token")
            yield {
                "agent": {
                    "response": "run_b",
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [],
                }
            }

        mock_graph_a = MagicMock()
        mock_graph_a.astream = mock_graph_astream_a
        mock_graph_b = MagicMock()
        mock_graph_b.astream = mock_graph_astream_b

        runner_a = OrchestratorRunner(graph=mock_graph_a)
        runner_b = OrchestratorRunner(graph=mock_graph_b)

        # Collect events from both runners
        events_a = await _collect_events(
            runner_a,
            message="test_a",
            run_service=_make_mock_run_service(),
            run_id="run-a",
        )
        events_b = await _collect_events(
            runner_b,
            message="test_b",
            run_service=_make_mock_run_service(),
            run_id="run-b",
        )

        tokens_a = [
            e["payload"]["token"]
            for e in events_a
            if e["event_type"] == "token_stream"
        ]
        tokens_b = [
            e["payload"]["token"]
            for e in events_b
            if e["event_type"] == "token_stream"
        ]

        # Each run only received its own tokens
        assert tokens_a == ["run_a_token"]
        assert tokens_b == ["run_b_token"]


# ---------------------------------------------------------------------------
# TS1-3: invoke_llm_stream integration — callback fires per chunk
# ---------------------------------------------------------------------------


class TestInvokeLlmStreamConcurrency:
    """Verify invoke_llm_stream calls callback for each chunk during generation."""

    def setup_method(self):
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    def teardown_method(self):
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    @pytest.mark.asyncio
    async def test_callback_called_per_partial_chunk(self):
        """token_callback is called once per partial token, not once at end."""
        import noa.orchestrator.nodes.agent as agent_mod

        callback_call_count = 0
        callback_calls: list[str] = []

        async def counting_cb(token: str) -> None:
            nonlocal callback_call_count
            callback_call_count += 1
            callback_calls.append(token)

        async def fake_stream() -> AsyncGenerator[dict[str, Any], None]:
            yield {"type": "token", "content": "chunk1"}
            await asyncio.sleep(0)  # simulate async I/O between chunks
            yield {"type": "token", "content": "chunk2"}
            await asyncio.sleep(0)
            yield {"type": "token", "content": "chunk3"}
            yield {
                "type": "complete",
                "content": "chunk1chunk2chunk3",
                "tool_calls": [],
                "usage": {"input_tokens": 5, "output_tokens": 3},
                "provider": "openai",
                "model": "gpt-4.1",
            }

        mock_router = MagicMock()
        mock_router.complete_stream = AsyncMock(return_value=fake_stream())
        agent_mod._router = mock_router

        result = await agent_mod.invoke_llm_stream(
            "openai/gpt-4.1",
            [{"role": "user", "content": "hi"}],
            token_callback=counting_cb,
        )

        # Callback called 3 times (once per chunk, not once at end)
        assert callback_call_count == 3
        assert callback_calls == ["chunk1", "chunk2", "chunk3"]
        # Final response assembled correctly
        assert result.content == "chunk1chunk2chunk3"
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_callback_called_before_return(self):
        """All token callbacks fire before invoke_llm_stream returns."""
        import noa.orchestrator.nodes.agent as agent_mod

        callback_fired = False
        result_available = False

        async def cb(token: str) -> None:
            nonlocal callback_fired
            callback_fired = True
            # At this point, result should not yet be available
            assert not result_available, (
                "Callback fired after result returned — should be before"
            )

        async def fake_stream() -> AsyncGenerator[dict[str, Any], None]:
            yield {"type": "token", "content": "x"}
            yield {
                "type": "complete",
                "content": "x",
                "tool_calls": [],
                "usage": {},
                "provider": "openai",
                "model": "gpt-4.1",
            }

        mock_router = MagicMock()
        mock_router.complete_stream = AsyncMock(return_value=fake_stream())
        agent_mod._router = mock_router

        result = await agent_mod.invoke_llm_stream(
            "openai/gpt-4.1",
            [{"role": "user", "content": "hi"}],
            token_callback=cb,
        )
        result_available = True

        assert callback_fired, "Callback should have been called"
        assert result.content == "x"
