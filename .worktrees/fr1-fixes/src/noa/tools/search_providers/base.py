"""Abstract base class for search providers.

All search providers must implement this interface to be usable
with the WebSearchTool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SearchProvider(ABC):
    """Abstract search provider interface.

    Subclasses must implement search() and the name property.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier (e.g., 'tavily', 'serper', 'exa')."""

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Execute a search query.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of result dicts with title, url, snippet keys.
        """
