"""Audit log query and integrity verification endpoints — SPEC.md §28.1, §28.2."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.audit.schemas import AuditEntryRead
from noa.auth.middleware import AuthUser, require_auth

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/entries")
async def query_audit_entries(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    trace_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    domain: str | None = Query(default=None),  # noqa: B008
    tool_name: str | None = Query(default=None),  # noqa: B008
    privacy_classification: str | None = Query(default=None),  # noqa: B008
    since: datetime | None = Query(default=None, description="ISO-8601 lower bound"),  # noqa: B008
    until: datetime | None = Query(default=None, description="ISO-8601 upper bound"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Query audit entries with optional filters — paginated (§28.1)."""
    rid = trace_id_ctx.get("")

    from noa.api.app_state import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return success_envelope(
            data={"entries": [], "total": 0, "limit": limit, "offset": offset},
            trace_id=rid,
        )

    from sqlalchemy import func, select

    from noa.db.models.audit import AuditLog

    async with factory() as session:
        q = select(AuditLog).where(AuditLog.user_id == user.user_id)

        if trace_id is not None:
            q = q.where(AuditLog.trace_id == trace_id)
        if domain is not None:
            q = q.where(AuditLog.domain == domain)
        if tool_name is not None:
            q = q.where(AuditLog.tool_name == tool_name)
        if privacy_classification is not None:
            q = q.where(AuditLog.privacy_classification == privacy_classification)
        if since is not None:
            q = q.where(AuditLog.timestamp >= since)
        if until is not None:
            q = q.where(AuditLog.timestamp <= until)

        count_q = select(func.count()).select_from(q.subquery())
        total_result = await session.execute(count_q)
        total = total_result.scalar_one()

        q = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
        result = await session.execute(q)
        entries = result.scalars().all()

    return success_envelope(
        data={
            "entries": [
                AuditEntryRead.model_validate(e).model_dump(mode="json")
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        trace_id=rid,
    )


@router.get("/verify")
async def verify_chain_endpoint(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Verify hash chain integrity of the audit log (§28.2)."""
    rid = trace_id_ctx.get("")

    from noa.api.app_state import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return success_envelope(
            data={"valid": True, "entries_checked": 0, "error": "no database"},
            trace_id=rid,
        )

    from sqlalchemy import select

    from noa.db.models.audit import AuditLog

    async with factory() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user.user_id)
            .order_by(AuditLog.timestamp, AuditLog.id)
        )
        entries = list(result.scalars().all())

    # Verify chain in-process (chain verification is CPU-only, no DB needed)
    import hashlib

    valid = True
    broken_at: str | None = None
    for i, entry in enumerate(entries):
        if i == 0:
            if entry.previous_entry_hash is not None:
                valid = False
                broken_at = str(entry.id)
                break
        else:
            prev = entries[i - 1]
            expected = hashlib.sha256(
                prev.hash_chain_data().encode()
            ).hexdigest()
            if entry.previous_entry_hash != expected:
                valid = False
                broken_at = str(entry.id)
                break

    return success_envelope(
        data={
            "valid": valid,
            "entries_checked": len(entries),
            "broken_at_entry_id": broken_at,
        },
        trace_id=rid,
    )


@router.get("/export")
async def export_audit_entries(
    request: Request,
    domain: str | None = Query(default=None),  # noqa: B008
    tool_name: str | None = Query(default=None),  # noqa: B008
    privacy_classification: str | None = Query(default=None),  # noqa: B008
    since: datetime | None = Query(default=None),  # noqa: B008
    until: datetime | None = Query(default=None),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> Response:
    """Export audit entries as JSON file download (§28.1)."""
    from noa.api.app_state import get_session_factory

    factory = get_session_factory()

    entries_out: list[dict[str, Any]] = []

    if factory is not None:
        from sqlalchemy import select

        from noa.db.models.audit import AuditLog

        async with factory() as session:
            q = select(AuditLog).where(AuditLog.user_id == user.user_id)

            if domain is not None:
                q = q.where(AuditLog.domain == domain)
            if tool_name is not None:
                q = q.where(AuditLog.tool_name == tool_name)
            if privacy_classification is not None:
                q = q.where(AuditLog.privacy_classification == privacy_classification)
            if since is not None:
                q = q.where(AuditLog.timestamp >= since)
            if until is not None:
                q = q.where(AuditLog.timestamp <= until)

            q = q.order_by(AuditLog.timestamp.desc())
            result = await session.execute(q)
            entries = result.scalars().all()

        entries_out = [
            AuditEntryRead.model_validate(e).model_dump(mode="json")
            for e in entries
        ]

    payload = json.dumps(entries_out, indent=2, default=str)
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="audit_export.json"',
        },
    )
