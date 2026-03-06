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

logger = logging.getLogger(__name__)

# Re-export for convenience (tests import ProviderError from here)
__all__ = [
    "PrivacyViolationError",
    "ProviderError",
    "ProviderRouter",
    "ProviderTimeoutError",
]

# Default models per provider
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
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

    def __init__(self, config: dict[str, Any]) -> None:
        self._default_provider: str = config["default_provider"]
        self._providers: dict[str, Any] = config.get("providers", {})
        self._clients: dict[str, Any] = {}

    @classmethod
    def from_settings(cls, settings: Any) -> ProviderRouter:
        """Create a ProviderRouter from a UserSettings object.

        Instantiates real LLM clients for each provider that has
        credentials configured.
        """
        default = (
            getattr(settings, "default_provider", "anthropic")
            or "anthropic"
        )
        config: dict[str, Any] = {
            "default_provider": default,
            "providers": {},
        }

        router = cls(config)

        # Anthropic
        anthropic_key = getattr(settings, "anthropic_api_key", None)
        if anthropic_key:
            from noa.external_worker.llm.anthropic import AnthropicClient

            default_model = (
                getattr(settings, "default_model", None)
                or _DEFAULT_MODELS["anthropic"]
            )
            # Use provider default if not an Anthropic model
            if not default_model.startswith("claude"):
                default_model = _DEFAULT_MODELS["anthropic"]
            router._clients["anthropic"] = AnthropicClient(
                api_key=anthropic_key,
                model=default_model,
            )

        # OpenAI
        openai_key = getattr(settings, "openai_api_key", None)
        if openai_key:
            from noa.external_worker.llm.openai import OpenAIClient

            router._clients["openai"] = OpenAIClient(
                api_key=openai_key,
                model=_DEFAULT_MODELS["openai"],
            )

        # Google AI
        google_key = getattr(settings, "google_api_key", None)
        if google_key:
            from noa.external_worker.llm.google_ai import GoogleAIClient

            router._clients["google_ai"] = GoogleAIClient(
                api_key=google_key,
                model=_DEFAULT_MODELS["google_ai"],
            )

        # Ollama (always available — local service)
        ollama_url = getattr(settings, "ollama_base_url", "http://ollama:11434") or "http://ollama:11434"
        from noa.private_worker.ollama_client import OllamaClient

        router._clients["ollama"] = OllamaClient(
            base_url=ollama_url,
            model_manifest=_DEFAULT_OLLAMA_MANIFEST,
        )

        return router

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
        if privacy_mode == "private":
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
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dispatch a completion request to the appropriate provider.

        Args:
            messages: Conversation messages.
            max_tokens: Maximum tokens to generate.
            privacy_mode: ``"external"`` or ``"private"``.
            provider: Optional explicit provider override.
            model: Optional model override.
            **kwargs: Provider-specific parameters (temperature, top_p, etc.).

        Returns:
            Normalized response dict with content, tool_calls, usage, provider, model.

        Raises:
            PrivacyViolationError: If privacy constraints are violated.
            ProviderError: If the selected provider is unavailable or fails.
        """
        selected = self.select(privacy_mode=privacy_mode, user_selected=provider)

        client = self._clients.get(selected)
        if client is None:
            msg = f"Provider '{selected}' is not configured"
            raise ProviderError(msg)

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
        result = await client.complete(
            messages=messages,
            max_tokens=max_tokens,
            **kwargs,
        )
        return result
