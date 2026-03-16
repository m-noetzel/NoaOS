"""Notion tool — search, read, create, update pages.

Spec refs: SPEC.md §12.3, §16.3

All operations go through the external domain. Content is sanitized
before display per §16.3.
"""

from __future__ import annotations

from typing import Any, cast

import nh3


class NotionAPIError(Exception):
    """Raised when the Notion API returns an error."""


# Allowed tags for nh3 sanitization (H10)
_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "dd", "del", "details",
    "div", "dl", "dt", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
    "i", "ins", "kbd", "li", "mark", "ol", "p", "pre", "q", "s", "samp",
    "small", "span", "strong", "sub", "summary", "sup", "table", "tbody",
    "td", "th", "thead", "tr", "u", "ul",
}

_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def _sanitize_content(content: str) -> str:
    """Sanitize HTML content using nh3 per §16.3 (H10).

    Strips all dangerous elements/attributes including script tags,
    event handlers, SVG-based XSS, and javascript: URIs.
    """
    return nh3.clean(
        content,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
    )


class NotionTool:
    """Notion tool per SPEC.md §12.3.

    Attributes:
        domain: "external" — requires Notion API access.
        risk_tiers: Per-action risk tiers.
    """

    name: str = "notion"
    domain: str = "external"
    risk_tiers: dict[str, str] = {
        "search_pages": "low",
        "read_page": "low",
        "create_page": "medium",
        "update_page": "medium",
    }

    def __init__(self, *, api_client: Any) -> None:
        self._client = api_client

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch to the appropriate method by function name."""
        method = getattr(self, function, None)
        if method is None:
            raise ValueError(f"Unknown function: {function}")
        return cast(dict[str, Any], await method(**args))

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
        return cast(list[dict[str, Any]], await self._client.search_pages(query=query))

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
        result: dict[str, Any] = cast(
            dict[str, Any], await self._client.read_page(page_id=page_id)
        )

        # Sanitize content per §16.3
        if "content" in result:
            result["content"] = _sanitize_content(result["content"])

        return result

    async def create_page(
        self,
        *,
        parent_id: str,
        parent_type: str = "page_id",
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Create a page under a parent page or database (Medium risk).

        Args:
            parent_id: ID of the parent page or database.
            parent_type: Either "page_id" or "database_id".
            title: Page title.
            content: Page content in markdown.

        Returns:
            Dict with created page ID.
        """
        return cast(dict[str, Any], await self._client.create_page(
            parent_id=parent_id,
            parent_type=parent_type,
            title=title,
            content=content,
        ))

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
        return cast(dict[str, Any], await self._client.update_page(
            page_id=page_id,
            content=content,
        ))
