"""Fire-and-forget async push notification helper — iOS1.

Spec refs: SPEC.md §29.5 (Push Notifications)

Called from sync service hooks (ApprovalService, RunService) via
asyncio.ensure_future() to actually dispatch APNs pushes.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


async def send_push_to_user(
    *,
    user_id: uuid.UUID,
    notification_type: str,
    request_id: uuid.UUID,
    risk_tier: str,
) -> None:
    """Look up all device tokens for *user_id* and send a push notification.

    Runs as a fire-and-forget asyncio task — failures are logged, not raised.
    """
    try:
        from sqlalchemy import select

        from noa.api.app_state import get_apns_service, get_session_factory
        from noa.db.models.device_token import DevicePushToken

        apns = get_apns_service()
        if apns is None:
            return

        sf = get_session_factory()
        if sf is None:
            return

        async with sf() as session:
            result = await session.execute(
                select(DevicePushToken).where(DevicePushToken.user_id == user_id)
            )
            tokens = result.scalars().all()

        for token in tokens:
            send_result = await apns.send(
                device_token=token.push_token,
                notification_type=notification_type,
                request_id=request_id,
                risk_tier=risk_tier,
            )
            if not send_result.success:
                logger.warning(
                    "APNs send failed: user=%s token=...%s reason=%s expired=%s",
                    user_id,
                    token.push_token[-6:],
                    send_result.reason,
                    send_result.expired,
                )
    except Exception:  # noqa: BLE001
        logger.warning("send_push_to_user failed", exc_info=True)
