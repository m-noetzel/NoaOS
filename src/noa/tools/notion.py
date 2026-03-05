"""Notion tool — search, read, create, update pages.

Spec refs: SPEC.md §12.3, §16.3

All operations go through the external domain. Content is sanitized
before display per §16.3.
"""

from __future__ import annotations

import re
from typing import Any


class NotionAPIError(Exception):
    """Raised when the Notion API returns an error."""


# Pattern to strip script tags and their content per §16.3
_SCRIPT_TAG_RE = re.compile(
    r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
)


def _sanitize_content(content: str) -> str:
    """Remove potentially dangerous HTML from Notion content per §16.3."""
    return _SCRIPT_TAG_RE.sub("", content)


class NotionTool:
    """Notion tool per SPEC.md §12.3.

    Attributes:
        domain: "external" — requires Notion API access.
        risk_tiers: Per-action risk tiers.
    """

    domain: str = "external"
    risk_tiers: dict[str, str] = {
        "search_pages": "low",
        "read_page": "low",
        "create_page": "medium",
        "update_page": "medium",
    }

    def __init__(self, *, api_client: Any) -> None:
        self._client = api_client

    async def search_pages(
        self,
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        """Search pages with titles and IDs (Low risk).

        Args:
            query: Search query string.

        Returns:
            List of page summary dicts.
        """
        return await self._client.search_pages(query=query)

    async def read_page(
        self,
        *,
        page_id: str,
    ) -> dict[str, Any]:
        """Read page content as markdown (Low risk).

        Content is sanitized before display per §16.3.

        Args:
            page_id: ID of the page to read.

        Returns:
            Page dict with sanitized content.
        """
        result = await self._client.read_page(page_id=page_id)

        # Sanitize content per §16.3
        if "content" in result:
            result["content"] = _sanitize_content(result["content"])

        return result

    async def create_page(
        self,
        *,
        parent_id: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Create a page under a parent (Medium risk).

        Args:
            parent_id: ID of the parent page.
            title: Page title.
            content: Page content in markdown.

        Returns:
            Dict with created page ID.
        """
        return await self._client.create_page(
            parent_id=parent_id,
            title=title,
            content=content,
        )

    async def update_page(
        self,
        *,
        page_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Update page content (Medium risk).

        Args:
            page_id: ID of the page to update.
            content: New content in markdown.

        Returns:
            Dict with updated page data.
        """
        return await self._client.update_page(
            page_id=page_id,
            content=content,
        )
