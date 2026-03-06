"""Tests for TG3: Tavily HTTP Client + Registration.

Real httpx calls to Tavily API, registration in ToolGateway at startup.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from noa.tools.search_providers.tavily import (
    _TavilyClient,
)

# -------------------------------------------------------------------
# _TavilyClient HTTP tests (mocked httpx)
# -------------------------------------------------------------------


class TestTavilyClient:
    def _make_client(self, api_key: str = "test-key") -> _TavilyClient:
        return _TavilyClient(api_key=api_key)

    def test_sends_post_to_search_endpoint(self) -> None:
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "content": "Hello world",
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_resp
            mock_http_client.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_client.__aexit__ = AsyncMock(
                return_value=False
            )
            mock_httpx.AsyncClient.return_value = (
                mock_http_client
            )

            result = asyncio.run(
                client.search(query="hello", max_results=5)
            )

            mock_http_client.post.assert_called_once()
            call_args = mock_http_client.post.call_args
            assert "/search" in call_args[0][0]
            body = call_args[1].get(
                "json", call_args[0][1] if len(call_args[0]) > 1 else {}
            )
            assert body["query"] == "hello"
            assert result["results"][0]["title"] == "Example"

    def test_includes_api_key_in_request(self) -> None:
        client = self._make_client(api_key="my-secret")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            asyncio.run(
                client.search(query="test")
            )

            body = mock_http.post.call_args[1].get(
                "json", {}
            )
            assert body.get("api_key") == "my-secret"

    def test_parses_results(self) -> None:
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "A",
                    "url": "https://a.com",
                    "content": "aaa",
                },
                {
                    "title": "B",
                    "url": "https://b.com",
                    "content": "bbb",
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            result = asyncio.run(
                client.search(query="q", max_results=2)
            )

            assert len(result["results"]) == 2
            assert result["results"][0]["title"] == "A"
            assert result["results"][1]["url"] == "https://b.com"

    def test_handles_401_gracefully(self) -> None:
        client = self._make_client()

        import httpx as real_httpx

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_resp.raise_for_status.side_effect = (
                real_httpx.HTTPStatusError(
                    "401", request=MagicMock(), response=mock_resp
                )
            )
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            try:
                asyncio.run(
                    client.search(query="q")
                )
                got_error = False
            except Exception as exc:
                got_error = True
                assert "401" in str(exc) or "Unauthorized" in str(exc)
            assert got_error

    def test_handles_429_gracefully(self) -> None:
        client = self._make_client()

        import httpx as real_httpx

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.text = "Too Many Requests"
            mock_resp.raise_for_status.side_effect = (
                real_httpx.HTTPStatusError(
                    "429", request=MagicMock(), response=mock_resp
                )
            )
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            try:
                asyncio.run(
                    client.search(query="q")
                )
                got_error = False
            except Exception as exc:
                got_error = True
                assert "429" in str(exc)
            assert got_error

    def test_handles_timeout(self) -> None:
        client = self._make_client()

        import httpx as real_httpx

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_http.post.side_effect = (
                real_httpx.ReadTimeout("timeout")
            )
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http
            mock_httpx.ReadTimeout = real_httpx.ReadTimeout

            try:
                asyncio.run(
                    client.search(query="q")
                )
                got_error = False
            except Exception:
                got_error = True
            assert got_error

    def test_respects_max_results(self) -> None:
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            asyncio.run(
                client.search(query="q", max_results=3)
            )

            body = mock_http.post.call_args[1].get(
                "json", {}
            )
            assert body.get("max_results") == 3


# -------------------------------------------------------------------
# Registration tests
# -------------------------------------------------------------------


class TestToolRegistration:
    def test_registers_web_search_with_key(self) -> None:
        """wire_llm_pipeline registers web_search when key present."""
        from noa.api import app as app_mod

        mock_settings = MagicMock()
        mock_settings.tavily_api_key = "test-key"

        with patch.dict(
            "os.environ", {"TAVILY_API_KEY": "test-key"}
        ), patch.object(
            app_mod, "wire_llm_pipeline", wraps=None
        ):
            # Call the gateway registration part directly
            from noa.tools.gateway import ToolGateway
            from noa.tools.registration import (
                register_tools,
            )

            gw = ToolGateway()
            register_tools(gw)
            assert "web_search" in gw.allowlist

    def test_skips_web_search_without_key(self) -> None:
        """No web_search when TAVILY_API_KEY missing."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import register_tools

        with patch.dict("os.environ", {}, clear=True):
            gw = ToolGateway()
            register_tools(gw)
            assert "web_search" not in gw.allowlist

    def test_end_to_end_gateway_dispatch(self) -> None:
        """ToolGateway dispatches web_search through adapter."""
        from noa.tools.gateway import (
            ToolGateway,
            ToolRequest,
        )
        from noa.tools.registration import register_tools

        with patch.dict(
            "os.environ", {"TAVILY_API_KEY": "k"}
        ):
            gw = ToolGateway()
            register_tools(gw)

        assert "web_search" in gw.allowlist

        # Mock the underlying provider search
        with patch(
            "noa.tools.search_providers.tavily.httpx"
        ) as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "results": [
                    {
                        "title": "R",
                        "url": "https://r.com",
                        "content": "c",
                    }
                ],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(
                return_value=mock_http
            )
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_http

            req = ToolRequest(
                tool="web_search",
                function="web_search",
                args={"query": "test"},
            )
            resp = asyncio.run(gw.dispatch(req))

            assert resp.error is None
            assert resp.result is not None
            assert "results" in resp.result
