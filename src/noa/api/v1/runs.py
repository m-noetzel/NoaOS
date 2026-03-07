"""Run endpoints & SSE streaming — SPEC.md §22.4."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth
from noa.api.deps import get_db_session
from noa.db.models.run import RunEvent

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
    db: Any = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Replay events after a given event ID for SSE reconnection.

    Queries the ``run_events`` table for events belonging to the run,
    ordered by timestamp, enabling clients to catch up after a
    disconnection using ``Last-Event-ID``.  Resolves M5.

    Args:
        run_id: The run UUID.
        request: FastAPI request.
        user: Authenticated user.
        after_event_id: Return events after this sequence number (0 = all).
        db: Database session.

    Returns:
        Envelope with list of events.
    """
    rid = trace_id_ctx.get("")

    stmt = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(RunEvent.timestamp)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Skip events up to after_event_id (1-based sequence index)
    events = [
        {
            "id": str(row.id),
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat(),
            "payload": row.payload,
        }
        for idx, row in enumerate(rows, start=1)
        if idx > after_event_id
    ]

    return success_envelope(data={"events": events}, trace_id=rid)
