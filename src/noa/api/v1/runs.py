"""Run endpoints & SSE streaming — SPEC.md §22.4."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from noa.api.middleware import trace_id_ctx
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for streaming run events per §22.4.

    Clients subscribe to real-time events via Server-Sent Events.
    """
    rid = trace_id_ctx.get("")

    async def event_generator() -> Any:
        """Generate SSE events. Placeholder — real impl connects to event bus."""
        # Send an initial comment to establish the connection
        yield ": connected\n\n"
        # In production, this would poll or subscribe to new events
        # For now, yield nothing and keep connection alive
        try:
            while True:
                await asyncio.sleep(30)
                yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-ID": rid,
        },
    )
