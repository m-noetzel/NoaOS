"""Tests for Phase TI4: Notion Tool.

Covers: search_pages, read_page, create_page, update_page, risk tiers,
content sanitization, error handling.

Spec refs: SPEC.md §12.3, §16.3
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page_summary(
    *,
    page_id: str = "page-123",
    title: str = "Project Roadmap",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "title": title,
        "url": f"https://notion.so/{page_id}",
    }


def _make_page_content(
    *,
    page_id: str = "page-123",
    title: str = "Project Roadmap",
    content: str = "# Roadmap\n\nPhase 1: Foundation",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "title": title,
        "content": content,
    }


# ---------------------------------------------------------------------------
# NotionTool metadata
# ---------------------------------------------------------------------------


class TestNotionToolMetadata:
    """Tests for NotionTool class attributes per §12.3."""

    def test_domain_is_external(self):
        """Notion tool must be in external domain.

        SPEC.md §12.3 — Domain: External.
        """
        from noa.tools.notion import NotionTool

        assert NotionTool.domain == "external"

    def test_search_risk_tier_is_low(self):
        """search_pages risk tier must be Low.

        SPEC.md §12.3 — Risk tier: Low (search).
        """
        from noa.tools.notion import NotionTool

        assert NotionTool.risk_tiers["search_pages"] == "low"

    def test_read_risk_tier_is_low(self):
        """read_page risk tier must be Low.

        SPEC.md §12.3 — Risk tier: Low (read).
        """
        from noa.tools.notion import NotionTool

        assert NotionTool.risk_tiers["read_page"] == "low"

    def test_create_risk_tier_is_medium(self):
        """create_page risk tier must be Medium.

        SPEC.md §12.3 — Risk tier: Medium (create).
        """
        from noa.tools.notion import NotionTool

        assert NotionTool.risk_tiers["create_page"] == "medium"

    def test_update_risk_tier_is_medium(self):
        """update_page risk tier must be Medium.

        SPEC.md §12.3 — Risk tier: Medium (update).
        """
        from noa.tools.notion import NotionTool

        assert NotionTool.risk_tiers["update_page"] == "medium"


# ---------------------------------------------------------------------------
# search_pages
# ---------------------------------------------------------------------------


class TestSearchPages:
    """Tests for search_pages() per §12.3."""

    @pytest.mark.asyncio
    async def test_search_returns_pages(self):
        """search_pages must return matching pages.

        SPEC.md §12.3 — search_pages(query).
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.search_pages.return_value = [
            _make_page_summary(),
            _make_page_summary(page_id="page-456", title="Sprint Plan"),
        ]
        tool = NotionTool(api_client=mock_client)

        result = await tool.search_pages(query="roadmap")

        assert len(result) == 2
        assert result[0]["title"] == "Project Roadmap"

    @pytest.mark.asyncio
    async def test_search_results_include_id_and_title(self):
        """search_pages results must include page ID and title.

        SPEC.md §12.3 — Pages with titles and IDs.
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.search_pages.return_value = [_make_page_summary()]
        tool = NotionTool(api_client=mock_client)

        result = await tool.search_pages(query="test")

        page = result[0]
        assert "id" in page
        assert "title" in page


# ---------------------------------------------------------------------------
# read_page
# ---------------------------------------------------------------------------


class TestReadPage:
    """Tests for read_page() per §12.3, §16.3."""

    @pytest.mark.asyncio
    async def test_read_returns_content_as_markdown(self):
        """read_page must return page content as markdown.

        SPEC.md §12.3 — read_page returns page content as markdown.
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.read_page.return_value = _make_page_content()
        tool = NotionTool(api_client=mock_client)

        result = await tool.read_page(page_id="page-123")

        assert "# Roadmap" in result["content"]

    @pytest.mark.asyncio
    async def test_read_sanitizes_content(self):
        """read_page must sanitize content before display.

        SPEC.md §16.3 — Notion page content is sanitized before display.
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.read_page.return_value = _make_page_content(
            content="Normal text<script>alert('xss')</script>More text",
        )
        tool = NotionTool(api_client=mock_client)

        result = await tool.read_page(page_id="page-123")

        assert "<script>" not in result["content"]
        assert "Normal text" in result["content"]
        assert "More text" in result["content"]


# ---------------------------------------------------------------------------
# create_page
# ---------------------------------------------------------------------------


class TestCreatePage:
    """Tests for create_page() per §12.3."""

    @pytest.mark.asyncio
    async def test_create_returns_page_id(self):
        """create_page must return the created page ID.

        SPEC.md §12.3 — create_page returns page ID.
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.create_page.return_value = {"id": "page-new"}
        tool = NotionTool(api_client=mock_client)

        result = await tool.create_page(
            parent_id="parent-123",
            title="New Page",
            content="# Hello\n\nWorld",
        )

        assert result["id"] == "page-new"

    @pytest.mark.asyncio
    async def test_create_passes_all_fields(self):
        """create_page must pass parent_id, title, content to API.

        SPEC.md §12.3 — create_page(parent_id, title, content).
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.create_page.return_value = {"id": "page-new"}
        tool = NotionTool(api_client=mock_client)

        await tool.create_page(
            parent_id="parent-123",
            title="Test Page",
            content="Content here",
        )

        mock_client.create_page.assert_called_once_with(
            parent_id="parent-123",
            title="Test Page",
            content="Content here",
        )


# ---------------------------------------------------------------------------
# update_page
# ---------------------------------------------------------------------------


class TestUpdatePage:
    """Tests for update_page() per §12.3."""

    @pytest.mark.asyncio
    async def test_update_modifies_content(self):
        """update_page must update page content.

        SPEC.md §12.3 — update_page(page_id, content).
        """
        from noa.tools.notion import NotionTool

        mock_client = AsyncMock()
        mock_client.update_page.return_value = {
            "id": "page-123",
            "title": "Updated",
        }
        tool = NotionTool(api_client=mock_client)

        result = await tool.update_page(
            page_id="page-123",
            content="# Updated Content",
        )

        assert result["id"] == "page-123"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling per §12.3."""

    @pytest.mark.asyncio
    async def test_api_failure_handled_gracefully(self):
        """API failures must be handled gracefully.

        SPEC.md §12.3 — Error handling: API failures handled gracefully.
        """
        from noa.tools.notion import NotionAPIError, NotionTool

        mock_client = AsyncMock()
        mock_client.search_pages.side_effect = NotionAPIError(
            "Notion API returned 429"
        )
        tool = NotionTool(api_client=mock_client)

        with pytest.raises(NotionAPIError, match="429"):
            await tool.search_pages(query="test")
