"""Regression tests for temperature wiring (ADHOC-M1).

Verifies that temperature flows through the entire call stack:
  ChatRequest.temperature → agent_node state → invoke_llm/invoke_llm_stream
  → ProviderRouter.complete() → provider client build_request()

Tests guard against silent refactor breakage of the temperature parameter.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_MESSAGES = [{"role": "user", "content": "hello"}]

_LLM_RESPONSE = {
    "content": "Hi there!",
    "tool_calls": [],
    "usage": {"input_tokens": 5, "output_tokens": 10},
    "provider": "ollama",
    "model": "llama3.1",
}


def _make_router(complete_return: dict[str, Any] | None = None) -> MagicMock:
    """Return a mock ProviderRouter with a pre-configured AsyncMock complete()."""
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=complete_return or _LLM_RESPONSE)
    mock_router.complete_stream = AsyncMock()
    return mock_router


# ---------------------------------------------------------------------------
# OllamaClient.build_request — temperature in request body
# ---------------------------------------------------------------------------

class TestOllamaTemperatureInRequestBody:
    """OllamaClient.build_request wires temperature into options.temperature."""

    def test_temperature_passed_to_ollama_client(self) -> None:
        """When temperature is set, it appears in options.temperature."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(base_url="http://ollama:11434")
        request = client.build_request(
            messages=_BASE_MESSAGES,
            model="llama3.1",
            max_tokens=256,
            temperature=0.7,
        )

        assert "options" in request
        assert request["options"]["temperature"] == 0.7

    def test_temperature_omitted_from_ollama_when_none(self) -> None:
        """When temperature is None, the key must NOT appear in options.

        This validates the ADHOC-M2 fix: None temperature must not be sent
        as null/0 to Ollama, which would override its own default sampling.
        """
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(base_url="http://ollama:11434")
        request = client.build_request(
            messages=_BASE_MESSAGES,
            model="llama3.1",
            max_tokens=256,
            temperature=None,
        )

        assert "options" in request
        assert "temperature" not in request["options"], (
            "temperature must be absent when None — not sent as 0 or null"
        )

    def test_temperature_zero_is_passed(self) -> None:
        """Explicit temperature=0.0 (deterministic) must be sent to Ollama."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(base_url="http://ollama:11434")
        request = client.build_request(
            messages=_BASE_MESSAGES,
            model="llama3.1",
            max_tokens=256,
            temperature=0.0,
        )

        assert request["options"]["temperature"] == 0.0


# ---------------------------------------------------------------------------
# AnthropicClient.build_request — temperature in request body
# ---------------------------------------------------------------------------

class TestAnthropicTemperatureInRequestBody:
    """AnthropicClient.build_request wires temperature into the request."""

    def test_temperature_passed_to_anthropic_client(self) -> None:
        """When temperature is set, it appears at the request top level."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key", model="claude-haiku")
        request = client.build_request(
            messages=_BASE_MESSAGES,
            max_tokens=256,
            temperature=0.5,
        )

        assert request["temperature"] == 0.5

    def test_temperature_omitted_from_anthropic_when_none(self) -> None:
        """When temperature is None, the key must NOT appear in the request."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key", model="claude-haiku")
        request = client.build_request(
            messages=_BASE_MESSAGES,
            max_tokens=256,
            temperature=None,
        )

        assert "temperature" not in request


# ---------------------------------------------------------------------------
# invoke_llm — temperature forwarded to ProviderRouter.complete()
# ---------------------------------------------------------------------------

class TestInvokeLLMTemperatureForwarding:
    """invoke_llm passes temperature through to ProviderRouter.complete()."""

    def test_temperature_forwarded_to_router_complete(self) -> None:
        """invoke_llm with temperature=0.8 must call router.complete with temperature=0.8."""
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = _make_router()
        set_router(mock_router)
        try:
            asyncio.get_event_loop().run_until_complete(
                invoke_llm(
                    "ollama/llama3.1",
                    _BASE_MESSAGES,
                    temperature=0.8,
                )
            )
        finally:
            set_router(None)  # type: ignore[arg-type]

        call_kwargs = mock_router.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.8

    def test_temperature_none_not_forwarded_to_router(self) -> None:
        """invoke_llm with temperature=None must NOT pass temperature kwarg to router."""
        from noa.orchestrator.nodes.agent import invoke_llm, set_router

        mock_router = _make_router()
        set_router(mock_router)
        try:
            asyncio.get_event_loop().run_until_complete(
                invoke_llm(
                    "ollama/llama3.1",
                    _BASE_MESSAGES,
                    temperature=None,
                )
            )
        finally:
            set_router(None)  # type: ignore[arg-type]

        call_kwargs = mock_router.complete.call_args.kwargs
        assert "temperature" not in call_kwargs, (
            "temperature=None must not be forwarded to router.complete()"
        )


# ---------------------------------------------------------------------------
# agent_node — temperature read from AgentState and passed to invoke_llm
# ---------------------------------------------------------------------------

class TestAgentNodeTemperatureInState:
    """agent_node reads temperature from AgentState and passes it to the LLM."""

    def test_temperature_in_agent_state_passed_to_router(self) -> None:
        """agent_node with state.temperature=0.6 must invoke router.complete with temperature=0.6."""
        from noa.orchestrator.nodes.agent import agent_node, set_router

        mock_router = _make_router()
        set_router(mock_router)
        try:
            state: dict[str, Any] = {
                "messages": _BASE_MESSAGES,
                "selected_model": "ollama/llama3.1",
                "temperature": 0.6,
                "available_tools": [],
            }
            asyncio.get_event_loop().run_until_complete(agent_node(state))
        finally:
            set_router(None)  # type: ignore[arg-type]

        call_kwargs = mock_router.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.6

    def test_no_temperature_in_state_omits_kwarg(self) -> None:
        """agent_node with no temperature in state must not pass temperature to router."""
        from noa.orchestrator.nodes.agent import agent_node, set_router

        mock_router = _make_router()
        set_router(mock_router)
        try:
            state: dict[str, Any] = {
                "messages": _BASE_MESSAGES,
                "selected_model": "ollama/llama3.1",
                # No temperature key
                "available_tools": [],
            }
            asyncio.get_event_loop().run_until_complete(agent_node(state))
        finally:
            set_router(None)  # type: ignore[arg-type]

        call_kwargs = mock_router.complete.call_args.kwargs
        assert "temperature" not in call_kwargs

    def test_temperature_from_state_survives_provider_routing(self) -> None:
        """Temperature set in state propagates through ProviderRouter to the provider.

        Uses a real ProviderRouter with a mocked Ollama client to verify
        the temperature kwarg reaches the provider's complete() call.
        """
        from noa.external_worker.llm.router import ProviderRouter
        from noa.orchestrator.nodes.agent import agent_node, set_router

        mock_ollama_complete = AsyncMock(return_value=_LLM_RESPONSE)
        mock_ollama = MagicMock()
        mock_ollama.complete = mock_ollama_complete

        router = ProviderRouter(
            config={"default_provider": "ollama", "providers": {}},
            clients={"ollama": mock_ollama},
        )
        set_router(router)
        try:
            state: dict[str, Any] = {
                "messages": _BASE_MESSAGES,
                "selected_model": "ollama/llama3.1",
                "temperature": 0.3,
                "available_tools": [],
            }
            asyncio.get_event_loop().run_until_complete(agent_node(state))
        finally:
            set_router(None)  # type: ignore[arg-type]

        call_kwargs = mock_ollama_complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.3, (
            "Temperature must survive the full path: agent_node → router → ollama client"
        )
