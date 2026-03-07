"""Queue endpoints — stub for web client."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


@router.get("")
async def list_queue(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List queued items."""
    rid = trace_id_ctx.get("")
    return success_envelope(data=[], trace_id=rid)
