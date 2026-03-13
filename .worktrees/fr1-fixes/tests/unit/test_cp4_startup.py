"""Tests for CP4: App Startup Wiring.

Verifies that the app lifespan wires ProviderRouter, ToolRegistry,
and OrchestratorRunner into app state.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")

from unittest.mock import MagicMock

from noa.api.app_state import (
    get_provider_router,
    get_runner,
    set_provider_router,
    set_runner,
)


class TestAppStateExtensions:
    """app_state has provider_router and runner getters/setters."""

    def test_set_get_provider_router(self) -> None:
        mock = MagicMock()
        set_provider_router(mock)
        assert get_provider_router() is mock
        set_provider_router(None)

    def test_set_get_runner(self) -> None:
        mock = MagicMock()
        set_runner(mock)
        assert get_runner() is mock
        set_runner(None)

    def test_provider_router_initially_none(self) -> None:
        set_provider_router(None)
        assert get_provider_router() is None

    def test_runner_initially_none(self) -> None:
        set_runner(None)
        assert get_runner() is None


class TestMissingKeys:
    """Missing LLM keys don't crash startup."""

    def test_missing_keys_no_crash(self) -> None:
        from noa.external_worker.llm.router import ProviderRouter

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.default_provider = "ollama"
        mock_settings.default_model = None

        router = ProviderRouter.from_settings(mock_settings)
        assert "ollama" in router.available_providers
        assert "anthropic" not in router.available_providers


class TestWireLLMPipeline:
    """wire_llm_pipeline builds and stores all components."""

    def test_function_exists(self) -> None:
        from noa.api.app import wire_llm_pipeline

        assert callable(wire_llm_pipeline)

    def test_sets_provider_router(self) -> None:
        from noa.api.app import wire_llm_pipeline
        from noa.orchestrator.nodes.agent import (
            get_router,
            set_router,
        )

        # Reset
        set_provider_router(None)
        set_runner(None)
        set_router(None)

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.default_provider = "ollama"
        mock_settings.default_model = None

        wire_llm_pipeline(mock_settings)

        assert get_provider_router() is not None
        assert get_runner() is not None
        assert get_router() is not None

        # Cleanup
        set_provider_router(None)
        set_runner(None)
        set_router(None)

    def test_provider_router_has_ollama(self) -> None:
        from noa.api.app import wire_llm_pipeline

        set_provider_router(None)
        set_runner(None)

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.default_provider = "ollama"
        mock_settings.default_model = None

        wire_llm_pipeline(mock_settings)

        router = get_provider_router()
        assert "ollama" in router.available_providers

        # Cleanup
        set_provider_router(None)
        set_runner(None)

    def test_runner_is_orchestrator_runner(self) -> None:
        from noa.api.app import wire_llm_pipeline
        from noa.orchestrator.runner import OrchestratorRunner

        set_provider_router(None)
        set_runner(None)

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.google_api_key = None
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.default_provider = "ollama"
        mock_settings.default_model = None

        wire_llm_pipeline(mock_settings)

        runner = get_runner()
        assert isinstance(runner, OrchestratorRunner)

        # Cleanup
        set_provider_router(None)
        set_runner(None)
