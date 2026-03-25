"""Thread endpoints — web client thread management."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.conversation import Conversation, Message
from noa.db.rls import set_domain_context

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


class CreateThreadRequest(BaseModel):
    """Request body for creating a thread."""

    title: str
    domain: Literal["private", "external"] = "external"


@router.get("")
async def list_threads(
    request: Request,
    privacy_mode: Literal["private", "external"] = Query(default="external"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List all threads for the authenticated user, filtered by domain.

    BE-C3: Only returns threads belonging to the requested domain so
    private threads are never exposed in external mode and vice versa.
    """
    rid = trace_id_ctx.get("")
    # RLS1: set domain context so Postgres RLS policies apply
    await set_domain_context(session, privacy_mode)

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
        .where(
            Conversation.user_id == user.user_id,
            Conversation.domain == privacy_mode,
        )
        .order_by(Conversation.created_at.desc())
        .limit(100)
    )
    rows = result.all()

    data = [
        {
            "id": str(row.Conversation.id),
            "title": row.Conversation.title,
            "message_count": row.message_count,
            "domain": row.Conversation.domain,
            "created_at": row.Conversation.created_at.isoformat(),
            # TODO: add updated_at to Conversation model (currently echoes created_at)
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
    """Create a new thread scoped to the specified domain."""
    rid = trace_id_ctx.get("")

    conversation = Conversation(
        user_id=user.user_id,
        title=body.title,
        domain=body.domain,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    return success_envelope(
        data={
            "id": str(conversation.id),
            "title": conversation.title,
            "domain": conversation.domain,
            "created_at": conversation.created_at.isoformat(),
            # TODO: add updated_at to Conversation model (currently echoes created_at)
            "updated_at": conversation.created_at.isoformat(),
        },
        trace_id=rid,
    )


@router.get("/{thread_id}/messages")
async def list_messages(
    thread_id: uuid.UUID,
    request: Request,
    privacy_mode: Literal["private", "external"] = Query(default="external"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List messages for a thread.

    BE-C3: Verifies the thread belongs to the requested domain before
    returning messages. Returns 403 on domain mismatch.
    """
    rid = trace_id_ctx.get("")
    # RLS1: set domain context so Postgres RLS policies apply
    await set_domain_context(session, privacy_mode)

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

    # Domain isolation check (BE-C3)
    if conversation.domain != privacy_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Thread {thread_id} belongs to domain '{conversation.domain}' "
                f"but request is in domain '{privacy_mode}'"
            ),
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


class UpdateThreadRequest(BaseModel):
    """Request body for renaming a thread."""

    title: str


@router.patch("/{thread_id}")
async def update_thread(
    thread_id: uuid.UUID,
    body: UpdateThreadRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a thread's title (UX-M3: inline rename).

    Only the title field is updateable. Returns the updated thread.
    Returns 404 if the thread does not belong to the authenticated user.
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

    title = body.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thread title cannot be empty",
        )
    if len(title) > 256:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thread title cannot exceed 256 characters",
        )

    conversation.title = title
    await session.commit()
    await session.refresh(conversation)

    return success_envelope(
        data={
            "id": str(conversation.id),
            "title": conversation.title,
            "domain": conversation.domain,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.created_at.isoformat(),
        },
        trace_id=rid,
    )


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: uuid.UUID,
    request: Request,
    privacy_mode: Literal["private", "external"] = Query(default="external"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Delete a thread by ID.

    iOS5 ThreadListView swipe-to-delete calls this endpoint.
    Returns 204-equivalent success envelope; thread and its messages are removed.
    BE-C3: Domain check prevents cross-domain deletion.
    """
    rid = trace_id_ctx.get("")
    # RLS1: set domain context so Postgres RLS policies apply
    await set_domain_context(session, privacy_mode)

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

    # BE-C3: Domain isolation — cannot delete a thread across domains
    if conversation.domain != privacy_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Thread {thread_id} belongs to domain '{conversation.domain}' "
                f"but request is in domain '{privacy_mode}'"
            ),
        )

    await session.delete(conversation)
    await session.commit()

    return success_envelope(data={"deleted": str(thread_id)}, trace_id=rid)
