"""Tests for CP1: Wire invoke_llm to ProviderRouter.

Verifies that invoke_llm calls ProviderRouter.complete() and that
agent_node works as an async function with real LLM responses.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSetGetRouter:
    """set_router / get_router stores and retrieves ProviderRouter."""

    def test_set_and_get_router(self) -> None:
        from noa.orchestrator.nodes.agent import get_router, set_router

        mock_router = MagicMock()
        set_router(mock_router)
        assert get_router() is mock_router
        set_router(None)  # type: ignore[arg-type]

    def test_get_router_returns_none_initially(self) -> None:
        from noa.orchestrator.nodes.agent import get_router, set_router

        set_router(None)  # type: ignore[arg-type]
        assert get_router() is None


class TestInvokeLLM:
    """invoke_llm calls ProviderRouter.complete() correctly."""

    def test_raises_when_no_router(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        set_router(None)  # type: ignore[arg-type]
        msgs = [{"role": "user", "content": "hi"}]
        with pytest.raises(RuntimeError, match="no router configured"):
            asyncio.get_event_loop().run_until_complete(
                invoke_llm("anthropic/claude-haiku", msgs)
            )

    def test_calls_router_complete(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "Hello!",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        messages = [{"role": "user", "content": "hi"}]
        asyncio.get_event_loop().run_until_complete(
            invoke_llm("anthropic/claude-haiku", messages)
        )

        mock_router.complete.assert_called_once()
        call_kwargs = mock_router.complete.call_args[1]
        assert call_kwargs["messages"] == messages
        set_router(None)  # type: ignore[arg-type]

    def test_returns_llm_response_with_content(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "Hello world!",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        msgs = [{"role": "user", "content": "hi"}]
        result = asyncio.get_event_loop().run_until_complete(
            invoke_llm("anthropic/claude-haiku", msgs)
        )
        assert result.content == "Hello world!"
        assert result.tool_calls == []
        set_router(None)  # type: ignore[arg-type]

    def test_returns_llm_response_with_tool_calls(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        tc = [
            {"id": "tc1", "name": "web_search", "input": {"q": "w"}},
        ]
        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "",
                "tool_calls": tc,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        msgs = [{"role": "user", "content": "weather?"}]
        result = asyncio.get_event_loop().run_until_complete(
            invoke_llm("anthropic/claude-haiku", msgs)
        )
        assert result.tool_calls == tc
        set_router(None)  # type: ignore[arg-type]

    def test_passes_privacy_mode(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "ok",
                "tool_calls": [],
                "usage": {"input_tokens": 5, "output_tokens": 2},
                "provider": "ollama",
                "model": "llama3.1",
            }
        )
        set_router(mock_router)

        msgs = [{"role": "user", "content": "private stuff"}]
        asyncio.get_event_loop().run_until_complete(
            invoke_llm(
                "ollama/llama3.1",
                msgs,
                privacy_mode="private",
            )
        )

        call_kwargs = mock_router.complete.call_args[1]
        assert call_kwargs["privacy_mode"] == "private"
        set_router(None)  # type: ignore[arg-type]

    def test_passes_max_tokens_default(self) -> None:
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "ok",
                "tool_calls": [],
                "usage": {"input_tokens": 5, "output_tokens": 2},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        msgs = [{"role": "user", "content": "hi"}]
        asyncio.get_event_loop().run_until_complete(
            invoke_llm("anthropic/claude-haiku", msgs)
        )

        call_kwargs = mock_router.complete.call_args[1]
        assert call_kwargs["max_tokens"] == 4096
        set_router(None)  # type: ignore[arg-type]


class TestAsyncAgentNode:
    """agent_node is async and works with LLMResponse objects."""

    def _make_state(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "messages": [{"role": "user", "content": "hello"}],
            "privacy_mode": "external",
            "selected_model": "anthropic/claude-haiku",
            "tool_calls": [],
            "tool_results": [],
            "response": None,
            "total_cost": 0.0,
        }
        base.update(overrides)
        return base

    def test_agent_node_is_async(self) -> None:
        import asyncio as aio

        from noa.orchestrator.nodes.agent import agent_node

        assert aio.iscoroutinefunction(agent_node)

    def test_returns_response_when_no_tool_calls(self) -> None:
        from noa.orchestrator.nodes.agent import agent_node, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "Hi there!",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        state = self._make_state()
        result = asyncio.get_event_loop().run_until_complete(
            agent_node(state),
        )

        assert result["response"] == "Hi there!"
        assert result["tool_calls"] == []
        set_router(None)  # type: ignore[arg-type]

    def test_returns_tool_calls_from_llm(self) -> None:
        from noa.orchestrator.nodes.agent import agent_node, set_router

        tool_calls = [
            {"id": "tc1", "name": "web_search", "input": {"q": "t"}},
            {"id": "tc2", "name": "calendar_list", "input": {}},
        ]
        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "",
                "tool_calls": tool_calls,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        state = self._make_state()
        result = asyncio.get_event_loop().run_until_complete(
            agent_node(state),
        )

        assert result["tool_calls"] == tool_calls
        assert "response" not in result
        set_router(None)  # type: ignore[arg-type]

    def test_enforces_max_tool_calls_cap(self) -> None:
        from noa.orchestrator.nodes.agent import (
            MAX_TOOL_CALLS,
            agent_node,
            set_router,
        )

        tool_calls = [
            {"id": f"tc{i}", "name": "web_search", "input": {"q": f"{i}"}}
            for i in range(MAX_TOOL_CALLS + 5)
        ]
        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "",
                "tool_calls": tool_calls,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        state = self._make_state()
        result = asyncio.get_event_loop().run_until_complete(
            agent_node(state),
        )

        assert len(result["tool_calls"]) == MAX_TOOL_CALLS
        set_router(None)  # type: ignore[arg-type]

    def test_appends_assistant_message(self) -> None:
        from noa.orchestrator.nodes.agent import agent_node, set_router

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(
            return_value={
                "content": "response text",
                "tool_calls": [],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "provider": "anthropic",
                "model": "claude-haiku",
            }
        )
        set_router(mock_router)

        state = self._make_state()
        result = asyncio.get_event_loop().run_until_complete(
            agent_node(state),
        )

        last_msg = result["messages"][-1]
        assert last_msg["role"] == "assistant"
        assert last_msg["content"] == "response text"
        set_router(None)  # type: ignore[arg-type]
