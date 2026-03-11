"""Artifact endpoints — web client artifact downloads."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.artifact import Artifact
from noa.db.models.run import Run

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("")
async def list_artifacts(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List artifacts for the authenticated user."""
    rid = trace_id_ctx.get("")
    user_id = user.user_id
    # Join artifacts to runs so we can filter by user_id
    result = await session.execute(
        select(Artifact)
        .join(Run, Run.id == Artifact.run_id)
        .where(Run.user_id == user_id)
        .order_by(Artifact.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    artifacts = result.scalars().all()
    data = [
        {
            "id": str(a.id),
            "run_id": str(a.run_id),
            "type": a.type,
            "name": a.name,
            "mime_type": a.mime_type,
            "size_bytes": a.size_bytes,
            "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]
    return success_envelope(data=data, trace_id=rid)


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> FileResponse:
    """Download an artifact by ID — streams the file from storage_ref path."""
    user_id = user.user_id
    result = await session.execute(
        select(Artifact)
        .join(Run, Run.id == Artifact.run_id)
        .where(Artifact.id == artifact_id, Run.user_id == user_id)
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )
    path = Path(artifact.storage_ref)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact file not found on disk",
        )
    return FileResponse(
        path=str(path),
        media_type=artifact.mime_type,
        filename=artifact.name,
    )
