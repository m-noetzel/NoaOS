"""Ollama client for local LLM inference per SPEC.md §8.1.

Uses /api/chat (chat-style) for message-based completions.
Canonical location: noa.llm.providers (domain-neutral, per C2).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from noa.llm.exceptions import ProviderError

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 120.0  # Local models can be slow


class OllamaClient:
    """Client for interacting with a local Ollama instance."""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model_manifest: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_manifest = model_manifest or {}

    def is_model_approved(self, model_name: str) -> bool:
        """Check whether a model name is in the approved manifest per §8.1."""
        return model_name in self.model_manifest

    def build_request(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Build the request body for an Ollama /api/chat call."""
        return {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

    async def _send_request(self, request: dict[str, Any]) -> httpx.Response:
        """Send a request to the Ollama /api/chat endpoint."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            return await client.post("/api/chat", json=request)

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse an Ollama API response into normalized format."""
        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = body.get("error", "")
            except (ValueError, KeyError):
                detail = response.text
            msg = f"Ollama API error {response.status_code}: {detail}"
            raise ProviderError(msg)

        body = response.json()
        message = body.get("message", {})
        content = message.get("content", "")

        return {
            "content": content,
            "tool_calls": [],
            "usage": {
                "input_tokens": body.get("prompt_eval_count", 0),
                "output_tokens": body.get("eval_count", 0),
            },
            "provider": "ollama",
            "model": body.get("model", ""),
        }

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Send a completion request to Ollama.

        Returns normalized response dict with content, tool_calls, usage.

        Raises:
            ProviderError: If model not approved, connection fails, or timeout.
        """
        if not self.is_model_approved(model):
            msg = f"Model '{model}' is not approved in the manifest"
            raise ProviderError(msg)

        request = self.build_request(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            response = await self._send_request(request)
        except httpx.ConnectError as exc:
            msg = "Ollama unavailable: connection refused"
            raise ProviderError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = "Timeout calling Ollama API"
            raise ProviderError(msg) from exc
        return self._parse_response(response)
