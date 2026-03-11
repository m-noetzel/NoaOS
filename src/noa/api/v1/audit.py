"""Audit log query and integrity verification endpoints — SPEC.md §28.1, §28.2."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.audit.schemas import AuditEntryRead
from noa.auth.middleware import AuthUser, require_auth

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/entries")
async def query_audit_entries(
    request: Request,
    trace_id: uuid.UUID = Query(..., description="Filter entries by trace_id"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Query audit entries by trace_id for debugging/compliance (§28.1)."""
    rid = trace_id_ctx.get("")

    from noa.api.app_state import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return success_envelope(data={"entries": []}, trace_id=rid)

    async with factory() as session:
        # AuditService expects a sync-style session; use run_sync for the query
        from sqlalchemy import select

        from noa.db.models.audit import AuditLog

        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.trace_id == trace_id)
            .order_by(AuditLog.timestamp)
        )
        entries = result.scalars().all()

    return success_envelope(
        data={
            "entries": [
                AuditEntryRead.model_validate(e).model_dump(mode="json")
                for e in entries
            ],
        },
        trace_id=rid,
    )


@router.post("/verify")
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
            select(AuditLog).order_by(AuditLog.timestamp, AuditLog.id)
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
