"""Audio file validation — Phase iOS2.

Spec refs: SPEC.md §29.3
"""

from __future__ import annotations

MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_MIME_TYPES = frozenset({
    "audio/mp4",      # m4a (IANA registered)
    "audio/m4a",      # m4a (iOS AVFoundation default)
    "audio/mpeg",     # mp3
    "audio/wav",      # wav
    "audio/x-wav",    # wav variant
    "audio/flac",     # flac
    "audio/ogg",      # ogg
    "audio/webm",     # webm
})


def validate_audio(data: bytes, content_type: str) -> None:
    """Validate audio data size and MIME type.

    Args:
        data: Raw audio bytes.
        content_type: MIME type of the audio file.

    Raises:
        ValueError: If the audio exceeds 25 MB or has an unsupported MIME type.
    """
    if len(data) > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Audio file exceeds maximum size of 25 MB "
            f"({len(data)} bytes provided)"
        )

    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Unsupported audio MIME type: {content_type}. "
            f"Supported types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )
