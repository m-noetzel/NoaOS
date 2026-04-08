"""Tests for LS1 — LLM token streaming across all providers and the runner.

Test plan:
- Happy path: each provider's complete_stream() yields token chunks then complete
- ProviderRouter.complete_stream() delegates to the right client
- invoke_llm_stream() calls token_callback for each token and returns LLMResponse
- agent.py stream callback: per-run token_callback in state (W27-FX2: module globals removed)
- OrchestratorRunner yields token_stream SSE events when tokens flow
- Non-streaming path (backward compat): streaming disabled when no callback
- Error paths: ProviderError on HTTP errors, streaming still produces error events
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — build fake SSE/NDJSON byte streams for httpx mock
# ---------------------------------------------------------------------------

def _sse_lines(*lines: str) -> bytes:
    """Build raw SSE bytes from lines (each line is a full SSE line)."""
    return "\n".join(lines).encode()


def _anthropic_sse_stream(tokens: list[str]) -> bytes:
    """Fake Anthropic SSE stream bytes for a list of token strings."""
    parts: list[str] = []
    parts.append(
        'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}'
    )
    for token in tokens:
        payload = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": token},
            }
        )
        parts.append(f"data: {payload}")
    parts.append(
        'data: {"type":"message_delta","usage":{"output_tokens":5}}'
    )
    parts.append('data: {"type":"message_stop"}')
    return "\n".join(parts).encode()


def _openai_sse_stream(tokens: list[str]) -> bytes:
    """Fake OpenAI SSE stream bytes for a list of token strings."""
    parts: list[str] = []
    for token in tokens:
        payload = json.dumps(
            {
                "choices": [{"delta": {"content": token}}],
                "model": "gpt-4.1",
            }
        )
        parts.append(f"data: {payload}")
    # Final chunk with usage
    parts.append(
        'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5}}'
    )
    parts.append("data: [DONE]")
    return "\n".join(parts).encode()


def _google_sse_stream(tokens: list[str]) -> bytes:
    """Fake Google AI SSE stream bytes for a list of token strings."""
    parts: list[str] = []
    for token in tokens:
        payload = json.dumps(
            {
                "candidates": [
                    {"content": {"parts": [{"text": token}]}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                },
            }
        )
        parts.append(f"data: {payload}")
    return "\n".join(parts).encode()


def _ollama_ndjson_stream(tokens: list[str]) -> bytes:
    """Fake Ollama NDJSON stream bytes for a list of token strings."""
    lines: list[str] = []
    for token in tokens:
        lines.append(
            json.dumps(
                {
                    "message": {"content": token},
                    "done": False,
                    "prompt_eval_count": 0,
                    "eval_count": 0,
                }
            )
        )
    # Final done chunk
    lines.append(
        json.dumps(
            {
                "message": {"content": ""},
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 5,
            }
        )
    )
    return "\n".join(lines).encode()


async def _collect_stream(
    gen: AsyncGenerator[dict[str, Any], None],
) -> list[dict[str, Any]]:
    """Drain an async generator into a list."""
    result = []
    async for item in gen:
        result.append(item)
    return result


def _make_mock_stream_response(status_code: int, content: bytes) -> Any:
    """Create a mock httpx streaming response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    async def _aiter_lines():
        for line in content.decode().split("\n"):
            yield line

    mock_resp.aiter_lines = _aiter_lines

    async def _aread():
        return content

    mock_resp.aread = _aread
    return mock_resp


def _make_mock_stream_context(status_code: int, content: bytes) -> Any:
    """Wrap a mock response in an async context manager."""
    resp = _make_mock_stream_response(status_code, content)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# AnthropicClient.complete_stream
# ---------------------------------------------------------------------------


class TestAnthropicClientStream:
    """Tests for AnthropicClient.complete_stream."""

    @pytest.mark.asyncio
    async def test_yields_tokens_then_complete(self):
        """complete_stream yields token chunks then a complete chunk."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key", model="claude-test")
        tokens = ["Hello", ", ", "world", "!"]
        raw = _anthropic_sse_stream(tokens)

        stream_cm = _make_mock_stream_context(200, raw)
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=mock_instance
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.stream.return_value = stream_cm

            gen = await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            chunks = await _collect_stream(gen)

        token_chunks = [c for c in chunks if c["type"] == "token"]
        complete_chunks = [c for c in chunks if c["type"] == "complete"]

        assert len(token_chunks) == len(tokens)
        assert [c["content"] for c in token_chunks] == tokens
        assert len(complete_chunks) == 1

        final = complete_chunks[0]
        assert final["content"] == "Hello, world!"
        assert final["provider"] == "anthropic"
        assert final["usage"]["input_tokens"] == 10
        assert final["usage"]["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_raises_provider_error_on_401(self):
        """complete_stream raises ProviderError on 401 response."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="bad-key", model="claude-test")
        stream_cm = _make_mock_stream_context(401, b"")
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=mock_instance
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.stream.return_value = stream_cm

            gen = await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            with pytest.raises(ProviderError, match="invalid API key"):
                await _collect_stream(gen)

    @pytest.mark.asyncio
    async def test_complete_still_works(self):
        """Non-streaming complete() still works after streaming is added."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key", model="claude-test")
        body = {
            "content": [{"type": "text", "text": "Hi there"}],
            "usage": {"input_tokens": 5, "output_tokens": 3},
            "model": "claude-test",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = body

        with patch.object(client, "_send_request", AsyncMock(return_value=mock_response)):
            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

        assert result["content"] == "Hi there"
        assert result["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# OpenAIClient.complete_stream
# ---------------------------------------------------------------------------


class TestOpenAIClientStream:
    """Tests for OpenAIClient.complete_stream."""

    @pytest.mark.asyncio
    async def test_yields_tokens_then_complete(self):
        """complete_stream yields token chunks then complete chunk."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="test-key", model="gpt-test")
        tokens = ["The", " sky", " is", " blue"]
        raw = _openai_sse_stream(tokens)

        stream_cm = _make_mock_stream_context(200, raw)
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=mock_instance
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.stream.return_value = stream_cm

            gen = await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            chunks = await _collect_stream(gen)

        token_chunks = [c for c in chunks if c["type"] == "token"]
        complete_chunks = [c for c in chunks if c["type"] == "complete"]

        assert [c["content"] for c in token_chunks] == tokens
        assert len(complete_chunks) == 1
        final = complete_chunks[0]
        assert final["content"] == "The sky is blue"
        assert final["provider"] == "openai"
        assert final["usage"]["input_tokens"] == 10
        assert final["usage"]["output_tokens"] == 5


# ---------------------------------------------------------------------------
# GoogleAIClient.complete_stream
# ---------------------------------------------------------------------------


class TestGoogleAIClientStream:
    """Tests for GoogleAIClient.complete_stream."""

    @pytest.mark.asyncio
    async def test_yields_tokens_then_complete(self):
        """complete_stream yields token chunks then complete chunk."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-test")
        tokens = ["Gemini", " says", " hi"]
        raw = _google_sse_stream(tokens)

        stream_cm = _make_mock_stream_context(200, raw)
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=mock_instance
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.stream.return_value = stream_cm

            gen = await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            chunks = await _collect_stream(gen)

        token_chunks = [c for c in chunks if c["type"] == "token"]
        complete_chunks = [c for c in chunks if c["type"] == "complete"]

        assert [c["content"] for c in token_chunks] == tokens
        assert len(complete_chunks) == 1
        final = complete_chunks[0]
        assert final["content"] == "Gemini says hi"
        assert final["provider"] == "google_ai"


# ---------------------------------------------------------------------------
# OllamaClient.complete_stream
# ---------------------------------------------------------------------------


class TestOllamaClientStream:
    """Tests for OllamaClient.complete_stream."""

    @pytest.mark.asyncio
    async def test_yields_tokens_then_complete(self):
        """complete_stream yields token chunks then complete chunk."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(
            base_url="http://localhost:11434",
            model_manifest={"llama3.1": "approved"},
        )
        tokens = ["Llama", " says", " hello"]
        raw = _ollama_ndjson_stream(tokens)

        stream_cm = _make_mock_stream_context(200, raw)
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_instance = MagicMock()
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=mock_instance
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.stream.return_value = stream_cm

            gen = await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                model="llama3.1",
                max_tokens=100,
            )
            chunks = await _collect_stream(gen)

        token_chunks = [c for c in chunks if c["type"] == "token"]
        complete_chunks = [c for c in chunks if c["type"] == "complete"]

        assert [c["content"] for c in token_chunks] == tokens
        assert len(complete_chunks) == 1
        final = complete_chunks[0]
        assert final["content"] == "Llama says hello"
        assert final["provider"] == "ollama"
        assert final["usage"]["input_tokens"] == 10
        assert final["usage"]["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_raises_provider_error_unapproved_model(self):
        """complete_stream raises ProviderError for unapproved models.

        The check happens synchronously before the async generator is
        created, so the error is raised at call time (not during iteration).
        """
        from noa.llm.exceptions import ProviderError
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(
            base_url="http://localhost:11434",
            model_manifest={"llama3.1": "approved"},
        )
        with pytest.raises(ProviderError, match="not approved"):
            await client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                model="evil-model",
                max_tokens=100,
            )


# ---------------------------------------------------------------------------
# agent.py — stream callback wiring
# ---------------------------------------------------------------------------


class TestAgentStreamCallback:
    """W27-FX2: set_stream_callback/get_stream_callback removed (W26-L3 dead code fix).

    These functions were module-global callbacks superseded by per-run
    token_callback in state (ST4). They were removed in W27-FX2.
    """

    def test_set_stream_callback_removed(self):
        """set_stream_callback no longer exists in agent module (W26-L3 fix)."""
        import noa.orchestrator.nodes.agent as agent_mod
        assert not hasattr(agent_mod, "set_stream_callback"), (
            "set_stream_callback should have been removed (W26-L3)"
        )

    def test_get_stream_callback_removed(self):
        """get_stream_callback no longer exists in agent module (W26-L3 fix)."""
        import noa.orchestrator.nodes.agent as agent_mod
        assert not hasattr(agent_mod, "get_stream_callback"), (
            "get_stream_callback should have been removed (W26-L3)"
        )

    def test_stream_global_removed(self):
        """_stream_callback module global no longer exists in agent module."""
        import noa.orchestrator.nodes.agent as agent_mod
        assert not hasattr(agent_mod, "_stream_callback"), (
            "_stream_callback module global should have been removed (W26-L3)"
        )


# ---------------------------------------------------------------------------
# invoke_llm_stream — integration with mock router
# ---------------------------------------------------------------------------


class TestInvokeLlmStream:
    """Tests for invoke_llm_stream() function."""

    def setup_method(self):
        """Reset router before each test."""
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    def teardown_method(self):
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    @pytest.mark.asyncio
    async def test_calls_token_callback_for_each_token(self):
        """invoke_llm_stream calls token_callback for each token."""
        import noa.orchestrator.nodes.agent as agent_mod

        tokens_received: list[str] = []

        async def token_cb(token: str) -> None:
            tokens_received.append(token)

        async def fake_stream() -> AsyncGenerator[dict[str, Any], None]:
            yield {"type": "token", "content": "Hello"}
            yield {"type": "token", "content": " world"}
            yield {
                "type": "complete",
                "content": "Hello world",
                "tool_calls": [],
                "usage": {"input_tokens": 5, "output_tokens": 2},
                "provider": "openai",
                "model": "gpt-test",
            }

        mock_router = MagicMock()
        mock_router.complete_stream = AsyncMock(return_value=fake_stream())
        agent_mod._router = mock_router

        result = await agent_mod.invoke_llm_stream(
            "openai/gpt-test",
            [{"role": "user", "content": "Hi"}],
            token_callback=token_cb,
        )

        assert tokens_received == ["Hello", " world"]
        assert result.content == "Hello world"
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_falls_back_to_non_streaming_when_no_callback(self):
        """invoke_llm_stream falls back to invoke_llm when no callback."""
        import noa.orchestrator.nodes.agent as agent_mod

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "non-streaming response",
                "tool_calls": [],
                "usage": {},
                "provider": "openai",
                "model": "gpt-test",
            }
        )
        agent_mod._router = mock_router

        result = await agent_mod.invoke_llm_stream(
            "openai/gpt-test",
            [{"role": "user", "content": "Hi"}],
            token_callback=None,  # No callback
        )

        assert result.content == "non-streaming response"
        mock_router.complete.assert_called_once()
        mock_router.complete_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_router(self):
        """invoke_llm_stream raises RuntimeError when router is not configured."""
        import noa.orchestrator.nodes.agent as agent_mod

        async def cb(token: str) -> None:
            pass

        with pytest.raises(RuntimeError, match="no router configured"):
            await agent_mod.invoke_llm_stream(
                "openai/gpt-test",
                [{"role": "user", "content": "Hi"}],
                token_callback=cb,
            )


# ---------------------------------------------------------------------------
# OrchestratorRunner — token_stream SSE events emitted
# ---------------------------------------------------------------------------


class TestRunnerTokenStreamEvents:
    """Integration test: runner yields token_stream events when agent uses streaming."""

    def setup_method(self):
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    def teardown_method(self):
        import noa.orchestrator.nodes.agent as agent_mod
        agent_mod._router = None

    @pytest.mark.asyncio
    async def test_runner_yields_token_stream_events(self):
        """Runner yields token_stream SSE events when agent streams tokens.

        This is the integration test: the runner sets up the callback,
        the mock agent node fires it, and the runner's event loop
        emits token_stream events.

        The mock graph simulates the agent node behaviour:
        1. Graph node calls the stream callback with tokens
        2. Returns a state update (response, no tool_calls)

        The runner must yield token_stream events before result_ready.
        """
        from noa.orchestrator.runner import OrchestratorRunner

        # We need to capture the runner's token queue/callback so the mock
        # graph node can fire it to simulate real streaming behaviour.

        token_cb_holder: list[Any] = [None]

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            # W27-FX2: module global removed — callback is exclusively in state
            cb = initial_state.get("token_callback")
            if cb is not None:
                token_cb_holder[0] = cb
                await cb("Hello")
                await cb(", ")
                await cb("world")

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

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        events = []
        async for event in runner.run(
            message="test",
            run_service=mock_run_service,
            run_id="test-run-id",
        ):
            events.append(event)

        event_types = [e["event_type"] for e in events]

        # token_stream events must appear before result_ready
        assert "token_stream" in event_types
        token_events = [e for e in events if e["event_type"] == "token_stream"]
        assert len(token_events) == 3
        tokens = [e["payload"]["token"] for e in token_events]
        assert tokens == ["Hello", ", ", "world"]

        result_idx = event_types.index("result_ready")
        for te in token_events:
            te_idx = events.index(te)
            assert te_idx < result_idx, (
                "token_stream events must precede result_ready"
            )

    @pytest.mark.asyncio
    async def test_runner_no_module_global_callback(self):
        """W27-FX2: Module-global callback removed; runner uses per-run state only."""
        import noa.orchestrator.nodes.agent as agent_mod
        from noa.orchestrator.runner import OrchestratorRunner

        async def mock_graph_astream(initial_state: dict) -> AsyncGenerator:
            yield {
                "agent": {
                    "response": "done",
                    "tool_calls": [],
                    "messages": [],
                    "llm_usage": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = mock_graph_astream

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        async for _ in runner.run(
            message="test",
            run_service=mock_run_service,
            run_id="test-run-id",
        ):
            pass

        # W27-FX2: module global removed; verify it does not exist
        assert not hasattr(agent_mod, "_stream_callback"), (
            "_stream_callback module global should not exist (W26-L3 fix)"
        )

    @pytest.mark.asyncio
    async def test_backward_compat_no_streaming_when_tools_active(self):
        """Non-streaming path is preserved when tools are active."""
        # Streaming is disabled when available_tools is non-empty because
        # tool calls are not supported in streaming mode.
        import noa.orchestrator.nodes.agent as agent_mod

        tokens_received: list[str] = []
        mock_router_complete_stream_called = False

        async def token_cb(t: str) -> None:
            tokens_received.append(t)

        async def fake_complete(**kwargs: Any) -> dict[str, Any]:
            return {
                "content": "tool response",
                "tool_calls": [{"name": "web_search", "id": "tc1", "input": {}}],
                "usage": {},
                "provider": "openai",
                "model": "gpt-4.1",
            }

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(side_effect=fake_complete)
        mock_router.complete_stream = AsyncMock()
        agent_mod._router = mock_router

        # W27-FX2: use per-run token_callback in state (module global removed)
        state: dict[str, Any] = {
            "messages": [{"role": "user", "content": "search for something"}],
            "selected_model": "openai/gpt-4.1",
            "privacy_mode": "external",
            "available_tools": [{"name": "web_search"}],
            "token_callback": token_cb,
            "max_tokens": 512,
            "max_tool_calls": 10,
            "temperature": None,
            "tool_calls": [],
            "tool_results": [],
            "response": None,
            "total_cost": 0.0,
            "llm_usage": [],
            "model_config": {},
            "tool_rounds": 0,
            "user_privacy_override": "external",
            "user_model_override": None,
            "user_provider_override": "openai",
            "approvals_enabled": True,
            "private_available": True,
            "user_id": "test-user",
            "tool_scope": None,
            "task_type": None,
            "timeout_seconds": 120,
            "max_retries": 3,
        }

        from noa.orchestrator.nodes.agent import agent_node
        result = await agent_node(state)

        # With tools present, complete (not complete_stream) should have been used
        mock_router.complete.assert_called_once()
        mock_router.complete_stream.assert_not_called()
        assert tokens_received == []
        # Tool calls should be present in result
        assert len(result.get("tool_calls", [])) > 0
