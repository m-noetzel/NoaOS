"""Queue endpoints — real DB queries for web client."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth
from noa.db.models.task_queue import TaskQueue

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


@router.get("")
async def list_queue(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List queued and in-progress tasks."""
    rid = trace_id_ctx.get("")
    result = await session.execute(
        select(TaskQueue)
        .where(TaskQueue.status.in_(["queued", "processing"]))
        .order_by(TaskQueue.queued_at.desc())
        .limit(100)
    )
    tasks = result.scalars().all()
    data = [
        {
            "id": str(t.id),
            "task_type": t.task_type,
            "status": t.status,
            "retry_count": t.retry_count,
            "queued_at": t.queued_at.isoformat(),
            "timeout_at": t.timeout_at.isoformat() if t.timeout_at else None,
        }
        for t in tasks
    ]
    return success_envelope(data=data, trace_id=rid)
