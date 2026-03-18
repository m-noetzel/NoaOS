"""Tests for GT3: Notion HTTP Client + Registration.

Covers: NotionClient with real httpx calls to Notion API v1,
proper headers, error handling, and tool registration.

Spec refs: SPEC.md §12.3, §11.1
"""
# ruff: noqa: S105, S106, S107

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.gt3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(*, status_code: int = 200, json_data: dict | list | None = None):
    """Build a mock httpx response."""
    import httpx as real_httpx

    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = real_httpx.HTTPStatusError(
            str(status_code), request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _mock_httpx_client(*responses):
    """Build a mock async httpx client."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=list(responses))
    mock_client.get = AsyncMock(side_effect=list(responses))
    mock_client.patch = AsyncMock(side_effect=list(responses))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ===========================================================================
# search_pages
# ===========================================================================


class TestNotionClientSearch:
    """Tests for NotionClient.search_pages()."""

    @pytest.mark.asyncio
    async def test_search_sends_post_to_search(self):
        """search_pages must POST to /v1/search."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        search_data = {
            "results": [
                {
                    "id": "page-1",
                    "url": "https://notion.so/page-1",
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [{"plain_text": "My Page"}],
                        },
                    },
                },
            ],
        }
        mock_http = _mock_httpx_client(
            _mock_response(json_data=search_data)
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.search_pages(query="test")

        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args[0][0]
        assert "/v1/search" in call_url

    @pytest.mark.asyncio
    async def test_search_returns_id_title_url(self):
        """search_pages must return list of {id, title, url}."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        search_data = {
            "results": [
                {
                    "id": "p1",
                    "url": "https://notion.so/p1",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "Doc"}],
                        },
                    },
                },
            ],
        }
        mock_http = _mock_httpx_client(
            _mock_response(json_data=search_data)
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            result = await client.search_pages(query="doc")

        assert len(result) == 1
        assert result[0]["id"] == "p1"
        assert result[0]["title"] == "Doc"
        assert result[0]["url"] == "https://notion.so/p1"


# ===========================================================================
# read_page
# ===========================================================================


class TestNotionClientRead:
    """Tests for NotionClient.read_page()."""

    @pytest.mark.asyncio
    async def test_read_sends_get_to_blocks(self):
        """read_page must GET /v1/blocks/{id}/children."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        blocks_data = {
            "results": [
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "Hello world"}],
                    },
                },
            ],
        }
        mock_http = _mock_httpx_client(
            _mock_response(json_data=blocks_data)
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.read_page(page_id="abc-123")

        mock_http.get.assert_called_once()
        call_url = mock_http.get.call_args[0][0]
        assert "/v1/blocks/abc-123/children" in call_url

    @pytest.mark.asyncio
    async def test_read_converts_blocks_to_text(self):
        """read_page must convert blocks to plain text."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        blocks_data = {
            "results": [
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "Line one"}],
                    },
                },
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "Line two"}],
                    },
                },
            ],
        }
        mock_http = _mock_httpx_client(
            _mock_response(json_data=blocks_data)
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            result = await client.read_page(page_id="p1")

        assert "Line one" in result["content"]
        assert "Line two" in result["content"]


# ===========================================================================
# create_page
# ===========================================================================


class TestNotionClientCreate:
    """Tests for NotionClient.create_page()."""

    @pytest.mark.asyncio
    async def test_create_sends_post_to_pages(self):
        """create_page must POST to /v1/pages."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        mock_http = _mock_httpx_client(
            _mock_response(
                json_data={"id": "new-p", "url": "https://notion.so/new-p"}
            )
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            # Wave 23: parent_id removed — parent is always the hardcoded
            # Knowledge Management database (_DEFAULT_PARENT in notion_client.py)
            result = await client.create_page(
                title="New Page",
                content="Content here",
            )

        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args[0][0]
        assert "/v1/pages" in call_url
        assert result["id"] == "new-p"
        assert result["url"] == "https://notion.so/new-p"


# ===========================================================================
# update_page
# ===========================================================================


class TestNotionClientUpdate:
    """Tests for NotionClient.update_page()."""

    @pytest.mark.asyncio
    async def test_update_sends_patch_to_blocks(self):
        """update_page must PATCH /v1/blocks/{id}/children."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="test-token")

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"results": []})
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.update_page(
                page_id="p1", content="Updated text"
            )

        mock_http.patch.assert_called_once()
        call_url = mock_http.patch.call_args[0][0]
        assert "/v1/blocks/p1/children" in call_url


# ===========================================================================
# Headers
# ===========================================================================


class TestNotionClientHeaders:
    """Tests for Notion client headers."""

    @pytest.mark.asyncio
    async def test_sets_bearer_header(self):
        """Must set Authorization: Bearer {token}."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="my-notion-token")

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"results": []})
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.search_pages(query="test")

        call_kwargs = mock_http.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my-notion-token"

    @pytest.mark.asyncio
    async def test_sets_notion_version_header(self):
        """Must set Notion-Version: 2022-06-28."""
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="tok")

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"results": []})
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.search_pages(query="x")

        call_kwargs = mock_http.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Notion-Version") == "2022-06-28"


# ===========================================================================
# Error handling
# ===========================================================================


class TestNotionClientErrors:
    """Tests for Notion client error handling."""

    @pytest.mark.asyncio
    async def test_raises_on_401(self):
        """Must raise NotionAPIError on 401 (invalid token)."""
        from noa.tools.notion import NotionAPIError
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="bad-token")

        mock_http = _mock_httpx_client(
            _mock_response(status_code=401, json_data={"message": "Unauthorized"})
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(NotionAPIError):
                await client.search_pages(query="test")

    @pytest.mark.asyncio
    async def test_raises_on_404(self):
        """Must raise NotionAPIError on 404 (page not found)."""
        from noa.tools.notion import NotionAPIError
        from noa.tools.notion_client import NotionClient

        client = NotionClient(token="tok")

        mock_http = _mock_httpx_client(
            _mock_response(status_code=404, json_data={"message": "Not found"})
        )

        with patch("noa.tools.notion_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(NotionAPIError):
                await client.read_page(page_id="missing")


# ===========================================================================
# Registration
# ===========================================================================


class TestNotionRegistration:
    """Tests for Notion tool registration."""

    def test_register_notion_when_token_set(self):
        """_register_notion registers notion tool when NOTION_TOKEN set."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import register_tools

        gateway = ToolGateway()

        with patch.dict("os.environ", {"NOTION_TOKEN": "ntn_test123"}):
            register_tools(gateway)

        assert "notion" in gateway._adapters
