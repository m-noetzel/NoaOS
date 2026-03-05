"""Tavily search provider implementation.

Tavily provides AI-optimized search results with pre-processed
content extraction. This is the first concrete SearchProvider
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noa.tools.search_providers.base import SearchProvider


@dataclass
class _TavilyClient:
    """Minimal Tavily API client stub.

    In production, this would use httpx/aiohttp to call the Tavily API.
    The _send_request method is the integration point.
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
    ) -> dict[str, Any]:  # pragma: no cover
        """Send HTTP request to Tavily API.

        Stub — will be implemented with real HTTP client.
        """
        raise NotImplementedError


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

        Args:
            query: Search query.
            max_results: Maximum results.

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
