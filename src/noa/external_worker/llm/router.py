"""Provider routing — selects and dispatches to the correct LLM provider.

Spec refs: SPEC.md Section 14.1, Section 14.2, Section 14.3, Section 14.4
"""

from __future__ import annotations

import logging
from typing import Any

from noa.external_worker.exceptions import (
    PrivacyViolationError,
    ProviderError,
    ProviderTimeoutError,
)
from noa.types import PrivacyMode

logger = logging.getLogger(__name__)

# Re-export for convenience (tests import ProviderError from here)
__all__ = [
    "PrivacyViolationError",
    "ProviderError",
    "ProviderRouter",
    "ProviderTimeoutError",
    "build_llm_clients",
]

# Default models per provider
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4.1",
    "google_ai": "gemini-pro",
    "ollama": "llama3.1",
}

# Default Ollama model manifest
_DEFAULT_OLLAMA_MANIFEST: dict[str, str] = {
    "llama3.1": "approved",
    "mistral": "approved",
    "qwen3": "approved",
}

_EXTERNAL_PROVIDERS = {"anthropic", "openai", "google_ai"}


class ProviderRouter:
    """Route LLM requests to the appropriate provider.

    Enforces privacy invariants: private-mode requests must never be
    forwarded to an external provider.
    """

    def __init__(
        self,
        config: dict[str, Any],
        clients: dict[str, Any] | None = None,
    ) -> None:
        self._default_provider: str = config["default_provider"]
        self._providers: dict[str, Any] = config.get("providers", {})
        self._clients: dict[str, Any] = clients if clients is not None else {}

    @classmethod
    def from_settings(cls, settings: Any) -> ProviderRouter:
        """Create a ProviderRouter from a UserSettings object.

        Instantiates real LLM clients for each provider that has
        credentials configured.  Delegates client construction to
        ``build_llm_clients()`` (Phase QC8 / A2).
        """
        default = (
            getattr(settings, "default_provider", "openai")
            or "openai"
        )
        config: dict[str, Any] = {
            "default_provider": default,
            "providers": {},
        }
        clients = build_llm_clients(settings)
        return cls(config, clients=clients)

    @property
    def available_providers(self) -> list[str]:
        """Return list of available provider names."""
        return list(self._clients.keys())

    def select(
        self,
        *,
        privacy_mode: str = "external",
        user_selected: str | None = None,
    ) -> str:
        """Select a provider name based on configuration and constraints.

        Args:
            privacy_mode: ``"external"`` (default) or ``"private"``.
            user_selected: Optional explicit provider choice from the user.

        Returns:
            The provider name string.

        Raises:
            PrivacyViolationError: If *privacy_mode* is ``"private"``
                and an external provider is selected.
        """
        if privacy_mode == PrivacyMode.PRIVATE:
            if user_selected and user_selected in _EXTERNAL_PROVIDERS:
                msg = "private mode forbids routing to external providers"
                raise PrivacyViolationError(msg)
            return "ollama"

        if user_selected is not None:
            return user_selected

        return self._default_provider

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        privacy_mode: str = "external",
        provider: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dispatch a completion request to the appropriate provider.

        Args:
            messages: Conversation messages.
            max_tokens: Maximum tokens to generate.
            privacy_mode: ``"external"`` or ``"private"``.
            provider: Optional explicit provider override.
            model: Optional model override.
            tools: Optional tool definitions (provider-specific format).
            **kwargs: Provider-specific parameters (temperature, top_p, etc.).

        Returns:
            Normalized response dict with content, tool_calls, usage, provider, model.

        Raises:
            PrivacyViolationError: If privacy constraints are violated.
            ProviderError: If the selected provider is unavailable or fails.
        """
        selected = self.select(
            privacy_mode=privacy_mode, user_selected=provider,
        )

        client = self._clients.get(selected)
        if client is None:
            msg = f"Provider '{selected}' is not configured"
            raise ProviderError(msg)

        # Build provider-specific tool definitions
        provider_tools = self._format_tools(selected, tools)

        # Ollama has a different interface (model is a required param)
        if selected == "ollama":
            ollama_model = model or _DEFAULT_MODELS["ollama"]
            result: dict[str, Any] = await client.complete(
                messages=messages,
                model=ollama_model,
                max_tokens=max_tokens,
                **kwargs,
            )
            return result

        # External providers (Anthropic, OpenAI, Google AI)
        complete_kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if model:
            complete_kwargs["model"] = model
        if provider_tools:
            complete_kwargs["tools"] = provider_tools
        result = await client.complete(**complete_kwargs)
        return result

    @staticmethod
    def _format_tools(
        provider_name: str,
        registered_tools: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        """Format tool definitions for the selected provider."""
        if not registered_tools:
            return None

        if provider_name in ("anthropic", "google_ai"):
            from noa.tools.definitions import get_anthropic_tools
            tool_names = [t["name"] for t in registered_tools]
            return get_anthropic_tools(tool_names)

        if provider_name == "openai":
            from noa.tools.definitions import get_openai_tools
            tool_names = [t["name"] for t in registered_tools]
            return get_openai_tools(tool_names)

        return None


def build_llm_clients(settings: Any) -> dict[str, Any]:
    """Build a dict of LLM clients from settings.

    Returns only providers that have valid credentials configured.
    Ollama is always included as a local provider.

    Phase QC8 / A2.
    """
    clients: dict[str, Any] = {}

    # Anthropic
    anthropic_key = getattr(settings, "anthropic_api_key", None)
    if anthropic_key:
        from noa.external_worker.llm.anthropic import AnthropicClient

        clients["anthropic"] = AnthropicClient(
            api_key=anthropic_key,
            model=_DEFAULT_MODELS["anthropic"],
        )

    # OpenAI
    openai_key = getattr(settings, "openai_api_key", None)
    if openai_key:
        from noa.external_worker.llm.openai import OpenAIClient

        clients["openai"] = OpenAIClient(
            api_key=openai_key,
            model=_DEFAULT_MODELS["openai"],
        )

    # Google AI
    google_key = getattr(settings, "google_ai_api_key", None)
    if google_key:
        from noa.external_worker.llm.google_ai import GoogleAIClient

        clients["google_ai"] = GoogleAIClient(
            api_key=google_key,
            model=_DEFAULT_MODELS["google_ai"],
        )

    # Ollama (always available — local service)
    ollama_url = (
        getattr(settings, "ollama_base_url", "http://ollama:11434")
        or "http://ollama:11434"
    )
    from noa.llm.providers import OllamaClient

    clients["ollama"] = OllamaClient(
        base_url=ollama_url,
        model_manifest=_DEFAULT_OLLAMA_MANIFEST,
    )

    return clients
