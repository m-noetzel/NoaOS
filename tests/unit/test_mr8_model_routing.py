"""Tests for MR8: Per-Node Model Routing.

Each LangGraph node can specify its preferred model via ModelConfig,
cutting token costs by using cheaper/no models where appropriate.

Deliverables tested:
1. ModelConfig dataclass with per-node defaults
2. AgentState gets model_config field
3. router_node returns model_config in state update
4. agent_node reads model_config["agent"] with fallback
5. Default config: router=none, agent=anthropic/claude-sonnet-4-20250514, responder=none
6. Private mode: agent=ollama/llama3.1
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.mr8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user_message(content: str = "Hello Noa") -> dict[str, Any]:
    return {"role": "user", "content": content}


def _make_agent_state(
    *,
    messages: list[dict[str, Any]] | None = None,
    privacy_mode: str = "external",
    selected_model: str = "anthropic/claude-haiku",
    tool_calls: list[dict[str, Any]] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    response: str | None = None,
    total_cost: float = 0.0,
    model_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "messages": messages or [_make_user_message()],
        "privacy_mode": privacy_mode,
        "selected_model": selected_model,
        "tool_calls": tool_calls or [],
        "tool_results": tool_results or [],
        "response": response,
        "total_cost": total_cost,
    }
    if model_config is not None:
        state["model_config"] = model_config
    return state


# ===========================================================================
# 1. ModelConfig dataclass defaults
# ===========================================================================

class TestModelConfigDefaults:
    """ModelConfig must declare correct per-node defaults."""

    def test_default_external_config(self):
        """External-mode defaults: router=none, agent=sonnet, responder=none."""
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig()
        assert cfg.router == "none"
        assert cfg.agent == "anthropic/claude-sonnet-4-20250514"
        assert cfg.responder == "none"

    def test_private_mode_config(self):
        """Private mode must use ollama/llama3.1 for agent."""
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig.for_privacy_mode("private")
        assert cfg.agent == "ollama/llama3.1"

    def test_external_mode_config(self):
        """External mode must use anthropic/claude-sonnet-4-20250514 for agent."""
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig.for_privacy_mode("external")
        assert cfg.agent == "anthropic/claude-sonnet-4-20250514"

    def test_to_dict(self):
        """ModelConfig.to_dict() returns a plain dict suitable for AgentState."""
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig()
        d = cfg.to_dict()
        assert isinstance(d, dict)
        assert d == {
            "router": "none",
            "agent": "anthropic/claude-sonnet-4-20250514",
            "responder": "none",
        }

    def test_router_and_responder_always_none(self):
        """Router and responder models should be 'none' (no LLM cost)."""
        from noa.orchestrator.model_config import ModelConfig

        for mode in ("private", "external"):
            cfg = ModelConfig.for_privacy_mode(mode)
            assert cfg.router == "none", f"router should be none in {mode} mode"
            assert cfg.responder == "none", f"responder should be none in {mode} mode"


# ===========================================================================
# 2. AgentState has model_config field
# ===========================================================================

class TestAgentStateModelConfig:
    """AgentState TypedDict must include model_config."""

    def test_state_has_model_config_annotation(self):
        from noa.orchestrator.state import AgentState

        annotations = AgentState.__annotations__
        assert "model_config" in annotations, (
            "AgentState must have model_config field"
        )


# ===========================================================================
# 3. router_node returns model_config
# ===========================================================================

class TestRouterNodeModelConfig:
    """router_node must include model_config in its state update."""

    def test_router_returns_model_config_external(self):
        """Router state update must include model_config for external mode."""
        from noa.orchestrator.nodes.router import router_node

        state = _make_agent_state(
            messages=[_make_user_message("What is the weather?")],
        )
        result = router_node(state)
        assert "model_config" in result, "router must return model_config"
        mc = result["model_config"]
        assert mc["agent"] == "anthropic/claude-sonnet-4-20250514"
        assert mc["router"] == "none"
        assert mc["responder"] == "none"

    def test_router_returns_model_config_private(self):
        """Router state update must include model_config for private mode."""
        from noa.orchestrator.nodes.router import router_node

        state = _make_agent_state(
            messages=[_make_user_message("Show me my private journal")],
        )
        result = router_node(state)
        assert result["privacy_mode"] == "private"
        assert "model_config" in result
        mc = result["model_config"]
        assert mc["agent"] == "ollama/llama3.1"


# ===========================================================================
# 4. agent_node reads model_config["agent"]
# ===========================================================================

class TestAgentNodeModelConfig:
    """agent_node must prefer model_config['agent'] over selected_model."""

    def test_agent_uses_model_config_when_present(self):
        """When model_config is in state, agent_node uses model_config['agent']."""
        from noa.orchestrator.nodes.agent import LLMResponse, agent_node

        mock_response = LLMResponse(content="OK", tool_calls=[])
        state = _make_agent_state(
            selected_model="anthropic/claude-haiku",
            model_config={
                "router": "none",
                "agent": "anthropic/claude-sonnet-4-20250514",
                "responder": "none",
            },
        )

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm",
            return_value=mock_response,
        ) as mock_llm:
            asyncio.run(agent_node(state))
            # The model passed to invoke_llm should be from model_config
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            assert call_args[0][0] == "anthropic/claude-sonnet-4-20250514"

    def test_agent_falls_back_to_selected_model(self):
        """When model_config is absent, agent_node falls back to selected_model."""
        from noa.orchestrator.nodes.agent import LLMResponse, agent_node

        mock_response = LLMResponse(content="OK", tool_calls=[])
        state = _make_agent_state(
            selected_model="anthropic/claude-haiku",
            # No model_config
        )

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm",
            return_value=mock_response,
        ) as mock_llm:
            asyncio.run(agent_node(state))
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            assert call_args[0][0] == "anthropic/claude-haiku"


# ===========================================================================
# 5. ModelConfig.from_settings reads user preferences
# ===========================================================================

class TestModelConfigFromSettings:
    """ModelConfig.from_settings creates config from user overrides."""

    def test_from_settings_overrides_agent(self):
        """User can override the agent model via settings dict."""
        from noa.orchestrator.model_config import ModelConfig

        settings = {"agent": "openai/gpt-4o"}
        cfg = ModelConfig.from_settings(settings)
        assert cfg.agent == "openai/gpt-4o"
        # Non-overridden fields keep defaults
        assert cfg.router == "none"
        assert cfg.responder == "none"

    def test_from_settings_empty_uses_defaults(self):
        """Empty settings dict returns default ModelConfig."""
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig.from_settings({})
        assert cfg.agent == "anthropic/claude-sonnet-4-20250514"


# ===========================================================================
# 6. Per-node model override via ChatRequest
# ===========================================================================

class TestPerNodeOverride:
    """Per-node model can be overridden at request time."""

    def test_model_config_override_via_state(self):
        """A model_config dict in state overrides the default for agent_node."""
        from noa.orchestrator.nodes.agent import LLMResponse, agent_node

        mock_response = LLMResponse(content="response", tool_calls=[])
        custom_config = {
            "router": "none",
            "agent": "openai/gpt-4o",
            "responder": "none",
        }
        state = _make_agent_state(
            model_config=custom_config,
        )

        with patch(
            "noa.orchestrator.nodes.agent.invoke_llm",
            return_value=mock_response,
        ) as mock_llm:
            asyncio.run(agent_node(state))
            call_args = mock_llm.call_args
            assert call_args[0][0] == "openai/gpt-4o"
