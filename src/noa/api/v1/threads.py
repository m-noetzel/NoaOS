"""Thread endpoints — web client thread management."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


class CreateThreadRequest(BaseModel):
    """Request body for creating a thread."""

    title: str


@router.get("")
async def list_threads(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List all threads for the authenticated user."""
    rid = trace_id_ctx.get("")
    # Stub: return mock threads
    return success_envelope(
        data=[
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "title": "Welcome thread",
                "created_at": "2026-03-05T00:00:00Z",
                "updated_at": "2026-03-05T00:00:00Z",
                "message_count": 0,
            },
        ],
        trace_id=rid,
    )


@router.post("")
async def create_thread(
    body: CreateThreadRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Create a new thread."""
    rid = trace_id_ctx.get("")
    thread_id = str(uuid.uuid4())
    return success_envelope(
        data={
            "id": thread_id,
            "title": body.title,
        },
        trace_id=rid,
    )


@router.get("/{thread_id}/messages")
async def list_messages(
    thread_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List messages for a thread."""
    rid = trace_id_ctx.get("")
    return success_envelope(data=[], trace_id=rid)
