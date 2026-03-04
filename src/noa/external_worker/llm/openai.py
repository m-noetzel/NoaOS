"""OpenAI LLM client for the external worker.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

from typing import Any

from noa.external_worker.exceptions import ProviderError


class OpenAIClient:
    """Client for the OpenAI Chat Completions API."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def build_request(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        top_p: float | None = None,
    ) -> dict[str, Any]:
        """Build a request payload for the OpenAI Chat Completions API.

        Returns:
            Dict with model, messages, max_tokens, and optional top_p.
        """
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if top_p is not None:
            request["top_p"] = top_p
        return request

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the OpenAI API (placeholder)."""
        raise NotImplementedError  # pragma: no cover

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        top_p: float | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to OpenAI.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        try:
            return await self._send_request(request)
        except TimeoutError as exc:
            msg = "Timeout calling OpenAI API"
            raise ProviderError(msg) from exc
