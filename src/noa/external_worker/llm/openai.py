"""OpenAI LLM client for the external worker.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

import asyncio
import json
import logging
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
        top_p: float | None = None,
    ) -> dict[str, Any]:
        """Build a request payload for the OpenAI Chat Completions API."""
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if top_p is not None:
            request["top_p"] = top_p
        return request

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
            except Exception:
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
        top_p: float | None = None,
    ) -> dict[str, Any]:
        """Send a completion request to OpenAI.

        Returns normalized response dict with content, tool_calls, usage.

        Raises:
            ProviderError: On upstream failure or timeout.
        """
        request = self.build_request(
            messages=messages,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        try:
            response = await self._send_request(request)
        except httpx.TimeoutException as exc:
            msg = "Timeout calling OpenAI API"
            raise ProviderError(msg) from exc
        return self._parse_response(response)
