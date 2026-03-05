"""Memory fact endpoints — web client memory management."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class UpdateFactRequest(BaseModel):
    """Request body for updating a fact."""

    fact: str


@router.get("/facts")
async def list_facts(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List memory facts for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data={"facts": []}, trace_id=rid)


@router.post("/facts/{fact_id}/approve")
async def approve_fact(
    fact_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Approve a memory fact."""
    rid = trace_id_ctx.get("")
    return success_envelope(
        data={"id": str(fact_id), "status": "approved"},
        trace_id=rid,
    )


@router.post("/facts/{fact_id}/update")
async def update_fact(
    fact_id: uuid.UUID,
    body: UpdateFactRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Update a memory fact's text."""
    rid = trace_id_ctx.get("")
    return success_envelope(
        data={"id": str(fact_id), "status": "updated"},
        trace_id=rid,
    )


@router.delete("/facts/{fact_id}")
async def delete_fact(
    fact_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Delete a memory fact."""
    rid = trace_id_ctx.get("")
    return success_envelope(
        data={"id": str(fact_id), "status": "deleted"},
        trace_id=rid,
    )
