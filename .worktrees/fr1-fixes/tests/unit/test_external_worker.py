"""Tests for External Worker Skeleton -- Phase DW2.

Spec refs: SPEC.md Section 8.2, Section 6.2, Section 14.1
Phase plan: MASTER_PLAN.md Phase DW2

Tests cover: provider routing (config-based + user selection), private mode
isolation, LLM client request formatting (Anthropic, OpenAI), per-provider
parameter configuration, tool registry/dispatch, external worker FastAPI app,
health endpoint, JSON-only responses, and error handling (retry, timeout).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.dw2


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _provider_config(
    *,
    default_provider: str = "anthropic",
    anthropic_api_key: str = "sk-test-anthropic",
    openai_api_key: str = "sk-test-openai",
    anthropic_model: str = "claude-sonnet-4-20250514",
    openai_model: str = "gpt-4o",
) -> dict[str, Any]:
    """Create a minimal provider configuration dict."""
    return {
        "default_provider": default_provider,
        "providers": {
            "anthropic": {
                "api_key": anthropic_api_key,
                "model": anthropic_model,
            },
            "openai": {
                "api_key": openai_api_key,
                "model": openai_model,
            },
        },
    }


# ===========================================================================
# 1. Provider Routing (SPEC.md Section 14.1, Section 14.2)
# ===========================================================================

class TestProviderRouting:
    """Provider router selects the correct LLM provider per Section 14.1."""

    def test_default_provider_selected(self):
        """When no explicit choice, the configured default provider is used."""
        from noa.external_worker.llm.router import ProviderRouter

        config = _provider_config(default_provider="anthropic")
        router = ProviderRouter(config)
        provider = router.select(privacy_mode="external")
        assert provider == "anthropic"

    def test_user_selected_provider_overrides_default(self):
        """User-explicit provider selection overrides the default (Section 14.2 rule 2)."""
        from noa.external_worker.llm.router import ProviderRouter

        config = _provider_config(default_provider="anthropic")
        router = ProviderRouter(config)
        provider = router.select(
            privacy_mode="external", user_selected="openai",
        )
        assert provider == "openai"

    def test_private_mode_routes_to_ollama(self):
        """Private mode MUST route to Ollama only (Section 14.2 rule 1).

        This is a hard security invariant: if privacy_mode is 'private',
        the router must always select the local Ollama provider.
        """
        from noa.external_worker.llm.router import ProviderRouter

        config = _provider_config(default_provider="anthropic")
        router = ProviderRouter(config)
        assert router.select(privacy_mode="private") == "ollama"

    def test_private_mode_rejects_external_override(self):
        """Private mode rejects explicit selection of external provider."""
        from noa.external_worker.exceptions import PrivacyViolationError
        from noa.external_worker.llm.router import ProviderRouter

        config = _provider_config(default_provider="anthropic")
        router = ProviderRouter(config)
        with pytest.raises(PrivacyViolationError, match="private"):
            router.select(privacy_mode="private", user_selected="anthropic")

    def test_default_provider_configurable(self):
        """Default provider can be set to OpenAI instead of Anthropic."""
        from noa.external_worker.llm.router import ProviderRouter

        config = _provider_config(default_provider="openai")
        router = ProviderRouter(config)
        provider = router.select(privacy_mode="external")
        assert provider == "openai"


# ===========================================================================
# 2. LLM Clients (SPEC.md Section 14.1, Section 14.4)
# ===========================================================================

class TestAnthropicClient:
    """Anthropic LLM client formats requests correctly."""

    def test_request_has_required_fields(self):
        """Anthropic requests include model, messages, and max_tokens."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(
            api_key="sk-test", model="claude-sonnet-4-20250514",
        )
        request = client.build_request(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
        )
        assert request["model"] == "claude-sonnet-4-20250514"
        assert request["messages"] == [{"role": "user", "content": "Hello"}]
        assert request["max_tokens"] == 1024

    def test_temperature_configurable(self):
        """Temperature is configurable per request (Section 14.4)."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(
            api_key="sk-test", model="claude-sonnet-4-20250514",
        )
        request = client.build_request(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
            temperature=0.7,
        )
        assert request["temperature"] == 0.7


class TestOpenAIClient:
    """OpenAI LLM client formats requests correctly."""

    def test_request_has_required_fields(self):
        """OpenAI requests include model, messages, and max_tokens."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")
        request = client.build_request(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
        )
        assert request["model"] == "gpt-4o"
        assert request["messages"] == [{"role": "user", "content": "Hello"}]
        assert request["max_tokens"] == 1024

    def test_top_p_configurable(self):
        """top_p is configurable per request (Section 14.4)."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")
        request = client.build_request(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
            top_p=0.9,
        )
        assert request["top_p"] == 0.9


# ===========================================================================
# 3. Tool Registry (SPEC.md Section 6.2 Domain B capabilities)
# ===========================================================================

class TestToolRegistry:
    """Tool registry manages external domain tools."""

    def test_register_and_discover_tool(self):
        """Registered tools are discoverable by name."""
        from noa.external_worker.tools import ToolRegistry

        registry = ToolRegistry()

        def dummy_handler(args: dict[str, Any]) -> dict[str, Any]:
            return {"result": "ok"}

        registry.register("web_search", dummy_handler)
        assert registry.has("web_search")
        assert "web_search" in registry.list_tools()

    def test_dispatch_routes_to_correct_handler(self):
        """Tool dispatch routes a call to the registered handler."""
        from noa.external_worker.tools import ToolRegistry

        registry = ToolRegistry()
        call_log: list[str] = []

        def handler_a(args: dict[str, Any]) -> dict[str, Any]:
            call_log.append("a")
            return {"tool": "a"}

        def handler_b(args: dict[str, Any]) -> dict[str, Any]:
            call_log.append("b")
            return {"tool": "b"}

        registry.register("tool_a", handler_a)
        registry.register("tool_b", handler_b)

        result = registry.dispatch("tool_b", {"query": "test"})
        assert result == {"tool": "b"}
        assert call_log == ["b"]

    def test_unregistered_tool_rejected(self):
        """Calling an unregistered tool raises an error."""
        from noa.external_worker.tools import ToolRegistry

        registry = ToolRegistry()
        with pytest.raises(KeyError, match="not_registered"):
            registry.dispatch("not_registered", {})


# ===========================================================================
# 4. Worker App (SPEC.md Section 8.2)
# ===========================================================================

class TestExternalWorkerApp:
    """External worker FastAPI application."""

    def test_app_creates_successfully(self):
        """External worker FastAPI app instantiates without error."""
        from noa.external_worker.app import create_external_app

        app = create_external_app()
        assert app is not None

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_status(self):
        """Health endpoint returns ok status (Section 8.2 structured outputs)."""
        import httpx

        from noa.external_worker.app import create_external_app

        app = create_external_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_json_only_responses(self):
        """All responses are JSON (Section 8.2: produce structured outputs)."""
        import httpx

        from noa.external_worker.app import create_external_app

        app = create_external_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/health")
            assert resp.headers["content-type"].startswith("application/json")


# ===========================================================================
# 5. Error Handling (provider failures, timeouts)
# ===========================================================================

class TestErrorHandling:
    """Provider failure handling -- graceful retry and timeout."""

    @pytest.mark.asyncio
    async def test_provider_failure_raises_provider_error(self):
        """When the upstream LLM API fails, a ProviderError is raised."""
        from noa.external_worker.llm.anthropic import AnthropicClient
        from noa.external_worker.llm.router import ProviderError

        client = AnthropicClient(
            api_key="sk-test", model="claude-sonnet-4-20250514",
        )
        # Mock the HTTP call to simulate a 500 from the provider
        with patch.object(
            client, "_send_request",
            new_callable=AsyncMock,
            side_effect=ProviderError("upstream 500"),
        ), pytest.raises(ProviderError):
            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

    @pytest.mark.asyncio
    async def test_timeout_handled(self):
        """Request timeout is caught and wrapped as ProviderError."""
        import httpx

        from noa.external_worker.llm.anthropic import AnthropicClient
        from noa.external_worker.llm.router import ProviderError

        client = AnthropicClient(
            api_key="sk-test", model="claude-sonnet-4-20250514",
        )
        with patch.object(
            client, "_send_request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ), pytest.raises(ProviderError, match="[Tt]imeout"):
            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
