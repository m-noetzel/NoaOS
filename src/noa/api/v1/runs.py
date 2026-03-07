"""Run endpoints & SSE streaming — SPEC.md §22.4."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
async def list_runs(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List runs for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data={"events": []}, trace_id=rid)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for streaming run events per §22.4.

    Clients subscribe to real-time events via Server-Sent Events.
    Events include an ``id:`` field so clients can use ``Last-Event-ID``
    for reconnection replay.  Phase QC8 / M5.
    """
    rid = trace_id_ctx.get("")

    async def event_generator() -> Any:
        """Generate SSE events with id: fields for Last-Event-ID tracking."""
        event_counter = 0

        # Send an initial event with id field
        event_counter += 1
        yield f"id: {event_counter}\nevent: connected\ndata: connected\n\n"

        # In production, this would poll or subscribe to new events
        try:
            while True:
                await asyncio.sleep(30)
                event_counter += 1
                yield f"id: {event_counter}\n: keepalive\n\n"
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


@router.get("/{run_id}/events/replay")
async def replay_run_events(
    run_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
    after_event_id: int = 0,
) -> dict[str, Any]:
    """Replay events after a given event ID for SSE reconnection.

    Returns events that occurred after ``after_event_id``, enabling
    clients to catch up after a disconnection using ``Last-Event-ID``.
    Phase QC8 / M5.

    Args:
        run_id: The run UUID.
        request: FastAPI request.
        user: Authenticated user.
        after_event_id: Return events after this ID (0 = all).

    Returns:
        Envelope with list of events.
    """
    rid = trace_id_ctx.get("")
    # TODO: Query run_events table for events > after_event_id (M5 full implementation)
    # Currently returns empty — SSE events are not yet persisted to the event store
    return success_envelope(data={"events": []}, trace_id=rid)
