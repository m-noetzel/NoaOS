"""Anthropic LLM client for the external worker.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from noa.external_worker.exceptions import ProviderError

logger = logging.getLogger(__name__)

_API_BASE = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 529}
_TIMEOUT_SECONDS = 60.0


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
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a request payload for the Anthropic Messages API."""
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            request["temperature"] = temperature
        if tools:
            request["tools"] = tools
        return request

    async def _send_request(self, request: dict[str, Any]) -> httpx.Response:
        """Send a request to the Anthropic Messages API with retry."""
        async with httpx.AsyncClient(
            base_url=_API_BASE,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            last_response: httpx.Response | None = None
            for attempt in range(_MAX_RETRIES):
                response = await client.post("/v1/messages", json=request)
                if response.status_code not in _RETRY_STATUSES:
                    return response
                last_response = response
                delay = 2 ** attempt
                logger.warning(
                    "Anthropic %d (attempt %d/%d), retrying in %ds",
                    response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            # All retries exhausted — return last response for error handling
            assert last_response is not None
            return last_response

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse an Anthropic API response into normalized format."""
        if response.status_code == 401:
            msg = "Anthropic: invalid API key (401)"
            raise ProviderError(msg)

        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = body.get("error", {}).get("message", "")
            except (json.JSONDecodeError, ValueError):
                detail = response.text
            msg = f"Anthropic API error {response.status_code}: {detail}"
            raise ProviderError(msg)

        body = response.json()
        content_blocks = body.get("content", [])

        # Extract text content
        text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        content = "".join(text_parts)

        # Extract tool use blocks
        tool_calls = [
            {
                "id": b["id"],
                "name": b["name"],
                "input": b["input"],
            }
            for b in content_blocks
            if b.get("type") == "tool_use"
        ]

        usage = body.get("usage", {})

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            "provider": "anthropic",
            "model": body.get("model", self._model),
        }

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to Anthropic.

        Args:
            model: Optional model override (uses constructor default if None).
            tools: Optional Anthropic-format tool definitions.

        Returns normalized response dict with content, tool_calls, usage.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        if model:
            request["model"] = model
        try:
            response = await self._send_request(request)
        except httpx.TimeoutException as exc:
            msg = "Timeout calling Anthropic API"
            raise ProviderError(msg) from exc
        return self._parse_response(response)

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion request to Anthropic, yielding token chunks.

        Yields dicts with ``{"type": "token", "content": str}`` for each
        incremental chunk, then a final ``{"type": "complete", ...}`` with
        the full accumulated response and usage stats.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        if model:
            request["model"] = model
        request["stream"] = True

        return self._stream_request(request)

    async def _stream_request(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Internal async generator that streams from Anthropic SSE."""
        model_used = request.get("model", self._model)
        accumulated_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async with httpx.AsyncClient(
                base_url=_API_BASE,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                timeout=_TIMEOUT_SECONDS,
            ) as client, client.stream(
                "POST", "/v1/messages", json=request,
            ) as response:
                if response.status_code == 401:
                    msg = "Anthropic: invalid API key (401)"
                    raise ProviderError(msg)
                if response.status_code != 200:
                    body_text = await response.aread()
                    try:
                        body = json.loads(body_text)
                        detail = body.get("error", {}).get("message", "")
                    except (json.JSONDecodeError, ValueError):
                        detail = body_text.decode(errors="replace")
                    msg = (
                        f"Anthropic API error"
                        f" {response.status_code}: {detail}"
                    )
                    raise ProviderError(msg)

                buffer = ""
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        buffer = line[6:]
                        if buffer == "[DONE]":
                            break
                        try:
                            event_data = json.loads(buffer)
                        except json.JSONDecodeError:
                            continue
                        event_type = event_data.get("type", "")

                        if event_type == "content_block_delta":
                            delta = event_data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                chunk = delta.get("text", "")
                                if chunk:
                                    accumulated_text += chunk
                                    yield {
                                        "type": "token",
                                        "content": chunk,
                                    }

                        elif event_type == "message_start":
                            usage = (
                                event_data.get("message", {})
                                .get("usage", {})
                            )
                            input_tokens = usage.get("input_tokens", 0)

                        elif event_type == "message_delta":
                            usage = event_data.get("usage", {})
                            output_tokens = usage.get("output_tokens", 0)

                        elif event_type == "message_stop":
                            break

        except httpx.TimeoutException as exc:
            msg = "Timeout calling Anthropic API (streaming)"
            raise ProviderError(msg) from exc

        yield {
            "type": "complete",
            "content": accumulated_text,
            "tool_calls": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "provider": "anthropic",
            "model": model_used,
        }
