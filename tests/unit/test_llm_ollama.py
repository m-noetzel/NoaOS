"""Tests for Ollama LLM client — Phase LP4.

Spec refs: SPEC.md §8.1, §14.1
Phase plan: MASTER_PLAN.md Phase LP4

Tests cover: /api/chat endpoint, async httpx calls, model manifest enforcement,
response parsing, connection error handling, timeout handling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

pytestmark = [pytest.mark.lp4, pytest.mark.asyncio]


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("POST", "http://ollama:11434/api/chat"),
    )
    return resp


def _success_response(
    content: str = "Hello!",
    prompt_eval_count: int = 10,
    eval_count: int = 5,
) -> httpx.Response:
    return _mock_response(
        200,
        {
            "model": "llama3.1",
            "message": {
                "role": "assistant",
                "content": content,
            },
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
        },
    )


# ===========================================================================
# 1. Request formatting
# ===========================================================================


class TestOllamaRequestFormat:
    def test_build_request_uses_chat_format(self):
        """build_request formats messages for /api/chat endpoint."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(
            model_manifest={"llama3.1": "approved"},
        )
        request = client.build_request(
            messages=[{"role": "user", "content": "Hi"}],
            model="llama3.1",
            max_tokens=100,
        )
        assert request["model"] == "llama3.1"
        assert request["messages"] == [{"role": "user", "content": "Hi"}]
        assert request["stream"] is False

    async def test_complete_posts_to_api_chat(self):
        """complete() sends POST to {base_url}/api/chat."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(
            model_manifest={"llama3.1": "approved"},
        )

        with patch("noa.private_worker.ollama_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                model="llama3.1",
                max_tokens=100,
            )

            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "/api/chat" in str(call_args)


# ===========================================================================
# 2. Response parsing
# ===========================================================================


class TestOllamaResponseParsing:
    async def test_content_extracted(self):
        """Successful response: content extracted from message.content."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved"})

        with patch("noa.private_worker.ollama_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(content="World!")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                model="llama3.1",
                max_tokens=100,
            )
            assert result["content"] == "World!"

    async def test_usage_tokens_captured(self):
        """Usage tokens from eval_count/prompt_eval_count included."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved"})

        with patch("noa.private_worker.ollama_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = _success_response(
                prompt_eval_count=42, eval_count=17,
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                model="llama3.1",
                max_tokens=100,
            )
            assert result["usage"]["input_tokens"] == 42
            assert result["usage"]["output_tokens"] == 17


# ===========================================================================
# 3. Model manifest enforcement
# ===========================================================================


class TestOllamaManifest:
    async def test_unapproved_model_rejected(self):
        """Unapproved model rejected before request sent (§8.1)."""
        from noa.external_worker.exceptions import ProviderError
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved"})

        with pytest.raises(ProviderError, match="(?i)not approved|not in.*manifest"):
            await client.complete(
                messages=[{"role": "user", "content": "Hi"}],
                model="evil-model",
                max_tokens=100,
            )

    def test_approved_model_passes_check(self):
        """Approved model passes manifest check."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved", "mistral": "approved"})
        assert client.is_model_approved("llama3.1") is True
        assert client.is_model_approved("mistral") is True
        assert client.is_model_approved("unknown") is False


# ===========================================================================
# 4. Error handling
# ===========================================================================


class TestOllamaErrors:
    async def test_connection_error_raises_provider_error(self):
        """Connection error (Ollama not running) raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved"})

        with patch("noa.private_worker.ollama_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)connect|unavailable"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="llama3.1",
                    max_tokens=100,
                )

    async def test_timeout_raises_provider_error(self):
        """Timeout raises ProviderError."""
        from noa.external_worker.exceptions import ProviderError
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(model_manifest={"llama3.1": "approved"})

        with patch("noa.private_worker.ollama_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("timed out")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ProviderError, match="(?i)timeout"):
                await client.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="llama3.1",
                    max_tokens=100,
                )
