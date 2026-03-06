"""Tests for ProviderRouter dispatch hub — Phase LP5.

Spec refs: SPEC.md §14.2, §14.3, §14.4
Phase plan: MASTER_PLAN.md Phase LP5

Tests cover: from_settings factory, async complete() dispatch,
privacy enforcement (private→Ollama only), user provider override,
normalized response format.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.lp5, pytest.mark.asyncio]


def _mock_settings(
    *,
    anthropic_api_key: str | None = "sk-ant-test",
    openai_api_key: str | None = "sk-openai-test",
    google_api_key: str | None = None,
    ollama_base_url: str = "http://ollama:11434",
    default_provider: str = "anthropic",
    default_model: str = "claude-sonnet-4-20250514",
) -> MagicMock:
    """Create a mock settings object matching UserSettings fields."""
    settings = MagicMock()
    settings.anthropic_api_key = anthropic_api_key
    settings.openai_api_key = openai_api_key
    settings.google_api_key = google_api_key
    settings.ollama_base_url = ollama_base_url
    settings.default_provider = default_provider
    settings.default_model = default_model
    return settings


def _normalized_response(
    content: str = "Hello!",
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    return {
        "content": content,
        "tool_calls": [],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "provider": provider,
        "model": model,
    }


# ===========================================================================
# 1. from_settings factory
# ===========================================================================


class TestFromSettings:
    def test_creates_anthropic_client_when_key_present(self):
        """from_settings creates router with Anthropic client when API key set."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(anthropic_api_key="sk-ant-test")
        router = ProviderRouter.from_settings(settings)
        assert "anthropic" in router.available_providers

    def test_creates_openai_client_when_key_present(self):
        """from_settings creates router with OpenAI client when API key set."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(openai_api_key="sk-openai-test")
        router = ProviderRouter.from_settings(settings)
        assert "openai" in router.available_providers

    def test_creates_google_ai_client_when_key_present(self):
        """from_settings creates router with Google AI client when API key set."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(google_api_key="AIza-test-key")
        router = ProviderRouter.from_settings(settings)
        assert "google_ai" in router.available_providers

    def test_creates_ollama_client_from_base_url(self):
        """from_settings creates Ollama client from base_url setting."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(ollama_base_url="http://my-ollama:11434")
        router = ProviderRouter.from_settings(settings)
        assert "ollama" in router.available_providers


# ===========================================================================
# 2. Dispatch
# ===========================================================================


class TestDispatch:
    async def test_complete_dispatches_to_correct_provider(self):
        """complete() dispatches to the correct provider client."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(default_provider="anthropic")
        router = ProviderRouter.from_settings(settings)

        mock_response = _normalized_response(provider="anthropic")
        with patch.object(
            router._clients["anthropic"],
            "complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            assert result["provider"] == "anthropic"

    async def test_complete_with_user_selected_provider(self):
        """complete() with user-selected provider overrides default."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(default_provider="anthropic")
        router = ProviderRouter.from_settings(settings)

        mock_response = _normalized_response(provider="openai", model="gpt-4o")
        with patch.object(
            router._clients["openai"],
            "complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
                provider="openai",
            )
            assert result["provider"] == "openai"


# ===========================================================================
# 3. Privacy enforcement
# ===========================================================================


class TestPrivacyEnforcement:
    async def test_private_mode_routes_to_ollama(self):
        """complete() with privacy_mode='private' routes to Ollama only."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings()
        router = ProviderRouter.from_settings(settings)

        mock_response = _normalized_response(provider="ollama", model="llama3.1")
        with patch.object(
            router._clients["ollama"],
            "complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
                privacy_mode="private",
                model="llama3.1",
            )
            assert result["provider"] == "ollama"

    async def test_private_mode_with_external_provider_raises(self):
        """complete() with privacy_mode='private' + external provider raises PrivacyViolationError."""
        from noa.external_worker.exceptions import PrivacyViolationError
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings()
        router = ProviderRouter.from_settings(settings)

        with pytest.raises(PrivacyViolationError):
            await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
                privacy_mode="private",
                provider="anthropic",
            )


# ===========================================================================
# 4. Normalized response
# ===========================================================================


class TestNormalizedResponse:
    async def test_response_includes_all_fields(self):
        """Response includes content, tool_calls, usage, provider, model."""
        from noa.external_worker.llm.router import ProviderRouter

        settings = _mock_settings(default_provider="anthropic")
        router = ProviderRouter.from_settings(settings)

        mock_response = _normalized_response()
        with patch.object(
            router._clients["anthropic"],
            "complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            assert "content" in result
            assert "tool_calls" in result
            assert "usage" in result
            assert "input_tokens" in result["usage"]
            assert "output_tokens" in result["usage"]
            assert "provider" in result
            assert "model" in result
