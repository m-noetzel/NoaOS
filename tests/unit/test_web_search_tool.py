"""Tests for Phase TI5: Web Search Tool (Provider-Agnostic).

Covers: web_search, SearchProvider interface, TavilySearchProvider,
provider selection, risk tier, max_results, error handling.

Spec refs: SPEC.md §12.4
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_result(
    *,
    title: str = "Example Page",
    url: str = "https://example.com",
    snippet: str = "This is an example page about...",
) -> dict[str, Any]:
    return {"title": title, "url": url, "snippet": snippet}


# ---------------------------------------------------------------------------
# WebSearchTool metadata
# ---------------------------------------------------------------------------


class TestWebSearchToolMetadata:
    """Tests for WebSearchTool class attributes per §12.4."""

    def test_domain_is_external(self):
        """Web search tool must be in external domain.

        SPEC.md §12.4 — Domain: External.
        """
        from noa.tools.web_search import WebSearchTool

        assert WebSearchTool.domain == "external"

    def test_risk_tier_is_low(self):
        """Web search risk tier must be Low.

        SPEC.md §12.4 — Risk tier: Low.
        """
        from noa.tools.web_search import WebSearchTool

        assert WebSearchTool.risk_tier == "low"


# ---------------------------------------------------------------------------
# SearchProvider interface
# ---------------------------------------------------------------------------


class TestSearchProviderInterface:
    """Tests for the SearchProvider abstract interface."""

    def test_search_provider_is_abstract(self):
        """SearchProvider must be an abstract base class.

        Provider-agnostic design per MASTER_PLAN TI5.
        """
        from noa.tools.search_providers.base import SearchProvider

        with pytest.raises(TypeError):
            SearchProvider()  # type: ignore[abstract]

    def test_search_provider_requires_search_method(self):
        """SearchProvider must require a search() method.

        Provider-agnostic design per MASTER_PLAN TI5.
        """
        from noa.tools.search_providers.base import SearchProvider

        assert hasattr(SearchProvider, "search")

    def test_search_provider_requires_name_property(self):
        """SearchProvider must require a name property.

        Provider-agnostic design per MASTER_PLAN TI5.
        """
        from noa.tools.search_providers.base import SearchProvider

        assert hasattr(SearchProvider, "name")


# ---------------------------------------------------------------------------
# TavilySearchProvider
# ---------------------------------------------------------------------------


class TestTavilyProvider:
    """Tests for TavilySearchProvider per MASTER_PLAN TI5."""

    def test_tavily_provider_name(self):
        """TavilySearchProvider must have name 'tavily'.

        First concrete implementation per MASTER_PLAN TI5.
        """
        from noa.tools.search_providers.tavily import (
            TavilySearchProvider,
        )

        provider = TavilySearchProvider(api_key="test-key")
        assert provider.name == "tavily"

    def test_tavily_implements_search_provider(self):
        """TavilySearchProvider must implement SearchProvider.

        Provider-agnostic design per MASTER_PLAN TI5.
        """
        from noa.tools.search_providers.base import SearchProvider
        from noa.tools.search_providers.tavily import (
            TavilySearchProvider,
        )

        assert issubclass(TavilySearchProvider, SearchProvider)

    @pytest.mark.asyncio
    async def test_tavily_search_returns_results(self):
        """TavilySearchProvider.search() must return search results.

        SPEC.md §12.4 — web_search returns results.
        """
        from noa.tools.search_providers.tavily import (
            TavilySearchProvider,
        )

        provider = TavilySearchProvider(api_key="test-key")
        # Mock the internal HTTP call
        provider._client = AsyncMock()
        provider._client.search.return_value = {
            "results": [
                {
                    "title": "Python Docs",
                    "url": "https://docs.python.org",
                    "content": "Python documentation...",
                }
            ]
        }

        results = await provider.search(
            query="python docs", max_results=5,
        )

        assert len(results) == 1
        assert results[0]["title"] == "Python Docs"


# ---------------------------------------------------------------------------
# web_search function
# ---------------------------------------------------------------------------


class TestWebSearch:
    """Tests for web_search() per §12.4."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """web_search must return results with title, URL, snippet.

        SPEC.md §12.4 — search results with title, URL, content snippet.
        """
        from noa.tools.web_search import WebSearchTool

        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            _make_search_result(),
            _make_search_result(title="Another Page"),
        ]
        tool = WebSearchTool(provider=mock_provider)

        result = await tool.web_search(query="test")

        assert len(result) == 2
        assert result[0]["title"] == "Example Page"
        assert "url" in result[0]
        assert "snippet" in result[0]

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self):
        """web_search must pass max_results to the provider.

        SPEC.md §12.4 — web_search(query, max_results?).
        """
        from noa.tools.web_search import WebSearchTool

        mock_provider = AsyncMock()
        mock_provider.search.return_value = []
        tool = WebSearchTool(provider=mock_provider)

        await tool.web_search(query="test", max_results=3)

        mock_provider.search.assert_called_once_with(
            query="test", max_results=3,
        )

    @pytest.mark.asyncio
    async def test_search_default_max_results(self):
        """web_search must default to 10 results.

        SPEC.md §12.4 — web_search(query, max_results?).
        """
        from noa.tools.web_search import WebSearchTool

        mock_provider = AsyncMock()
        mock_provider.search.return_value = []
        tool = WebSearchTool(provider=mock_provider)

        await tool.web_search(query="test")

        mock_provider.search.assert_called_once_with(
            query="test", max_results=10,
        )


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


class TestProviderSelection:
    """Tests for provider selection via configuration."""

    def test_web_search_tool_accepts_provider(self):
        """WebSearchTool must accept a SearchProvider instance.

        Provider-agnostic design per MASTER_PLAN TI5.
        """
        from noa.tools.web_search import WebSearchTool

        mock_provider = AsyncMock()
        tool = WebSearchTool(provider=mock_provider)

        assert tool._provider is mock_provider


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling per §12.4."""

    @pytest.mark.asyncio
    async def test_provider_failure_raises_search_error(self):
        """Provider failures must be handled gracefully.

        SPEC.md §12.4 — Error handling: API failures handled gracefully.
        """
        from noa.tools.web_search import WebSearchError, WebSearchTool

        mock_provider = AsyncMock()
        mock_provider.search.side_effect = WebSearchError(
            "Tavily API returned 500"
        )
        tool = WebSearchTool(provider=mock_provider)

        with pytest.raises(WebSearchError, match="500"):
            await tool.web_search(query="test")
