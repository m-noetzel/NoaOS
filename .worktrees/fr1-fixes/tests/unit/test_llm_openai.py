"""Tests for OpenAI LLM client — Phase LP2.

Spec refs: SPEC.md §14.1, §14.4
Phase plan: MASTER_PLAN.md Phase LP2

Tests cover: real httpx calls to /v1/chat/completions, tool_calls parsing,
retry on 429, error mapping (401, 5xx), timeout handling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = [pytest.mark.lp2, pytest.mark.asyncio]


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    return resp


def _success_response(
    content: str = "Hello!",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> httpx.Response:
    return _mock_response(
        200,
        {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                },
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    )


def _tool_calls_response() -> httpx.Response:
    return _mock_response(
        200,
        {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": '{"query": "weather today"}',
                                },
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                },
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35},
        },
    )


# ===========================================================================
# 1. Request formatting
# ===========================================================================


class TestOpenAIRequestFormat:
    async def test_send_request_posts_to_completions_endpoint(self):
        """_send_request makes POST to /v1/chat/completions with Authorization header."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test-openai", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "/v1/chat/completions" in str(call_args)

    async def test_request_includes_bearer_auth(self):
        """Request includes Authorization: Bearer header."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test-openai", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

            constructor_kwargs = MockClient.call_args.kwargs if MockClient.call_args else {}
            headers = constructor_kwargs.get("headers", {})
            assert headers.get("Authorization") == "Bearer sk-test-openai"

    async def test_top_p_included_when_set(self):
        """top_p parameter included in request payload when set."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")
        request = client.build_request(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=100,
            top_p=0.9,
        )
        assert request["top_p"] == 0.9


# ===========================================================================
# 2. Response parsing
# ===========================================================================


class TestOpenAIResponseParsing:
    async def test_text_content_extracted(self):
        """Successful response: content extracted from choices[0].message."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(content="World!")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            assert result["content"] == "World!"

    async def test_usage_tokens_captured(self):
        """Usage tokens (prompt + completion) included in response."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(
                prompt_tokens=42, completion_tokens=17,
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

    async def test_tool_calls_parsed(self):
        """Tool calls in response parsed into normalized format."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _tool_calls_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Search weather"}],
                max_tokens=100,
            )
            assert len(result["tool_calls"]) == 1
            tc = result["tool_calls"][0]
            assert tc["id"] == "call_123"
            assert tc["name"] == "web_search"
            assert tc["input"] == {"query": "weather today"}


# ===========================================================================
# 3. Retry logic
# ===========================================================================


class TestOpenAIRetry:
    async def test_429_triggers_retry(self):
        """429 (rate limit) triggers retry with backoff."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        rate_limit_resp = _mock_response(429, {"error": {"message": "rate limited"}})
        success_resp = _success_response()

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = [rate_limit_resp, success_resp]
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("noa.external_worker.llm.openai.asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

            assert result["content"] == "Hello!"
            assert mock_instance.post.call_count == 2


# ===========================================================================
# 4. Error handling
# ===========================================================================


class TestOpenAIErrors:
    async def test_401_raises_invalid_api_key(self):
        """401 raises ProviderError mentioning invalid API key."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="bad-key", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(
                401, {"error": {"message": "Incorrect API key"}},
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)invalid.*api.key|401|auth"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    async def test_500_raises_provider_error(self):
        """5xx raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(
                500, {"error": {"message": "internal error"}},
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    async def test_timeout_raises_provider_error(self):
        """Timeout raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="sk-test", model="gpt-4o")

        with patch("noa.external_worker.llm.openai.httpx.AsyncClient") as MockClient:
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
