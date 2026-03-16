"""Memory fact endpoints — web client memory management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth

if TYPE_CHECKING:
    from noa.private_worker.memory_store import MemoryStore

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class CreateFactRequest(BaseModel):
    """Request body for creating a fact manually."""

    fact: str
    category: str = "personal_info"


class UpdateFactRequest(BaseModel):
    """Request body for updating a fact."""

    fact: str


def _get_memory_store() -> MemoryStore | None:
    from noa.api.app_state import get_memory_store

    return get_memory_store()


@router.get("/facts")
async def list_facts(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List memory facts for the authenticated user."""
    rid = trace_id_ctx.get("")
    store = _get_memory_store()
    if store is None:
        return success_envelope(data=[], trace_id=rid)
    facts = store.list_all(user_id=str(user.user_id))
    return success_envelope(data=facts, trace_id=rid)


@router.post("/facts")
async def create_fact(
    body: CreateFactRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Create a memory fact manually (auto-approved)."""
    from noa.private_worker.memory_store import VALID_CATEGORIES

    rid = trace_id_ctx.get("")
    store = _get_memory_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory store unavailable",
        )
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
        )
    fact_id = store.store(
        fact=body.fact,
        category=body.category,
        embedding=[],
        source_thread_id="manual",
        auto_extracted=False,
        user_id=str(user.user_id),
    )
    if fact_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate fact — this memory already exists",
        )
    return success_envelope(
        data={"id": fact_id, "status": "approved"}, trace_id=rid
    )


@router.post("/facts/{fact_id}/approve")
async def approve_fact(
    fact_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Approve a memory fact."""
    rid = trace_id_ctx.get("")
    store = _get_memory_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory store unavailable",
        )
    updated = store.update_status(str(fact_id), "approved", user_id=str(user.user_id))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact {fact_id} not found",
        )
    return success_envelope(
        data={"id": str(fact_id), "status": "approved"}, trace_id=rid
    )


@router.post("/facts/{fact_id}/update")
async def update_fact(
    fact_id: uuid.UUID,
    body: UpdateFactRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Update a memory fact's text."""
    rid = trace_id_ctx.get("")
    store = _get_memory_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory store unavailable",
        )
    existing = store.get_by_id(str(fact_id), user_id=str(user.user_id))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact {fact_id} not found",
        )
    existing["fact"] = body.fact
    store.persist(str(fact_id))
    return success_envelope(
        data={"id": str(fact_id), "status": "updated"}, trace_id=rid
    )


@router.delete("/facts/{fact_id}")
async def delete_fact(
    fact_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Delete a memory fact."""
    rid = trace_id_ctx.get("")
    store = _get_memory_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory store unavailable",
        )
    deleted = store.delete(str(fact_id), user_id=str(user.user_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact {fact_id} not found",
        )
    return success_envelope(
        data={"id": str(fact_id), "status": "deleted"}, trace_id=rid
    )
