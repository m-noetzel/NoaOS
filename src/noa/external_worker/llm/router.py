"""Provider routing -- selects the correct LLM provider per configuration.

Spec refs: SPEC.md Section 14.1, Section 14.2
"""

from __future__ import annotations

from typing import Any

from noa.external_worker.exceptions import ProviderError, ProviderTimeoutError

# Re-export for convenience (tests import ProviderError from here)
__all__ = ["ProviderError", "ProviderRouter", "ProviderTimeoutError"]


class ProviderRouter:
    """Route LLM requests to the appropriate provider.

    Enforces privacy invariants: private-mode requests must never be
    forwarded to an external provider.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._default_provider: str = config["default_provider"]
        self._providers: dict[str, Any] = config.get("providers", {})

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
            ValueError: If *privacy_mode* is ``"private"`` -- external
                providers must never handle private data.
        """
        if privacy_mode == "private":
            msg = (
                "private mode forbids routing to external providers"
            )
            raise ValueError(msg)

        if user_selected is not None:
            return user_selected

        return self._default_provider
