"""Notion API v1 HTTP client.

Spec refs: SPEC.md §12.3 (Notion functions), §11.1 (integration token)

Real httpx-based async client using Notion integration token
(simple bearer auth).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from httpx import HTTPStatusError

from noa.tools.notion import NotionAPIError

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Async client for Notion API v1.

    Args:
        token: Notion integration token.
    """

    def __init__(self, *, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an HTTP request to Notion API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await getattr(client, method)(
                url, headers=self._headers(), **kwargs,
            )
            try:
                resp.raise_for_status()
            except HTTPStatusError as exc:
                raise NotionAPIError(
                    f"Notion API error: {exc.response.status_code}"
                ) from exc
            result: dict[str, Any] = resp.json()
            return result

    async def search_pages(self, *, query: str) -> list[dict[str, Any]]:
        """Search for pages matching a query."""
        url = f"{_BASE_URL}/search"
        body = {"query": query, "filter": {"property": "object", "value": "page"}}
        data = await self._request("post", url, json=body)
        results = data.get("results", [])
        return [
            {
                "id": r["id"],
                "title": _extract_title(r),
                "url": r.get("url", ""),
            }
            for r in results
        ]

    async def read_page(self, *, page_id: str) -> dict[str, Any]:
        """Read page content by fetching child blocks."""
        url = f"{_BASE_URL}/blocks/{page_id}/children"
        data = await self._request("get", url)
        blocks = data.get("results", [])
        content = _blocks_to_text(blocks)
        return {"id": page_id, "content": content}

    async def create_page(
        self,
        *,
        parent_id: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Create a new page under a parent."""
        url = f"{_BASE_URL}/pages"
        body: dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}],
                },
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": content}}],
                    },
                },
            ],
        }
        result = await self._request("post", url, json=body)
        return {"id": result["id"], "url": result.get("url", "")}

    async def update_page(
        self,
        *,
        page_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Update page by appending content blocks."""
        url = f"{_BASE_URL}/blocks/{page_id}/children"
        body = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": content}}],
                    },
                },
            ],
        }
        return await self._request("patch", url, json=body)


def _extract_title(page: dict[str, Any]) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(
                t.get("plain_text", "") for t in title_parts
            )
    return ""


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion blocks to plain text."""
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_text)
        if text:
            lines.append(text)
    return "\n".join(lines)
