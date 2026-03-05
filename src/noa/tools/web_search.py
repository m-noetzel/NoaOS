"""Web Search tool — provider-agnostic search interface.

Spec refs: SPEC.md §12.4

Uses the SearchProvider interface to decouple from specific search
APIs. Tavily is the default provider; others (Serper, Exa) can be
added as drop-in implementations.
"""

from __future__ import annotations

from typing import Any

from noa.tools.search_providers.base import SearchProvider


class WebSearchError(Exception):
    """Raised when a search provider returns an error."""


class WebSearchTool:
    """Web Search tool per SPEC.md §12.4.

    Attributes:
        domain: "external" — requires API access.
        risk_tier: Always "low".
    """

    domain: str = "external"
    risk_tier: str = "low"

    def __init__(self, *, provider: SearchProvider | Any) -> None:
        """Initialize with a search provider.

        Args:
            provider: SearchProvider implementation (or mock).
        """
        self._provider = provider

    async def web_search(
        self,
        *,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search the web and return results.

        Args:
            query: Search query string.
            max_results: Maximum number of results.

        Returns:
            List of result dicts with title, url, snippet.
        """
        return await self._provider.search(
            query=query, max_results=max_results,
        )
