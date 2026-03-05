"""Chat endpoint — web client chat submission."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for chat submission."""

    message: str
    thread_id: str | None = None
    privacy_mode: str
    model: str
    provider: str
    temperature: float | None = None
    max_tokens: int | None = None


@router.post("/chat")
async def submit_chat(
    body: ChatRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Submit a chat message.

    Stub: returns a run_id. The real implementation will create a Run
    and start SSE streaming.
    """
    rid = trace_id_ctx.get("")
    run_id = str(uuid.uuid4())
    thread_id = body.thread_id or str(uuid.uuid4())
    return success_envelope(
        data={
            "run_id": run_id,
            "thread_id": thread_id,
        },
        trace_id=rid,
    )
