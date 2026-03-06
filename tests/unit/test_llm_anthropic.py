"""Tests for Anthropic LLM client — Phase LP1.

Spec refs: SPEC.md §14.1, §14.4
Phase plan: MASTER_PLAN.md Phase LP1

Tests cover: real httpx calls to /v1/messages, tool_use block parsing,
retry on 429/529, error mapping (401, 400, 5xx), timeout handling.
All HTTP calls are mocked — no real API calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = [pytest.mark.lp1, pytest.mark.asyncio]


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        headers=headers or {},
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return resp


def _success_response(
    text: str = "Hello!",
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> httpx.Response:
    return _mock_response(
        200,
        {
            "id": "msg_abc123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "model": "claude-sonnet-4-20250514",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        },
    )


def _tool_use_response() -> httpx.Response:
    return _mock_response(
        200,
        {
            "id": "msg_abc123",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll search for that."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "web_search",
                    "input": {"query": "weather today"},
                },
            ],
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 15, "output_tokens": 20},
        },
    )


# ===========================================================================
# 1. Request formatting
# ===========================================================================


class TestAnthropicRequestFormat:
    """Anthropic client sends correct request to /v1/messages."""

    async def test_send_request_posts_to_messages_endpoint(self):
        """_send_request makes POST to /v1/messages with correct headers."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-ant-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            # URL must be the messages endpoint
            assert "/v1/messages" in str(call_args)

    async def test_request_includes_auth_headers(self):
        """Request includes x-api-key and anthropic-version headers."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-ant-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            call_kwargs = mock_instance.post.call_args
            # Check headers are passed (via client constructor or per-request)
            headers = call_kwargs.kwargs.get("headers") or {}
            # At minimum, the client should configure x-api-key
            # Could be in constructor or request — check MockClient constructor too
            constructor_kwargs = MockClient.call_args.kwargs if MockClient.call_args else {}
            all_headers = {**constructor_kwargs.get("headers", {}), **headers}
            assert all_headers.get("x-api-key") == "sk-ant-test"
            assert "anthropic-version" in all_headers


# ===========================================================================
# 2. Response parsing
# ===========================================================================


class TestAnthropicResponseParsing:
    """Anthropic client parses API responses correctly."""

    async def test_text_content_extracted(self):
        """Successful response: text content extracted."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(text="Hello world!")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            assert result["content"] == "Hello world!"

    async def test_usage_tokens_captured(self):
        """Usage tokens (input + output) are included in response."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(
                input_tokens=42, output_tokens=17,
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            assert result["usage"]["input_tokens"] == 42
            assert result["usage"]["output_tokens"] == 17

    async def test_tool_use_blocks_returned(self):
        """Tool use blocks in response returned as tool_calls list."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _tool_use_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Search weather"}],
                max_tokens=100,
            )

            assert len(result["tool_calls"]) == 1
            tc = result["tool_calls"][0]
            assert tc["id"] == "toolu_123"
            assert tc["name"] == "web_search"
            assert tc["input"] == {"query": "weather today"}


# ===========================================================================
# 3. Retry logic
# ===========================================================================


class TestAnthropicRetry:
    """Anthropic client retries on 429 and 529."""

    async def test_429_triggers_retry(self):
        """429 (rate limit) triggers retry with backoff."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        rate_limit_resp = _mock_response(429, {"error": {"message": "rate limited"}})
        success_resp = _success_response()

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = [rate_limit_resp, success_resp]
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("noa.external_worker.llm.anthropic.asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

            assert result["content"] == "Hello!"
            assert mock_instance.post.call_count == 2

    async def test_529_triggers_retry(self):
        """529 (overloaded) triggers retry."""
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        overloaded_resp = _mock_response(529, {"error": {"message": "overloaded"}})
        success_resp = _success_response()

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = [overloaded_resp, success_resp]
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("noa.external_worker.llm.anthropic.asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

            assert result["content"] == "Hello!"
            assert mock_instance.post.call_count == 2


# ===========================================================================
# 4. Error handling
# ===========================================================================


class TestAnthropicErrors:
    """Anthropic client maps HTTP errors to ProviderError."""

    async def test_401_raises_invalid_api_key(self):
        """401 raises ProviderError mentioning invalid API key."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="bad-key", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(
                401, {"error": {"message": "invalid x-api-key"}},
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)invalid.*api.key|401|auth"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    async def test_400_raises_provider_error_with_detail(self):
        """400 raises ProviderError with the error detail."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(
                400, {"error": {"message": "max_tokens must be positive"}},
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="max_tokens"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=-1,
                )

    async def test_timeout_raises_provider_error(self):
        """Timeout raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="sk-test", model="claude-sonnet-4-20250514")

        with patch("noa.external_worker.llm.anthropic.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("timed out")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)timeout"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )
