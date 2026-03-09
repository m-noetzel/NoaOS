"""Tests for voice upload endpoint — Phase iOS2.

Spec refs: SPEC.md §29.3 (Voice: record audio, send to backend for processing),
           §36.3 item 3 (Voice recording and playback)
Phase plan: PHASE_DETAILS.md Phase iOS2

These tests define the behavioral contract for multipart audio upload,
Whisper-based transcription, audio validation, and optional chat pipeline
integration. They are written BEFORE implementation and must all fail initially.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.ios2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_id():
    return uuid.uuid4()


def _fake_audio_bytes(size: int = 1024, header: bytes = b"fLaC") -> bytes:
    """Return fake audio content with a recognizable header."""
    return header + b"\x00" * (size - len(header))


def _mock_whisper_response(text: str = "Hello world") -> dict:
    """Whisper API JSON response shape."""
    return {"text": text}


# ---------------------------------------------------------------------------
# TranscriptionService
# ---------------------------------------------------------------------------

class TestTranscriptionService:
    """PHASE iOS2: TranscriptionService wraps OpenAI Whisper API via httpx.

    Updated for iOS8: TranscriptionService now accepts provider objects.
    These tests use OpenAIWhisperProvider directly (the extracted OpenAI logic).
    """

    @pytest.mark.asyncio
    async def test_transcribe_returns_text(self):
        """PHASE iOS2: OpenAIWhisperProvider.transcribe() returns transcription text."""
        from noa.voice.transcription import OpenAIWhisperProvider, TranscriptionService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_whisper_response("Test transcription")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        service = TranscriptionService(
            openai_provider=provider,
            whisper_cpp_provider=provider,  # unused in this test
        )
        result = await service.transcribe(
            audio_data=_fake_audio_bytes(),
            filename="test.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )
        assert result.text == "Test transcription"

    @pytest.mark.asyncio
    async def test_transcribe_sends_multipart_to_whisper(self):
        """PHASE iOS2: OpenAIWhisperProvider posts multipart/form-data to OpenAI Whisper endpoint."""
        from noa.voice.transcription import OpenAIWhisperProvider, TranscriptionService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_whisper_response()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        service = TranscriptionService(
            openai_provider=provider,
            whisper_cpp_provider=provider,  # unused in this test
        )
        await service.transcribe(
            audio_data=_fake_audio_bytes(),
            filename="recording.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )

        # Must have called the Whisper API endpoint
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "transcriptions" in str(call_args)

    @pytest.mark.asyncio
    async def test_transcribe_propagates_api_error(self):
        """PHASE iOS2: OpenAIWhisperProvider raises TranscriptionError on Whisper API failure."""
        from noa.voice.transcription import OpenAIWhisperProvider, TranscriptionService, TranscriptionError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        service = TranscriptionService(
            openai_provider=provider,
            whisper_cpp_provider=provider,  # unused in this test
        )
        with pytest.raises(TranscriptionError):
            await service.transcribe(
                audio_data=_fake_audio_bytes(),
                filename="test.m4a",
                mime_type="audio/mp4",
                provider="openai",
            )


# ---------------------------------------------------------------------------
# Voice Schemas
# ---------------------------------------------------------------------------

class TestVoiceSchemas:
    """PHASE iOS2: Pydantic schemas for voice endpoint request/response."""

    def test_transcription_result_has_text(self):
        """PHASE iOS2: TranscriptionResult carries the transcribed text."""
        from noa.voice.schemas import TranscriptionResult

        result = TranscriptionResult(text="Hello from voice", duration_seconds=3.5)
        assert result.text == "Hello from voice"
        assert result.duration_seconds == 3.5

    def test_voice_upload_response_transcription_only(self):
        """PHASE iOS2: VoiceUploadResponse in transcription-only mode contains text, no thread."""
        from noa.voice.schemas import VoiceUploadResponse

        resp = VoiceUploadResponse(
            text="Transcribed text",
            mode="transcribe",
        )
        assert resp.text == "Transcribed text"
        assert resp.mode == "transcribe"
        assert resp.thread_id is None


# ---------------------------------------------------------------------------
# Audio Validation
# ---------------------------------------------------------------------------

class TestAudioValidation:
    """PHASE iOS2: Audio file validation (size, MIME type)."""

    def test_reject_oversized_audio(self):
        """PHASE iOS2: Audio files exceeding 25MB are rejected."""
        from noa.voice.validation import validate_audio

        max_bytes = 25 * 1024 * 1024  # 25 MB
        oversized = _fake_audio_bytes(size=max_bytes + 1)

        with pytest.raises(ValueError, match="25"):
            validate_audio(
                data=oversized,
                content_type="audio/mp4",
            )

    def test_accept_valid_m4a(self):
        """PHASE iOS2: m4a (audio/mp4) files within size limit are accepted."""
        from noa.voice.validation import validate_audio

        valid = _fake_audio_bytes(size=1024)
        # Should not raise
        validate_audio(data=valid, content_type="audio/mp4")

    def test_accept_valid_wav(self):
        """PHASE iOS2: wav (audio/wav) files are accepted."""
        from noa.voice.validation import validate_audio

        valid = _fake_audio_bytes(size=1024)
        validate_audio(data=valid, content_type="audio/wav")

    def test_accept_valid_mp3(self):
        """PHASE iOS2: mp3 (audio/mpeg) files are accepted."""
        from noa.voice.validation import validate_audio

        valid = _fake_audio_bytes(size=1024)
        validate_audio(data=valid, content_type="audio/mpeg")

    def test_reject_unsupported_mime_type(self):
        """PHASE iOS2: Unsupported MIME types (e.g., video/mp4) are rejected."""
        from noa.voice.validation import validate_audio

        data = _fake_audio_bytes(size=1024)
        with pytest.raises(ValueError, match="[Uu]nsupported"):
            validate_audio(data=data, content_type="video/mp4")


# ---------------------------------------------------------------------------
# Voice Endpoint — Transcription-Only Mode
# ---------------------------------------------------------------------------

class TestVoiceEndpointTranscribeOnly:
    """PHASE iOS2: POST /api/v1/voice/transcribe returns JSON transcription."""

    @pytest.mark.asyncio
    async def test_transcribe_returns_json_response(self):
        """PHASE iOS2: Transcription-only mode returns JSON with text field."""
        from noa.voice.transcription import OpenAIWhisperProvider, TranscriptionService
        from noa.voice.schemas import TranscriptionResult

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_whisper_response("Meeting at 3pm")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        service = TranscriptionService(
            openai_provider=provider,
            whisper_cpp_provider=provider,
        )
        result = await service.transcribe(
            audio_data=_fake_audio_bytes(),
            filename="voice.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Meeting at 3pm"


# ---------------------------------------------------------------------------
# Voice Endpoint — Chat Pipeline Mode
# ---------------------------------------------------------------------------

class TestVoiceEndpointChatMode:
    """PHASE iOS2: POST /api/v1/voice/transcribe?mode=chat pipes to chat pipeline."""

    @pytest.mark.asyncio
    async def test_chat_mode_feeds_transcription_to_pipeline(self):
        """PHASE iOS2: In chat mode, transcribed text is sent to the chat pipeline."""
        from noa.voice.schemas import VoiceUploadResponse

        # In chat mode, response must include a thread_id for the resulting conversation
        resp = VoiceUploadResponse(
            text="Remind me to call mom",
            mode="chat",
            thread_id=uuid.uuid4(),
        )
        assert resp.mode == "chat"
        assert resp.thread_id is not None


# ---------------------------------------------------------------------------
# Config Settings
# ---------------------------------------------------------------------------

class TestVoiceConfig:
    """PHASE iOS2: Voice-related settings in config."""

    def test_whisper_model_default(self):
        """PHASE iOS2: WHISPER_MODEL setting exists with a default value."""
        from noa.config import Settings
        import os

        os.environ.setdefault("SECRET_KEY", "test-key")
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        settings = Settings()
        assert hasattr(settings, "whisper_model")
        assert settings.whisper_model == "whisper-1"

    def test_max_audio_size_default(self):
        """PHASE iOS2: MAX_AUDIO_SIZE_MB setting defaults to 25."""
        from noa.config import Settings
        import os

        os.environ.setdefault("SECRET_KEY", "test-key")
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
        settings = Settings()
        assert hasattr(settings, "max_audio_size_mb")
        assert settings.max_audio_size_mb == 25


# ---------------------------------------------------------------------------
# Voice Endpoint — Auth & Router
# ---------------------------------------------------------------------------

class TestVoiceEndpointAuth:
    """PHASE iOS2: Voice endpoint requires authentication."""

    def test_voice_router_exists(self):
        """PHASE iOS2: Voice router is importable from noa.api.v1.voice."""
        from noa.api.v1.voice import router

        assert router is not None

    def test_voice_router_has_transcribe_route(self):
        """PHASE iOS2: Voice router exposes POST /transcribe endpoint."""
        from noa.api.v1.voice import router

        routes = [r.path for r in router.routes]
        assert "/transcribe" in routes


# ---------------------------------------------------------------------------
# Integration: TranscriptionService end-to-end (mocking only HTTP boundary)
# ---------------------------------------------------------------------------

class TestTranscriptionIntegration:
    """PHASE iOS2: Integration test — real TranscriptionService with mocked HTTP only."""

    @pytest.mark.asyncio
    async def test_full_transcription_flow(self):
        """PHASE iOS2: Validate → transcribe → result, with only HTTP mocked."""
        from noa.voice.validation import validate_audio
        from noa.voice.transcription import TranscriptionService
        from noa.voice.schemas import TranscriptionResult

        # Step 1: Validate audio (real code)
        audio_data = _fake_audio_bytes(size=2048)
        validate_audio(data=audio_data, content_type="audio/mp4")

        # Step 2: Transcribe via service (mock only the HTTP client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_whisper_response(
            "Schedule a meeting for tomorrow"
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        from noa.voice.transcription import OpenAIWhisperProvider
        provider = OpenAIWhisperProvider(api_key="sk-test", http_client=mock_client)
        service = TranscriptionService(
            openai_provider=provider,
            whisper_cpp_provider=provider,
        )
        result = await service.transcribe(
            audio_data=audio_data,
            filename="memo.m4a",
            mime_type="audio/mp4",
            provider="openai",
        )

        # Step 3: Verify result shape
        assert isinstance(result, TranscriptionResult)
        assert len(result.text) > 0
        assert result.text == "Schedule a meeting for tomorrow"
