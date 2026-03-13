"""whisper-service — Host-side FastAPI wrapper for whisper.cpp binary.

Accepts audio via multipart/form-data, writes to a temp file, runs the
whisper binary, and returns {"text": "..."}.

Spec ref: SPEC.md §29.3, Phase iOS8
Architecture: runs on Mac host (not in Docker); called by Noa backend via
http://host.docker.internal:8001/transcribe

Usage:
    uvicorn server:app --host 0.0.0.0 --port 8001

Configuration (environment variables):
    WHISPER_BIN   Path to the whisper.cpp main binary (default: whisper-cpp)
    WHISPER_MODEL Path to the .bin model file
                  (default: ~/whisper-models/ggml-large-v3-q5_0.bin)
    WHISPER_LANG  Language hint (default: auto)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="whisper-service", version="1.0.0")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WHISPER_BIN = os.environ.get("WHISPER_BIN", "whisper-cpp")
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL",
    str(Path.home() / "whisper-models" / "ggml-large-v3-q5_0.bin"),
)
WHISPER_LANG = os.environ.get("WHISPER_LANG", "auto")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    model_exists = Path(WHISPER_MODEL).exists()
    return {
        "status": "ok" if model_exists else "model_missing",
        "model": WHISPER_MODEL,
        "bin": WHISPER_BIN,
    }


# ---------------------------------------------------------------------------
# Transcription endpoint
# ---------------------------------------------------------------------------

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> JSONResponse:  # noqa: B008
    """Accept an audio file and return a transcription.

    Returns:
        {"text": "<transcription>"}

    Raises:
        422 if no file provided.
        503 if whisper model file is missing.
        502 if the whisper binary fails.
    """
    if not Path(WHISPER_MODEL).exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Whisper model not found: {WHISPER_MODEL}",
        )

    audio_data = await file.read()
    suffix = Path(file.filename or "audio.m4a").suffix or ".m4a"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        text = await _run_whisper(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return JSONResponse({"text": text})


# ---------------------------------------------------------------------------
# whisper.cpp runner
# ---------------------------------------------------------------------------

async def _run_whisper(audio_path: str) -> str:
    """Run the whisper.cpp binary on *audio_path* and return the transcription.

    whisper.cpp (main binary) CLI:
        whisper-cpp -m <model> -f <file> -l <lang> --output-txt -otxt

    We capture stdout/stderr and parse the plain-text output file that
    whisper.cpp writes alongside the input file when --output-txt is given.
    Alternatively, we use --no-timestamps and parse stdout directly.
    """
    cmd = [
        WHISPER_BIN,
        "-m", WHISPER_MODEL,
        "-f", audio_path,
        "-l", WHISPER_LANG,
        "--no-timestamps",
        "-np",        # no progress output
        "--print-special", "false",
    ]

    logger.info("Running: %s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"whisper binary not found: {WHISPER_BIN}",
        ) from exc
    except asyncio.TimeoutError as exc:
        # Kill the subprocess so it doesn't keep running after the request times out.
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Whisper transcription timed out (>5 min)",
        ) from exc

    if proc.returncode != 0:
        logger.error("whisper stderr: %s", stderr.decode(errors="replace"))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Whisper binary exited with error",
        )

    text = stdout.decode(errors="replace").strip()
    logger.info("Transcription complete: %d chars", len(text))
    return text
