"""Anthropic LLM client for the external worker.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

from typing import Any

from noa.external_worker.exceptions import ProviderError


class AnthropicClient:
    """Client for the Anthropic Messages API."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def build_request(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Build a request payload for the Anthropic Messages API.

        Returns:
            Dict with model, messages, max_tokens, and optional temperature.
        """
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            request["temperature"] = temperature
        return request

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the Anthropic API (placeholder)."""
        raise NotImplementedError  # pragma: no cover

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to Anthropic.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            return await self._send_request(request)
        except TimeoutError as exc:
            msg = "Timeout calling Anthropic API"
            raise ProviderError(msg) from exc
