"""Device push-token registration endpoints — iOS1.

POST   /api/v1/devices/push-token  — register/update device token
DELETE /api/v1/devices/push-token  — unregister device token

Spec refs: SPEC.md §29.5 (Push Notifications)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.device_token import DevicePushToken
from noa.push.schemas import DeviceTokenRequest

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.post("/push-token")
async def register_push_token(
    body: DeviceTokenRequest,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Register or update a device push token for the authenticated user."""
    rid = trace_id_ctx.get("")
    user_id = user.user_id

    stmt = (
        pg_insert(DevicePushToken)
        .values(
            user_id=user_id,
            device_id=body.device_id,
            platform=body.platform,
            push_token=body.push_token,
        )
        .on_conflict_do_update(
            index_elements=["device_id"],
            set_={"push_token": body.push_token, "platform": body.platform},
        )
    )
    await session.execute(stmt)
    await session.commit()

    return success_envelope(
        data={"device_id": body.device_id, "status": "registered"},
        trace_id=rid,
    )


@router.delete("/push-token")
async def unregister_push_token(
    body: DeviceTokenRequest,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Remove a device push token for the authenticated user."""
    rid = trace_id_ctx.get("")
    user_id = user.user_id

    stmt = delete(DevicePushToken).where(
        DevicePushToken.user_id == user_id,
        DevicePushToken.device_id == body.device_id,
    )
    result = await session.execute(stmt)
    await session.commit()

    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found",
        )

    return success_envelope(
        data={"device_id": body.device_id, "status": "unregistered"},
        trace_id=rid,
    )
