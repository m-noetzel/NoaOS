"""Voice Pydantic schemas — Phase iOS2.

Spec refs: SPEC.md §29.3, §36.3 item 3
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    """Result of a Whisper transcription."""

    text: str
    duration_seconds: float | None = None


class VoiceUploadResponse(BaseModel):
    """Response for the voice upload endpoint."""

    text: str
    mode: Literal["transcribe", "chat"] = "transcribe"
    thread_id: uuid.UUID | None = None
