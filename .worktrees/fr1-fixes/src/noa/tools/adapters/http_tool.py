"""HttpToolAdapter — generic HTTP adapter for custom tools (TM5).

Dispatches tool calls to base_url/{function_name} via HTTP POST.
Supports bearer token and API key authentication.
"""

from __future__ import annotations

import logging

import httpx

from noa.tools.gateway import ToolRequest, ToolResponse

logger = logging.getLogger(__name__)


class HttpToolAdapter:
    """Generic HTTP adapter that dispatches tool calls to an external API.

    Sends POST requests to ``{base_url}/{function_name}`` with the
    function arguments as the JSON body.
    """

    def __init__(
        self,
        *,
        base_url: str,
        auth_type: str = "none",
        auth_token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_type = auth_type
        self._auth_token = auth_token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute a tool function via HTTP POST."""
        url = f"{self._base_url}/{request.function}"
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if self._auth_type == "bearer" and self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        elif self._auth_type == "api_key" and self._auth_token:
            headers["X-API-Key"] = self._auth_token

        try:
            resp = await self._client.post(url, json=request.args, headers=headers)

            if resp.status_code != 200:
                return ToolResponse(
                    error=f"HTTP {resp.status_code}: {resp.text}",
                    provider="http_tool",
                )

            return ToolResponse(
                result=resp.json(),
                provider="http_tool",
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "HTTP tool adapter error for %s/%s: %s",
                self._base_url,
                request.function,
                exc,
            )
            return ToolResponse(error=str(exc), provider="http_tool")
