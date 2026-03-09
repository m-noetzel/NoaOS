"""Transcription service with dual-provider support — Phase iOS8.

Spec refs: SPEC.md §29.3 (Voice: record audio, send to backend for processing)
           SPEC.md §36.3 item 3 (Voice recording and playback)

Providers:
  - OpenAIWhisperProvider: posts to OpenAI Whisper API
  - WhisperCppProvider: posts to local whisper.cpp HTTP service

TranscriptionService dispatches to the selected provider based on caller's
'provider' kwarg (defaults to 'openai').
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from noa.voice.schemas import TranscriptionResult

logger = logging.getLogger(__name__)

WHISPER_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_WHISPER_CPP_URL = "http://host.docker.internal:8001"


class TranscriptionError(Exception):
    """Raised when transcription fails (API error, network issue, etc.)."""


class TranscriptionProvider(ABC):
    """Abstract base class for transcription provider implementations."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        filename: str,
        mime_type: str,
    ) -> TranscriptionResult:
        """Transcribe audio data and return a TranscriptionResult.

        Args:
            audio_data: Raw audio bytes.
            filename: Original filename (e.g. "recording.m4a").
            mime_type: MIME type of the audio (e.g. "audio/mp4").

        Returns:
            TranscriptionResult with the transcribed text.

        Raises:
            TranscriptionError: On API or network failure.
        """


class OpenAIWhisperProvider(TranscriptionProvider):
    """Transcription via OpenAI Whisper API."""

    def __init__(
        self, api_key: str, http_client: Any, model: str = "whisper-1"
    ) -> None:
        self._api_key = api_key
        self._client = http_client
        self._model = model

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str,
        mime_type: str,
    ) -> TranscriptionResult:
        """Post audio to OpenAI Whisper API and return transcription.

        Raises:
            TranscriptionError: On HTTP or network failure.
        """
        try:
            response = await self._client.post(
                WHISPER_ENDPOINT,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (filename, audio_data, mime_type)},
                data={"model": self._model},
            )
            response.raise_for_status()
        except Exception as exc:
            raise TranscriptionError(
                f"OpenAI Whisper API request failed: {exc}"
            ) from exc

        data = response.json()
        return TranscriptionResult(text=data["text"])


class WhisperCppProvider(TranscriptionProvider):
    """Transcription via a local whisper.cpp HTTP service.

    Posts to {base_url}/transcribe and parses {"text": "..."} from the response.
    base_url can be supplied directly or read from WHISPER_CPP_URL env var.
    """

    def __init__(
        self,
        http_client: Any,
        base_url: str | None = None,
    ) -> None:
        resolved_url = (
            base_url or os.environ.get("WHISPER_CPP_URL", _DEFAULT_WHISPER_CPP_URL)
        )
        self._base_url = resolved_url.rstrip("/")
        self._client = http_client

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str,
        mime_type: str,
    ) -> TranscriptionResult:
        """Post audio to whisper.cpp service and return transcription.

        Raises:
            TranscriptionError: On HTTP or network failure.
        """
        endpoint = f"{self._base_url}/transcribe"
        try:
            response = await self._client.post(
                endpoint,
                files={"file": (filename, audio_data, mime_type)},
            )
            response.raise_for_status()
        except Exception as exc:
            raise TranscriptionError(
                f"whisper.cpp request to {endpoint} failed: {exc}"
            ) from exc

        data = response.json()
        return TranscriptionResult(text=data["text"])


class TranscriptionService:
    """Dispatches transcription requests to the appropriate provider.

    Accepts two provider objects at construction time (openai_provider and
    whisper_cpp_provider) and routes calls based on the 'provider' kwarg
    passed to transcribe() — defaults to 'openai'.
    """

    def __init__(
        self,
        openai_provider: TranscriptionProvider | Any,
        whisper_cpp_provider: TranscriptionProvider | Any,
    ) -> None:
        self._openai_provider = openai_provider
        self._whisper_cpp_provider = whisper_cpp_provider

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str,
        mime_type: str,
        provider: str = "openai",
    ) -> TranscriptionResult:
        """Transcribe audio using the specified provider.

        Args:
            audio_data: Raw audio bytes.
            filename: Original filename.
            mime_type: MIME type of the audio.
            provider: Provider name — 'openai' or 'whisper_cpp'. Defaults to 'openai'.

        Returns:
            TranscriptionResult with the transcribed text.

        Raises:
            ValueError: If provider name is not recognised.
            TranscriptionError: If the underlying provider fails.
        """
        if provider == "openai":
            return await self._openai_provider.transcribe(
                audio_data=audio_data,
                filename=filename,
                mime_type=mime_type,
            )
        elif provider == "whisper_cpp":
            return await self._whisper_cpp_provider.transcribe(
                audio_data=audio_data,
                filename=filename,
                mime_type=mime_type,
            )
        else:
            raise ValueError(
                f"Unknown transcription provider: {provider!r}. "
                "Valid providers: 'openai', 'whisper_cpp'."
            )
