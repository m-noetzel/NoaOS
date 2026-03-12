"""Thread endpoints — web client thread management."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.conversation import Conversation, Message

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


class CreateThreadRequest(BaseModel):
    """Request body for creating a thread."""

    title: str


@router.get("")
async def list_threads(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List all threads for the authenticated user."""
    rid = trace_id_ctx.get("")

    # Subquery for message count per thread
    msg_count_sub = (
        select(Message.thread_id, func.count().label("cnt"))
        .group_by(Message.thread_id)
        .subquery()
    )

    result = await session.execute(
        select(
            Conversation,
            func.coalesce(msg_count_sub.c.cnt, 0).label("message_count"),
        )
        .outerjoin(msg_count_sub, Conversation.id == msg_count_sub.c.thread_id)
        .where(Conversation.user_id == user.user_id)
        .order_by(Conversation.created_at.desc())
        .limit(100)
    )
    rows = result.all()

    data = [
        {
            "id": str(row.Conversation.id),
            "title": row.Conversation.title,
            "message_count": row.message_count,
            "created_at": row.Conversation.created_at.isoformat(),
            "updated_at": row.Conversation.created_at.isoformat(),
        }
        for row in rows
    ]

    return success_envelope(data=data, trace_id=rid)


@router.post("")
async def create_thread(
    body: CreateThreadRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a new thread."""
    rid = trace_id_ctx.get("")

    conversation = Conversation(
        user_id=user.user_id,
        title=body.title,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    return success_envelope(
        data={
            "id": str(conversation.id),
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.created_at.isoformat(),
        },
        trace_id=rid,
    )


@router.get("/{thread_id}/messages")
async def list_messages(
    thread_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List messages for a thread."""
    rid = trace_id_ctx.get("")

    # Verify thread exists and belongs to the authenticated user
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == thread_id,
            Conversation.user_id == user.user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread {thread_id} not found",
        )

    msg_result = await session.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.timestamp.asc())
    )
    rows = msg_result.scalars().all()

    data = [
        {
            "id": str(row.id),
            "thread_id": str(row.thread_id),
            "role": row.role,
            "content": row.content,
            "created_at": row.timestamp.isoformat(),
        }
        for row in rows
    ]

    return success_envelope(data=data, trace_id=rid)


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Delete a thread by ID.

    iOS5 ThreadListView swipe-to-delete calls this endpoint.
    Returns 204-equivalent success envelope; thread and its messages are removed.
    """
    rid = trace_id_ctx.get("")

    result = await session.execute(
        select(Conversation).where(
            Conversation.id == thread_id,
            Conversation.user_id == user.user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread {thread_id} not found",
        )

    await session.delete(conversation)
    await session.commit()

    return success_envelope(data={"deleted": str(thread_id)}, trace_id=rid)
