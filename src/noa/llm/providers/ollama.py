"""Ollama client for local LLM inference per SPEC.md §8.1.

Uses /api/chat (chat-style) for message-based completions.
Canonical location: noa.llm.providers (domain-neutral, per C2).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
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
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Build the request body for an Ollama /api/chat call."""
        options: dict[str, Any] = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        return {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
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

    async def embed(
        self,
        text: str,
        *,
        model: str = "nomic-embed-text",
    ) -> list[float]:
        """Get an embedding vector from Ollama.

        Uses the /api/embed endpoint (batch-embed API, available since Ollama 0.3).

        Args:
            text: The text to embed.
            model: The embedding model to use. Defaults to nomic-embed-text (768-dim).

        Returns:
            List of floats representing the embedding vector.

        Raises:
            ProviderError: If Ollama is unavailable, times out, or returns an error.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            ) as client:
                resp = await client.post(
                    "/api/embed",
                    json={"model": model, "input": text},
                )
        except httpx.ConnectError as exc:
            msg = "Ollama unavailable: connection refused"
            raise ProviderError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = "Timeout calling Ollama embed API"
            raise ProviderError(msg) from exc

        if resp.status_code != 200:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("error", "")
            except (ValueError, KeyError):
                detail = resp.text
            msg = f"Ollama embed API error {resp.status_code}: {detail}"
            raise ProviderError(msg)

        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings or not isinstance(embeddings, list) or not embeddings[0]:
            msg = "Ollama embed API returned empty embeddings"
            raise ProviderError(msg)
        first: list[float] = embeddings[0]
        return first

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        temperature: float | None = None,
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

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion request to Ollama using NDJSON streaming.

        Yields dicts with ``{"type": "token", "content": str}`` for each
        incremental chunk, then a final ``{"type": "complete", ...}``.

        Raises:
            ProviderError: If model not approved, connection fails, or timeout.
        """
        if not self.is_model_approved(model):
            msg = f"Model '{model}' is not approved in the manifest"
            raise ProviderError(msg)

        options: dict[str, Any] = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        request = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        return self._stream_request(request, model)

    async def _stream_request(
        self,
        request: dict[str, Any],
        model: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Internal async generator that streams NDJSON from Ollama."""
        accumulated_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=_TIMEOUT_SECONDS,
            ) as client, client.stream(
                "POST", "/api/chat", json=request,
            ) as response:
                if response.status_code != 200:
                    body_text = await response.aread()
                    try:
                        body = json.loads(body_text)
                        detail = body.get("error", "")
                    except (json.JSONDecodeError, ValueError):
                        detail = body_text.decode(errors="replace")
                    msg = f"Ollama API error {response.status_code}: {detail}"
                    raise ProviderError(msg)

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = chunk_data.get("message", {})
                    chunk = message.get("content", "")
                    if chunk:
                        accumulated_text += chunk
                        yield {"type": "token", "content": chunk}

                    # Last chunk has done=True and eval stats
                    if chunk_data.get("done"):
                        input_tokens = chunk_data.get(
                            "prompt_eval_count", 0,
                        )
                        output_tokens = chunk_data.get("eval_count", 0)
                        break

        except httpx.ConnectError as exc:
            msg = "Ollama unavailable: connection refused"
            raise ProviderError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = "Timeout calling Ollama API (streaming)"
            raise ProviderError(msg) from exc

        yield {
            "type": "complete",
            "content": accumulated_text,
            "tool_calls": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "provider": "ollama",
            "model": model,
        }
