"""Tests for KM1: Kimi (Moonshot AI) LLM provider integration.

Spec refs: SPEC.md Section 14.1, Section 14.4
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from noa.external_worker.exceptions import ProviderError
from noa.external_worker.llm.kimi import KimiClient
from noa.external_worker.llm.router import build_llm_clients

# ---------------------------------------------------------------------------
# KimiClient.complete() — non-streaming
# ---------------------------------------------------------------------------


@pytest.fixture()
def kimi_client() -> KimiClient:
    return KimiClient(api_key="test-key", model="kimi-k2")


def _make_completion_response(
    content: str = "Hello, world!",
    model: str = "kimi-k2",
    tool_calls: list[dict[str, Any]] | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> dict[str, Any]:
    """Build a fake Kimi/OpenAI-compatible completion response body."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class TestKimiClientComplete:
    """Tests for KimiClient.complete()."""

    @pytest.mark.asyncio
    async def test_complete_returns_normalized_dict(
        self, kimi_client: KimiClient
    ) -> None:
        """complete() returns content, tool_calls, usage, provider=kimi."""
        response_body = _make_completion_response("Hello from Kimi!")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_body

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await kimi_client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )

        assert result["content"] == "Hello from Kimi!"
        assert result["provider"] == "kimi"
        assert result["model"] == "kimi-k2"
        assert result["tool_calls"] == []
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_complete_with_model_override(
        self, kimi_client: KimiClient
    ) -> None:
        """model override replaces the constructor default in the request."""
        response_body = _make_completion_response(model="moonshot-v1-128k")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_body

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await kimi_client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=100,
                model="moonshot-v1-128k",
            )
            # Verify the request sent uses the overridden model
            sent_request = mock_send.call_args[0][0]
            assert sent_request["model"] == "moonshot-v1-128k"

        assert result["model"] == "moonshot-v1-128k"

    @pytest.mark.asyncio
    async def test_complete_raises_on_401(
        self, kimi_client: KimiClient
    ) -> None:
        """401 response raises ProviderError with descriptive message."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {}

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            with pytest.raises(ProviderError, match="invalid API key"):
                await kimi_client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_complete_raises_on_500(
        self, kimi_client: KimiClient
    ) -> None:
        """Non-200 response raises ProviderError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": {"message": "Internal server error"}
        }

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            with pytest.raises(ProviderError, match="500"):
                await kimi_client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_complete_raises_on_timeout(
        self, kimi_client: KimiClient
    ) -> None:
        """Timeout raises ProviderError."""
        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = httpx.TimeoutException("timed out")
            with pytest.raises(ProviderError, match="Timeout"):
                await kimi_client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                )


# ---------------------------------------------------------------------------
# Tool call parsing
# ---------------------------------------------------------------------------


class TestKimiToolCallParsing:
    """Tests for tool call parsing in complete()."""

    @pytest.mark.asyncio
    async def test_tool_calls_parsed_correctly(
        self, kimi_client: KimiClient
    ) -> None:
        """Tool calls are parsed from OpenAI format into internal format."""
        raw_tool_calls = [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "search",
                    "arguments": json.dumps({"query": "test"}),
                },
            }
        ]
        response_body = _make_completion_response(
            content="", tool_calls=raw_tool_calls
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_body

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await kimi_client.complete(
                messages=[{"role": "user", "content": "Search for test"}],
                max_tokens=100,
            )

        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "call_abc123"
        assert tc["name"] == "search"
        assert tc["input"] == {"query": "test"}

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(
        self, kimi_client: KimiClient
    ) -> None:
        """Multiple tool calls are all parsed."""
        raw_tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search",
                    "arguments": json.dumps({"query": "a"}),
                },
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": "/var/data/x"}),
                },
            },
        ]
        response_body = _make_completion_response(
            content="", tool_calls=raw_tool_calls
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_body

        with patch.object(kimi_client, "_send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            result = await kimi_client.complete(
                messages=[{"role": "user", "content": "Do multiple things"}],
                max_tokens=100,
            )

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["name"] == "search"
        assert result["tool_calls"][1]["name"] == "read_file"


# ---------------------------------------------------------------------------
# 429 retry logic
# ---------------------------------------------------------------------------


class TestKimiRetry:
    """Tests for 429 retry behavior in _send_request."""

    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(
        self, kimi_client: KimiClient
    ) -> None:
        """First 429 is retried; second attempt succeeds."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = _make_completion_response("Retry worked")

        call_count = 0

        async def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rate_limit_resp
            return success_resp

        mock_async_client = AsyncMock()
        mock_async_client.post.side_effect = fake_post
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("noa.external_worker.llm.kimi.httpx.AsyncClient", return_value=mock_async_client),
            patch("noa.external_worker.llm.kimi.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await kimi_client.complete(
                messages=[{"role": "user", "content": "Retry test"}],
                max_tokens=100,
            )

        assert call_count == 2
        assert result["content"] == "Retry worked"

    @pytest.mark.asyncio
    async def test_returns_last_429_after_max_retries(
        self, kimi_client: KimiClient
    ) -> None:
        """After max retries all return 429, the last response is returned (raising ProviderError)."""
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.json.return_value = {"error": {"message": "rate limit"}}

        mock_async_client = AsyncMock()
        mock_async_client.post.return_value = rate_limit_resp
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("noa.external_worker.llm.kimi.httpx.AsyncClient", return_value=mock_async_client),
            patch("noa.external_worker.llm.kimi.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ProviderError),
        ):
            # After all retries, _parse_response raises ProviderError on 429
            await kimi_client.complete(
                messages=[{"role": "user", "content": "Rate limit test"}],
                max_tokens=100,
            )


# ---------------------------------------------------------------------------
# complete_stream()
# ---------------------------------------------------------------------------


class TestKimiStream:
    """Tests for KimiClient.complete_stream()."""

    @pytest.mark.asyncio
    async def test_stream_yields_tokens_then_complete(
        self, kimi_client: KimiClient
    ) -> None:
        """complete_stream yields token events then a final complete event."""
        # Build SSE lines as Kimi/OpenAI would send them
        sse_lines = [
            'data: {"id":"1","model":"kimi-k2","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}],"usage":null}',
            'data: {"id":"2","model":"kimi-k2","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}],"usage":null}',
            'data: {"id":"3","model":"kimi-k2","choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
            "data: [DONE]",
        ]

        async def fake_aiter_lines() -> AsyncGenerator[str, None]:
            for line in sse_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = fake_aiter_lines
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("noa.external_worker.llm.kimi.httpx.AsyncClient", return_value=mock_client):
            gen = await kimi_client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=50,
            )
            events = [event async for event in gen]

        token_events = [e for e in events if e["type"] == "token"]
        complete_events = [e for e in events if e["type"] == "complete"]

        assert len(token_events) == 2
        assert token_events[0]["content"] == "Hello"
        assert token_events[1]["content"] == " world"

        assert len(complete_events) == 1
        final = complete_events[0]
        assert final["content"] == "Hello world"
        assert final["provider"] == "kimi"
        assert final["usage"]["input_tokens"] == 5
        assert final["usage"]["output_tokens"] == 2

    @pytest.mark.asyncio
    async def test_stream_raises_on_401(
        self, kimi_client: KimiClient
    ) -> None:
        """Streaming 401 raises ProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("noa.external_worker.llm.kimi.httpx.AsyncClient", return_value=mock_client):
            gen = await kimi_client.complete_stream(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=50,
            )
            with pytest.raises(ProviderError, match="invalid API key"):
                async for _ in gen:
                    pass


# ---------------------------------------------------------------------------
# Router: build_llm_clients
# ---------------------------------------------------------------------------


class TestRouterKimiIntegration:
    """Tests that the router correctly handles Kimi configuration."""

    def test_kimi_included_when_api_key_set(self) -> None:
        """build_llm_clients includes 'kimi' when kimi_api_key is set."""
        settings = MagicMock()
        settings.kimi_api_key = "test-kimi-key"
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = None

        clients = build_llm_clients(settings)

        assert "kimi" in clients
        from noa.external_worker.llm.kimi import KimiClient
        assert isinstance(clients["kimi"], KimiClient)

    def test_kimi_excluded_when_api_key_missing(self) -> None:
        """build_llm_clients excludes 'kimi' when kimi_api_key is None."""
        settings = MagicMock()
        settings.kimi_api_key = None
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = None

        clients = build_llm_clients(settings)

        assert "kimi" not in clients

    def test_kimi_excluded_when_api_key_empty_string(self) -> None:
        """build_llm_clients excludes 'kimi' when kimi_api_key is empty string."""
        settings = MagicMock()
        settings.kimi_api_key = ""
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = None

        clients = build_llm_clients(settings)

        assert "kimi" not in clients

    def test_kimi_uses_kimi_k2_as_default_model(self) -> None:
        """build_llm_clients creates KimiClient with kimi-k2 as default model."""
        settings = MagicMock()
        settings.kimi_api_key = "sk-test"
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = None

        clients = build_llm_clients(settings)

        kimi_client = clients["kimi"]
        assert kimi_client._model == "kimi-k2"

    def test_ollama_always_present_with_kimi(self) -> None:
        """Ollama is always present regardless of Kimi configuration."""
        settings = MagicMock()
        settings.kimi_api_key = "sk-test"
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.google_ai_api_key = None
        settings.ollama_base_url = None

        clients = build_llm_clients(settings)

        assert "ollama" in clients
        assert "kimi" in clients


# ---------------------------------------------------------------------------
# Message normalization
# ---------------------------------------------------------------------------


class TestKimiMessageNormalization:
    """Tests for _normalize_messages static method."""

    def test_plain_messages_pass_through(self) -> None:
        """Plain user/assistant messages are unchanged."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = KimiClient._normalize_messages(messages)
        assert result == messages

    def test_internal_tool_call_converted_to_openai_format(self) -> None:
        """Internal-format tool_calls are converted to OpenAI format."""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "name": "search",
                        "input": {"query": "hello"},
                    }
                ],
            }
        ]
        result = KimiClient._normalize_messages(messages)

        assert len(result) == 1
        tc = result[0]["tool_calls"][0]
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "search"
        assert json.loads(tc["function"]["arguments"]) == {"query": "hello"}

    def test_content_set_to_none_when_tool_calls_present(self) -> None:
        """Content is set to None (not empty string) when tool_calls are present."""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_1", "name": "tool", "input": {}}
                ],
            }
        ]
        result = KimiClient._normalize_messages(messages)
        assert result[0]["content"] is None
