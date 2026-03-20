"""OpenAI LLM client for the external worker.

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

_API_BASE = "https://api.openai.com"
_MAX_RETRIES = 3
_RETRY_STATUSES = {429}
_TIMEOUT_SECONDS = 60.0


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
        temperature: float | None = None,
        top_p: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a request payload for the OpenAI Chat Completions API."""
        request: dict[str, Any] = {
            "model": self._model,
            "messages": self._normalize_messages(messages),
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            request["temperature"] = temperature
        if top_p is not None:
            request["top_p"] = top_p
        if tools:
            request["tools"] = tools
        return request

    @staticmethod
    def _normalize_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Re-format internal messages to OpenAI Chat Completions format.

        Converts internal tool_calls ({id, name, input}) back to OpenAI
        format ({id, type, function: {name, arguments}}).
        """
        normalized: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                oai_tool_calls = []
                for tc in msg["tool_calls"]:
                    if "function" in tc and "type" in tc:
                        # Already in OpenAI format
                        oai_tool_calls.append(tc)
                    else:
                        # Internal format → OpenAI format
                        args = tc.get("input") or tc.get("arguments") or {}
                        oai_tool_calls.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": (
                                    json.dumps(args)
                                    if isinstance(args, dict)
                                    else str(args)
                                ),
                            },
                        })
                normalized.append({
                    **msg,
                    "tool_calls": oai_tool_calls,
                    # OpenAI requires content to be null (not empty string)
                    # when there are tool_calls
                    "content": msg.get("content") or None,
                })
            else:
                normalized.append(msg)
        return normalized

    async def _send_request(self, request: dict[str, Any]) -> httpx.Response:
        """Send a request to the OpenAI API with retry on 429."""
        async with httpx.AsyncClient(
            base_url=_API_BASE,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            last_response: httpx.Response | None = None
            for attempt in range(_MAX_RETRIES):
                response = await client.post("/v1/chat/completions", json=request)
                if response.status_code not in _RETRY_STATUSES:
                    return response
                last_response = response
                delay = 2 ** attempt
                logger.warning(
                    "OpenAI %d (attempt %d/%d), retrying in %ds",
                    response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            assert last_response is not None
            return last_response

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse an OpenAI API response into normalized format."""
        if response.status_code == 401:
            msg = "OpenAI: invalid API key (401)"
            raise ProviderError(msg)

        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = body.get("error", {}).get("message", "")
            except (json.JSONDecodeError, ValueError):
                detail = response.text
            msg = f"OpenAI API error {response.status_code}: {detail}"
            raise ProviderError(msg)

        body = response.json()
        choice = body["choices"][0]["message"]
        content = choice.get("content") or ""

        # Parse tool calls
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            func = tc.get("function", {})
            arguments = func.get("arguments", "{}")
            try:
                parsed_args = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}
            tool_calls.append({
                "id": tc["id"],
                "name": func["name"],
                "input": parsed_args,
            })

        usage = body.get("usage", {})

        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            "provider": "openai",
            "model": body.get("model", self._model),
        }

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
        top_p: float | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to OpenAI.

        Args:
            model: Optional model override (uses constructor default if None).
            tools: Optional OpenAI-format tool definitions.

        Returns normalized response dict with content, tool_calls, usage.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            tools=tools,
        )
        if model:
            request["model"] = model
        try:
            response = await self._send_request(request)
        except httpx.TimeoutException as exc:
            msg = "Timeout calling OpenAI API"
            raise ProviderError(msg) from exc
        return self._parse_response(response)

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float | None = None,
        top_p: float | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a completion request to OpenAI, yielding token chunks.

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
            top_p=top_p,
            tools=tools,
        )
        if model:
            request["model"] = model
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}

        return self._stream_request(request)

    async def _stream_request(
        self,
        request: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Internal async generator that streams from OpenAI SSE."""
        model_used = request.get("model", self._model)
        accumulated_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            async with httpx.AsyncClient(
                base_url=_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT_SECONDS,
            ) as client, client.stream(
                "POST", "/v1/chat/completions", json=request,
            ) as response:
                if response.status_code == 401:
                    msg = "OpenAI: invalid API key (401)"
                    raise ProviderError(msg)
                if response.status_code != 200:
                    body_text = await response.aread()
                    try:
                        body = json.loads(body_text)
                        detail = body.get("error", {}).get("message", "")
                    except (json.JSONDecodeError, ValueError):
                        detail = body_text.decode(errors="replace")
                    msg = (
                        f"OpenAI API error"
                        f" {response.status_code}: {detail}"
                    )
                    raise ProviderError(msg)

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or line == "data: [DONE]":
                        if line == "data: [DONE]":
                            break
                        continue
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        chunk_data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    # Capture usage from the final chunk
                    if chunk_data.get("usage"):
                        usage = chunk_data["usage"]
                        input_tokens = usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0)

                    choices = chunk_data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    chunk = delta.get("content") or ""
                    if chunk:
                        accumulated_text += chunk
                        yield {"type": "token", "content": chunk}
                        model_used = chunk_data.get("model", model_used)

        except httpx.TimeoutException as exc:
            msg = "Timeout calling OpenAI API (streaming)"
            raise ProviderError(msg) from exc

        yield {
            "type": "complete",
            "content": accumulated_text,
            "tool_calls": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "provider": "openai",
            "model": model_used,
        }
