"""Tests for dual-provider transcription — Phase iOS8.

Spec refs: SPEC.md §29.3 item 3 (Voice: record audio, send to backend for processing)
           SPEC.md §36.3 item 3 (Voice recording and playback)
Phase plan: PHASE_DETAILS.md Phase iOS8 (Voice Recording & Playback)

iOS8 extends the iOS2 voice infrastructure with:
  - A TranscriptionProvider ABC with a stable transcribe() contract
  - OpenAIWhisperProvider (existing logic refactored out of TranscriptionService)
  - WhisperCppProvider (POSTs to WHISPER_CPP_URL/transcribe, parses {"text": "..."})
  - TranscriptionService updated to dispatch to the selected provider
  - voice.py updated to read provider from user settings, no longer hard-requires OPENAI_API_KEY
  - transcription_provider + whisper_cpp_url added to config

These tests define the behavioral contract for the refactored provider dispatch layer.
They are written BEFORE implementation and must fail initially (red phase).
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.ios8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_audio(size: int = 1024) -> bytes:
    """Return minimal fake audio bytes."""
    return b"\x00\x01" * (size // 2)


def _whisper_response(text: str = "hello world") -> dict:
    return {"text": text}


# ---------------------------------------------------------------------------
# Existing TranscriptionService: must be refactored (assertion red tests)
# ---------------------------------------------------------------------------


class TestTranscriptionServiceRefactored:
    """iOS8: TranscriptionService must be updated to accept provider kwarg — red gate."""

    @pytest.mark.asyncio
    async def test_transcription_service_accepts_provider_kwarg(self):
        """PLAN Phase iOS8: Updated TranscriptionService.transcribe() accepts a 'provider' kwarg."""
        # Pre-iOS8 TranscriptionService takes api_key + http_client and does NOT
        # accept a provider kwarg.  After iOS8 the signature must support provider dispatch.
        # This test will fail (AssertionError) until the service is refactored.
        import inspect
        from noa.voice.transcription import TranscriptionService

        sig = inspect.signature(TranscriptionService.transcribe)
        param_names = list(sig.parameters.keys())
        assert "provider" in param_names, (
            f"TranscriptionService.transcribe() must accept 'provider' kwarg after iOS8 refactor; "
            f"current params: {param_names}"
        )

    def test_transcription_service_no_longer_requires_api_key_at_init(self):
        """PLAN Phase iOS8: Refactored TranscriptionService init must not take api_key as positional arg."""
        import inspect
        from noa.voice.transcription import TranscriptionService

        sig = inspect.signature(TranscriptionService.__init__)
        param_names = list(sig.parameters.keys())
        # After refactor, TranscriptionService takes openai_provider + whisper_cpp_provider,
        # not api_key + http_client at the top level.
        assert "openai_provider" in param_names or "whisper_cpp_provider" in param_names, (
            f"TranscriptionService.__init__ must accept provider objects after iOS8 refactor; "
            f"current params: {param_names}"
        )


# ---------------------------------------------------------------------------
# TranscriptionProvider ABC
# ---------------------------------------------------------------------------


class TestTranscriptionProviderABC:
    """iOS8: TranscriptionProvider is an ABC that enforces the transcribe() contract."""

    def test_provider_abc_cannot_be_instantiated_directly(self):
        """PLAN Phase iOS8: TranscriptionProvider ABC must not be directly instantiable."""
        from noa.voice.transcription import TranscriptionProvider  # type: ignore[attr-defined]

        with pytest.raises(TypeError):
            TranscriptionProvider()  # type: ignore[abstract]

    def test_concrete_provider_must_implement_transcribe(self):
        """PLAN Phase iOS8: A concrete subclass that omits transcribe() cannot be instantiated."""
        from noa.voice.transcription import TranscriptionProvider  # type: ignore[attr-defined]

        class IncompleteProvider(TranscriptionProvider):  # type: ignore[misc]
            pass  # does NOT implement transcribe()

        with pytest.raises(TypeError):
            IncompleteProvider()


# ---------------------------------------------------------------------------
# OpenAIWhisperProvider
# ---------------------------------------------------------------------------


class TestOpenAIWhisperProvider:
    """iOS8: OpenAIWhisperProvider posts audio to the OpenAI Whisper API."""

    @pytest.mark.asyncio
    async def test_transcribe_returns_text_from_whisper(self):
        """PLAN Phase iOS8: OpenAIWhisperProvider.transcribe() returns the text from Whisper API."""
        from noa.voice.transcription import OpenAIWhisperProvider  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _whisper_response("dictation test")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        result = await provider.transcribe(
            audio_data=_fake_audio(),
            filename="note.m4a",
            mime_type="audio/mp4",
        )
        assert result.text == "dictation test"

    @pytest.mark.asyncio
    async def test_transcribe_sends_bearer_token_to_openai(self):
        """PLAN Phase iOS8: OpenAIWhisperProvider includes Authorization: Bearer in request headers."""
        from noa.voice.transcription import OpenAIWhisperProvider  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _whisper_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-secret", http_client=mock_client)
        await provider.transcribe(
            audio_data=_fake_audio(),
            filename="note.m4a",
            mime_type="audio/mp4",
        )

        call_kwargs = mock_client.post.call_args
        # Authorization header must be present and carry the API key
        headers = call_kwargs.kwargs.get("headers", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
        auth_header_found = any(
            "Bearer sk-secret" in str(v)
            for v in (headers.values() if isinstance(headers, dict) else [str(headers)])
        )
        assert auth_header_found or "sk-secret" in str(call_kwargs), (
            "API key not found in request headers"
        )

    @pytest.mark.asyncio
    async def test_transcribe_raises_transcription_error_on_api_failure(self):
        """PLAN Phase iOS8: OpenAIWhisperProvider raises TranscriptionError on HTTP error."""
        from noa.voice.transcription import OpenAIWhisperProvider, TranscriptionError  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("502 Bad Gateway")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        with pytest.raises(TranscriptionError):
            await provider.transcribe(
                audio_data=_fake_audio(),
                filename="test.m4a",
                mime_type="audio/mp4",
            )


# ---------------------------------------------------------------------------
# WhisperCppProvider
# ---------------------------------------------------------------------------


class TestWhisperCppProvider:
    """iOS8: WhisperCppProvider posts audio to a local whisper.cpp HTTP service."""

    @pytest.mark.asyncio
    async def test_transcribe_posts_to_whisper_cpp_url(self):
        """PLAN Phase iOS8: WhisperCppProvider POSTs to WHISPER_CPP_URL/transcribe endpoint."""
        from noa.voice.transcription import WhisperCppProvider  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _whisper_response("local transcription")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = WhisperCppProvider(
            base_url="http://host.docker.internal:8001", http_client=mock_client
        )
        result = await provider.transcribe(
            audio_data=_fake_audio(),
            filename="voice.m4a",
            mime_type="audio/mp4",
        )

        assert result.text == "local transcription"
        # Must have POSTed to the /transcribe path
        call_args = mock_client.post.call_args
        assert "/transcribe" in str(call_args)

    @pytest.mark.asyncio
    async def test_transcribe_parses_text_field_from_response(self):
        """PLAN Phase iOS8: WhisperCppProvider parses {"text": "..."} from whisper.cpp response."""
        from noa.voice.transcription import WhisperCppProvider  # type: ignore[attr-defined]

        expected = "buy groceries and milk"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": expected}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = WhisperCppProvider(
            base_url="http://localhost:8001", http_client=mock_client
        )
        result = await provider.transcribe(
            audio_data=_fake_audio(),
            filename="note.m4a",
            mime_type="audio/mp4",
        )
        assert result.text == expected

    @pytest.mark.asyncio
    async def test_transcribe_raises_transcription_error_on_connection_failure(self):
        """PLAN Phase iOS8: WhisperCppProvider raises TranscriptionError when local service is unreachable."""
        from noa.voice.transcription import WhisperCppProvider, TranscriptionError  # type: ignore[attr-defined]

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")

        provider = WhisperCppProvider(
            base_url="http://localhost:8001", http_client=mock_client
        )
        with pytest.raises(TranscriptionError):
            await provider.transcribe(
                audio_data=_fake_audio(),
                filename="test.m4a",
                mime_type="audio/mp4",
            )

    @pytest.mark.asyncio
    async def test_whisper_cpp_uses_base_url_from_env(self):
        """PLAN Phase iOS8: WhisperCppProvider reads WHISPER_CPP_URL env var when not provided explicitly."""
        from noa.voice.transcription import WhisperCppProvider  # type: ignore[attr-defined]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _whisper_response("env url test")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        env_url = "http://custom-host:9999"
        os.environ["WHISPER_CPP_URL"] = env_url

        try:
            provider = WhisperCppProvider(http_client=mock_client)
            await provider.transcribe(
                audio_data=_fake_audio(),
                filename="note.m4a",
                mime_type="audio/mp4",
            )
            call_args = str(mock_client.post.call_args)
            assert "custom-host:9999" in call_args or "9999" in call_args
        finally:
            del os.environ["WHISPER_CPP_URL"]


# ---------------------------------------------------------------------------
# Provider Dispatch in TranscriptionService
# ---------------------------------------------------------------------------


class TestTranscriptionServiceProviderDispatch:
    """iOS8: TranscriptionService dispatches to the correct provider based on user setting."""

    @pytest.mark.asyncio
    async def test_openai_provider_selected_when_setting_is_openai(self):
        """PLAN Phase iOS8: provider='openai' routes to OpenAIWhisperProvider."""
        from noa.voice.transcription import TranscriptionService  # type: ignore[attr-defined]

        openai_provider = AsyncMock()
        from noa.voice.schemas import TranscriptionResult
        openai_provider.transcribe.return_value = TranscriptionResult(text="from openai")

        whisper_cpp_provider = AsyncMock()

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio(),
            filename="test.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )

        openai_provider.transcribe.assert_called_once()
        whisper_cpp_provider.transcribe.assert_not_called()
        assert result.text == "from openai"

    @pytest.mark.asyncio
    async def test_whisper_cpp_provider_selected_when_setting_is_whisper_cpp(self):
        """PLAN Phase iOS8: provider='whisper_cpp' routes to WhisperCppProvider."""
        from noa.voice.transcription import TranscriptionService  # type: ignore[attr-defined]

        openai_provider = AsyncMock()

        whisper_cpp_provider = AsyncMock()
        from noa.voice.schemas import TranscriptionResult
        whisper_cpp_provider.transcribe.return_value = TranscriptionResult(text="from whisper.cpp")

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio(),
            filename="test.m4a",
            mime_type="audio/mp4",
            provider="whisper_cpp",
        )

        whisper_cpp_provider.transcribe.assert_called_once()
        openai_provider.transcribe.assert_not_called()
        assert result.text == "from whisper.cpp"

    @pytest.mark.asyncio
    async def test_openai_is_default_provider_when_not_specified(self):
        """PLAN Phase iOS8: TranscriptionService defaults to 'openai' provider when none is specified."""
        from noa.voice.transcription import TranscriptionService  # type: ignore[attr-defined]

        openai_provider = AsyncMock()
        from noa.voice.schemas import TranscriptionResult
        openai_provider.transcribe.return_value = TranscriptionResult(text="default openai")

        whisper_cpp_provider = AsyncMock()

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        # Call without provider kwarg — must fall back to openai
        result = await service.transcribe(
            audio_data=_fake_audio(),
            filename="test.m4a",
            mime_type="audio/mp4",
        )

        openai_provider.transcribe.assert_called_once()
        assert result.text == "default openai"

    @pytest.mark.asyncio
    async def test_unknown_provider_raises_value_error(self):
        """PLAN Phase iOS8: Passing an unrecognised provider name raises ValueError, not a silent no-op."""
        from noa.voice.transcription import TranscriptionService  # type: ignore[attr-defined]

        openai_provider = AsyncMock()
        whisper_cpp_provider = AsyncMock()

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        with pytest.raises(ValueError, match="provider"):
            await service.transcribe(
                audio_data=_fake_audio(),
                filename="test.m4a",
                mime_type="audio/mp4",
                provider="unknown_provider",
            )


# ---------------------------------------------------------------------------
# Config: transcription_provider + whisper_cpp_url
# ---------------------------------------------------------------------------


class TestTranscriptionConfig:
    """iOS8: Config exposes transcription_provider and whisper_cpp_url settings."""

    def test_transcription_provider_defaults_to_openai(self, monkeypatch):
        """PLAN Phase iOS8: transcription_provider config setting defaults to 'openai'."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.delenv("TRANSCRIPTION_PROVIDER", raising=False)

        from importlib import reload
        import noa.config as cfg
        reload(cfg)

        settings = cfg.Settings()
        assert settings.transcription_provider == "openai"  # type: ignore[attr-defined]

    def test_whisper_cpp_url_default(self, monkeypatch):
        """PLAN Phase iOS8: whisper_cpp_url defaults to http://host.docker.internal:8001."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.delenv("WHISPER_CPP_URL", raising=False)

        from importlib import reload
        import noa.config as cfg
        reload(cfg)

        settings = cfg.Settings()
        assert "8001" in str(settings.whisper_cpp_url)  # type: ignore[attr-defined]

    def test_transcription_provider_can_be_set_to_whisper_cpp(self, monkeypatch):
        """PLAN Phase iOS8: transcription_provider=whisper_cpp is a valid config value."""
        monkeypatch.setenv("SECRET_KEY", "test-key")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "whisper_cpp")

        from importlib import reload
        import noa.config as cfg
        reload(cfg)

        settings = cfg.Settings()
        assert settings.transcription_provider == "whisper_cpp"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Voice endpoint: no longer hard-requires OPENAI_API_KEY
# ---------------------------------------------------------------------------


class TestVoiceEndpointProviderFlex:
    """iOS8: /voice/transcribe no longer returns 503 when OPENAI_API_KEY is absent and provider=whisper_cpp."""

    @pytest.mark.asyncio
    async def test_endpoint_does_not_require_openai_key_for_whisper_cpp(self, monkeypatch):
        """PLAN Phase iOS8: voice.py must not raise 503 when provider is whisper_cpp (no OpenAI key needed)."""
        # If the endpoint reads provider from settings and OPENAI_API_KEY is missing but
        # provider=whisper_cpp, it must proceed without error.
        # We validate this at the TranscriptionService level: dispatching to whisper_cpp
        # must NOT require an openai_api_key to be set.
        from noa.voice.transcription import TranscriptionService  # type: ignore[attr-defined]

        whisper_cpp_provider = AsyncMock()
        from noa.voice.schemas import TranscriptionResult
        whisper_cpp_provider.transcribe.return_value = TranscriptionResult(text="local only")

        # openai_provider is present but would fail if called (no key)
        openai_provider = AsyncMock()
        openai_provider.transcribe.side_effect = Exception("no api key")

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio(),
            filename="test.m4a",
            mime_type="audio/mp4",
            provider="whisper_cpp",
        )
        # Must succeed via whisper_cpp — never touched openai
        assert result.text == "local only"
        openai_provider.transcribe.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: provider selection end-to-end (only HTTP boundary mocked)
# ---------------------------------------------------------------------------


class TestProviderDispatchIntegration:
    """iOS8: Integration test — real TranscriptionService and real provider objects, only HTTP mocked."""

    @pytest.mark.asyncio
    async def test_openai_provider_full_path_with_mocked_http(self):
        """PLAN Phase iOS8: Full path — OpenAIWhisperProvider → TranscriptionService → result."""
        from noa.voice.transcription import (  # type: ignore[attr-defined]
            OpenAIWhisperProvider,
            TranscriptionService,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _whisper_response("integration test openai")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        openai_provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        whisper_cpp_provider = AsyncMock()

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio(2048),
            filename="meeting.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )

        assert result.text == "integration test openai"
        whisper_cpp_provider.transcribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_whisper_cpp_provider_full_path_with_mocked_http(self):
        """PLAN Phase iOS8: Full path — WhisperCppProvider → TranscriptionService → result."""
        from noa.voice.transcription import (  # type: ignore[attr-defined]
            WhisperCppProvider,
            TranscriptionService,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "integration test whisper.cpp"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        whisper_cpp_provider = WhisperCppProvider(
            base_url="http://localhost:8001", http_client=mock_client
        )
        openai_provider = AsyncMock()

        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio(2048),
            filename="note.m4a",
            mime_type="audio/mp4",
            provider="whisper_cpp",
        )

        assert result.text == "integration test whisper.cpp"
        openai_provider.transcribe.assert_not_called()
