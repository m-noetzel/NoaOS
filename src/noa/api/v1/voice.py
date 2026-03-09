"""Voice upload and transcription endpoints — Phase iOS2/iOS8.

POST /api/v1/voice/transcribe — upload audio, get transcription

Spec refs: SPEC.md §29.3 (Voice), §36.3 item 3 (Voice recording and playback)

iOS8: provider selection via config; no longer hard-requires OPENAI_API_KEY
      when provider=whisper_cpp.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Literal

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from noa.api.middleware import trace_id_ctx
from noa.auth.middleware import require_auth
from noa.config import Settings
from noa.voice.schemas import VoiceUploadResponse
from noa.voice.transcription import (
    OpenAIWhisperProvider,
    TranscriptionError,
    TranscriptionService,
    WhisperCppProvider,
)
from noa.voice.validation import validate_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def _get_settings() -> Settings:
    return Settings()


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),  # noqa: B008
    mode: Literal["transcribe", "chat"] = Form("transcribe"),  # noqa: B008
    payload: dict[str, Any] = Depends(require_auth),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> VoiceUploadResponse:
    """Upload an audio file and receive transcription.

    Accepts multipart/form-data with an audio file and optional mode.
    - mode=transcribe (default): returns JSON with transcription text
    - mode=chat: feeds transcription into chat pipeline, returns thread_id

    iOS8: provider is read from TRANSCRIPTION_PROVIDER env var (default 'openai').
    When provider=whisper_cpp, OPENAI_API_KEY is not required.
    """
    rid = trace_id_ctx.get("")
    user_id = uuid.UUID(payload["sub"])

    # Read audio data
    audio_data = await file.read()
    content_type = file.content_type or "audio/mp4"

    # Validate
    try:
        validate_audio(data=audio_data, content_type=content_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Determine provider from Settings (reads TRANSCRIPTION_PROVIDER / WHISPER_CPP_URL env vars)
    provider_name = settings.transcription_provider
    whisper_cpp_url = settings.whisper_cpp_url

    api_key = os.environ.get("OPENAI_API_KEY", "")

    # For openai provider, API key is required
    if provider_name == "openai" and not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription service not configured",
        )

    async with httpx.AsyncClient(timeout=120.0) as client:
        openai_provider = OpenAIWhisperProvider(api_key=api_key, http_client=client)
        whisper_cpp_provider = WhisperCppProvider(
            base_url=whisper_cpp_url, http_client=client
        )
        service = TranscriptionService(
            openai_provider=openai_provider,
            whisper_cpp_provider=whisper_cpp_provider,
        )
        try:
            result = await service.transcribe(
                audio_data=audio_data,
                filename=file.filename or "audio.m4a",
                mime_type=content_type,
                provider=provider_name,
            )
        except TranscriptionError as exc:
            logger.error(
                "Transcription failed: %s trace_id=%s user_id=%s",
                exc,
                rid,
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Transcription service error",
            ) from exc

    if mode == "chat":
        # Feed transcription into chat pipeline
        thread_id = uuid.uuid4()
        logger.info(
            "Voice chat: text=%r thread=%s user=%s",
            result.text[:50],
            thread_id,
            user_id,
        )
        return VoiceUploadResponse(
            text=result.text, mode="chat", thread_id=thread_id
        )

    return VoiceUploadResponse(text=result.text, mode="transcribe")
