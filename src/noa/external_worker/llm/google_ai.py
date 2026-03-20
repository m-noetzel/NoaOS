"""Google AI (Gemini) LLM client for the external worker.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from noa.external_worker.exceptions import ProviderError

logger = logging.getLogger(__name__)

_API_BASE = "https://generativelanguage.googleapis.com"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429}
_TIMEOUT_SECONDS = 60.0

_ROLE_MAP = {"assistant": "model", "user": "user"}


class GoogleAIClient:
    """Client for the Google AI (Gemini) generateContent API."""

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
        """Build a request payload for the Gemini generateContent API.

        Maps OpenAI-style messages to Gemini contents format:
        - role 'assistant' → 'model'
        - role 'user' → 'user'
        """
        contents = []
        for msg in messages:
            role = _ROLE_MAP.get(msg["role"], msg["role"])
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        request: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
            },
        }
        if temperature is not None:
            request["generationConfig"]["temperature"] = temperature
        return request

    async def _send_request(self, request: dict[str, Any]) -> httpx.Response:
        """Send a request to the Gemini generateContent API with retry on 429."""
        url = f"/v1beta/models/{self._model}:generateContent"
        async with httpx.AsyncClient(
            base_url=_API_BASE,
            headers={"Content-Type": "application/json"},
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            last_response: httpx.Response | None = None
            for attempt in range(_MAX_RETRIES):
                response = await client.post(
                    url,
                    json=request,
                    params={"key": self._api_key},
                )
                if response.status_code not in _RETRY_STATUSES:
                    return response
                last_response = response
                delay = 2 ** attempt
                logger.warning(
                    "Google AI %d (attempt %d/%d), retrying in %ds",
                    response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            assert last_response is not None
            return last_response

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse a Gemini API response into normalized format."""
        if response.status_code == 403:
            msg = "Google AI: invalid API key (403)"
            raise ProviderError(msg)

        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = body.get("error", {}).get("message", "")
            except (ValueError, KeyError, AttributeError):
                detail = response.text
            msg = f"Google AI API error {response.status_code}: {detail}"
            raise ProviderError(msg)

        body = response.json()
        candidate = body["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])

        # Extract text content
        text_parts = [p["text"] for p in parts if "text" in p]
        content = "".join(text_parts)

        # Extract function calls
        tool_calls = []
        for p in parts:
            if "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append({
                    "id": uuid.uuid4().hex,
                    "name": fc["name"],
                    "input": fc.get("args", {}),
                })

        usage_meta = body.get("usageMetadata", {})

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": usage_meta.get("promptTokenCount", 0),
                "output_tokens": usage_meta.get("candidatesTokenCount", 0),
            },
            "provider": "google_ai",
            "model": self._model,
        }

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to Google AI (Gemini).

        Returns normalized response dict with content, tool_calls, usage.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            response = await self._send_request(request)
        except httpx.TimeoutException as exc:
            msg = "Timeout calling Google AI API"
            raise ProviderError(msg) from exc
        return self._parse_response(response)

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion request to Google AI (Gemini).

        Uses the ``streamGenerateContent`` endpoint with SSE output.
        Yields dicts with ``{"type": "token", "content": str}`` for each
        incremental chunk, then a final ``{"type": "complete", ...}``.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._stream_request(request)

    async def _stream_request(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Internal async generator that streams from Gemini SSE."""
        url = f"/v1beta/models/{self._model}:streamGenerateContent"
        accumulated_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async with httpx.AsyncClient(
                base_url=_API_BASE,
                headers={"Content-Type": "application/json"},
                timeout=_TIMEOUT_SECONDS,
            ) as client, client.stream(
                "POST",
                url,
                json=request,
                params={"key": self._api_key, "alt": "sse"},
            ) as response:
                if response.status_code == 403:
                    msg = "Google AI: invalid API key (403)"
                    raise ProviderError(msg)
                if response.status_code != 200:
                    body_text = await response.aread()
                    try:
                        body = _json.loads(body_text)
                        detail = body.get("error", {}).get("message", "")
                    except (ValueError, KeyError, AttributeError):
                        detail = body_text.decode(errors="replace")
                    msg = (
                        f"Google AI API error"
                        f" {response.status_code}: {detail}"
                    )
                    raise ProviderError(msg)

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        chunk_data = _json.loads(payload)
                    except _json.JSONDecodeError:
                        continue

                    # Extract text from candidates
                    candidates = chunk_data.get("candidates", [])
                    if candidates:
                        parts = (
                            candidates[0]
                            .get("content", {})
                            .get("parts", [])
                        )
                        for part in parts:
                            chunk = part.get("text", "")
                            if chunk:
                                accumulated_text += chunk
                                yield {"type": "token", "content": chunk}

                    # Capture usage metadata
                    usage_meta = chunk_data.get("usageMetadata", {})
                    if usage_meta:
                        input_tokens = usage_meta.get(
                            "promptTokenCount", input_tokens,
                        )
                        output_tokens = usage_meta.get(
                            "candidatesTokenCount", output_tokens,
                        )

        except httpx.TimeoutException as exc:
            msg = "Timeout calling Google AI API (streaming)"
            raise ProviderError(msg) from exc

        yield {
            "type": "complete",
            "content": accumulated_text,
            "tool_calls": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "provider": "google_ai",
            "model": self._model,
        }
