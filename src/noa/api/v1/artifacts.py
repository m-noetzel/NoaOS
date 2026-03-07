"""Artifact endpoints — web client artifact downloads."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("")
async def list_artifacts(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List artifacts for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data=[], trace_id=rid)


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> None:
    """Download an artifact by ID.

    TODO: Implement artifact storage lookup and file streaming.
    """
    raise HTTPException(status_code=404, detail="Artifact not found")
