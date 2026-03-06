"""Tavily search provider — real HTTP implementation.

Tavily provides AI-optimized search results with pre-processed
content extraction. Uses httpx.AsyncClient for HTTP calls.

Spec refs: SPEC.md §12.4
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from noa.tools.search_providers.base import SearchProvider

_TIMEOUT_SECONDS = 15.0


@dataclass
class _TavilyClient:
    """Tavily API client using httpx.

    Sends POST to /search with api_key, query, max_results.
    """

    api_key: str
    base_url: str = "https://api.tavily.com"

    async def search(
        self, *, query: str, max_results: int = 10
    ) -> dict[str, Any]:
        """Call the Tavily search API.

        Returns raw API response dict.
        """
        return await self._send_request(
            query=query, max_results=max_results,
        )

    async def _send_request(
        self, **kwargs: Any
    ) -> dict[str, Any]:
        """Send HTTP POST to Tavily /search endpoint."""
        body = {
            "api_key": self.api_key,
            **kwargs,
        }
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
        ) as client:
            resp = await client.post(
                f"{self.base_url}/search",
                json=body,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]


class TavilySearchProvider(SearchProvider):
    """Tavily search provider.

    Args:
        api_key: Tavily API key.
    """

    def __init__(self, *, api_key: str) -> None:
        self._client = _TavilyClient(api_key=api_key)

    @property
    def name(self) -> str:
        return "tavily"

    async def search(
        self,
        *,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search via Tavily API.

        Returns:
            List of result dicts with title, url, snippet.
        """
        response = await self._client.search(
            query=query, max_results=max_results,
        )

        results = response.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in results
        ]
