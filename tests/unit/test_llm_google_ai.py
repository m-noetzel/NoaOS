"""Tests for Google AI (Gemini) LLM client — Phase LP3.

Spec refs: SPEC.md §14.1, §14.4
Phase plan: MASTER_PLAN.md Phase LP3

Tests cover: message format mapping, generateContent API call,
response parsing, function call support, retry on 429, error mapping.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = [pytest.mark.lp3, pytest.mark.asyncio]


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        ),
    )
    return resp


def _success_response(
    text: str = "Hello!",
    prompt_tokens: int = 10,
    candidates_tokens: int = 5,
) -> httpx.Response:
    return _mock_response(
        200,
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": text}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                },
            ],
            "usageMetadata": {
                "promptTokenCount": prompt_tokens,
                "candidatesTokenCount": candidates_tokens,
                "totalTokenCount": prompt_tokens + candidates_tokens,
            },
        },
    )


def _function_call_response() -> httpx.Response:
    return _mock_response(
        200,
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "web_search",
                                    "args": {"query": "weather today"},
                                },
                            },
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                },
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 20,
                "totalTokenCount": 35,
            },
        },
    )


# ===========================================================================
# 1. Request formatting
# ===========================================================================


class TestGoogleAIRequestFormat:
    def test_build_request_maps_roles(self):
        """build_request maps 'assistant' role to 'model' for Gemini."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")
        request = client.build_request(
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "How are you?"},
            ],
            max_tokens=100,
        )
        contents = request["contents"]
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"
        assert contents[2]["role"] == "user"

    async def test_send_request_posts_to_generate_content(self):
        """_send_request POSTs to the generateContent URL with API key param."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
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
            url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
            assert "generateContent" in str(url)
            # API key should be in params
            params = call_args.kwargs.get("params", {})
            assert params.get("key") == "test-key"


# ===========================================================================
# 2. Response parsing
# ===========================================================================


class TestGoogleAIResponseParsing:
    async def test_text_content_extracted(self):
        """Successful response: text extracted from candidates[0].content.parts."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(text="World!")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
            assert result["content"] == "World!"

    async def test_usage_tokens_captured(self):
        """Usage tokens from usageMetadata included in response."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(
                prompt_tokens=42, candidates_tokens=17,
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

    async def test_function_call_returned(self):
        """functionCall parts returned as tool_calls."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _function_call_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Search weather"}],
                max_tokens=100,
            )
            assert len(result["tool_calls"]) == 1
            tc = result["tool_calls"][0]
            assert tc["name"] == "web_search"
            assert tc["input"] == {"query": "weather today"}


# ===========================================================================
# 3. Retry + errors
# ===========================================================================


class TestGoogleAIRetryAndErrors:
    async def test_429_triggers_retry(self):
        """429 triggers retry with backoff."""
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        rate_limit_resp = _mock_response(429, {"error": {"message": "rate limited"}})
        success_resp = _success_response()

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = [rate_limit_resp, success_resp]
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with patch("noa.external_worker.llm.google_ai.asyncio.sleep", new_callable=AsyncMock):
                result = await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )
            assert result["content"] == "Hello!"
            assert mock_instance.post.call_count == 2

    async def test_403_raises_invalid_api_key(self):
        """403 raises ProviderError mentioning invalid API key."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="bad-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(
                403, {"error": {"message": "API key not valid"}},
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)invalid.*api.key|403|auth"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    async def test_500_raises_provider_error(self):
        """5xx raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _mock_response(500, {"error": {"message": "internal"}})
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
        from noa.external_worker.llm.google_ai import GoogleAIClient

        client = GoogleAIClient(api_key="test-key", model="gemini-pro")

        with patch("noa.external_worker.llm.google_ai.httpx.AsyncClient") as MockClient:
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
