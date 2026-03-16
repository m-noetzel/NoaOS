"""APNs HTTP/2 push notification service — iOS1.

Spec refs: SPEC.md §29.5 (Push Notifications), §29.6 (Approval Flow)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from noa.push.schemas import PushPayload

logger = logging.getLogger(__name__)

# Event types that should NOT trigger a push notification
_SILENT_EVENT_TYPES = frozenset({"approval_auto_approved"})

# Risk tiers that are silent when auto-approved
_SILENT_RISK_TIERS = frozenset({"low"})

APNS_URL = "https://api.push.apple.com/3/device"


@dataclass
class SendResult:
    """Result of an APNs send attempt."""

    success: bool
    expired: bool = False
    reason: str | None = None


class APNsService:
    """Sends push notifications via APNs HTTP/2.

    Parameters
    ----------
    key_id : str
        APNs auth key ID.
    team_id : str
        Apple Developer Team ID.
    key_path : str
        Path to the ``.p8`` private key file.
    bundle_id : str
        iOS app bundle identifier.
    """

    def __init__(
        self,
        *,
        key_id: str,
        team_id: str,
        key_path: str,
        bundle_id: str,
    ) -> None:
        self.key_id = key_id
        self.team_id = team_id
        self.key_path = key_path
        self.bundle_id = bundle_id
        self._http_client: object | None = None
        self._jwt_token: str | None = None
        self._jwt_issued_at: float = 0

    def initialize(self, http_client: object) -> None:
        """Set the HTTP/2 client. Must be called before ``send()``."""
        self._http_client = http_client

    # ------------------------------------------------------------------
    # JWT Auth
    # ------------------------------------------------------------------

    def _generate_jwt(self) -> str:
        """Generate a JWT for APNs authentication (ES256).

        Tokens are cached for up to 50 minutes (Apple allows 60 min).
        """
        now = time.time()
        if (
            self._jwt_token is not None
            and (now - self._jwt_issued_at) < 3000
        ):
            return self._jwt_token

        import jwt  # PyJWT

        key_data = Path(self.key_path).read_text()
        payload = {
            "iss": self.team_id,
            "iat": int(now),
        }
        token: str = jwt.encode(
            payload,
            key_data,
            algorithm="ES256",
            headers={"kid": self.key_id},
        )
        self._jwt_token = token
        self._jwt_issued_at = now
        return token

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send(
        self,
        *,
        device_token: str,
        notification_type: str,
        request_id: uuid.UUID,
        risk_tier: str,
    ) -> SendResult:
        """Send a push notification to the given device token.

        Returns a ``SendResult`` indicating success or failure.
        Handles APNs error codes (410 expired, 400 bad token) gracefully.
        """
        payload = PushPayload(
            notification_type=notification_type,
            request_id=request_id,
            risk_tier=risk_tier,
        )

        if self._http_client is None:
            logger.error("APNs HTTP client not initialised")
            return SendResult(success=False, reason="no_client")

        try:
            jwt_token = self._generate_jwt()
        except (OSError, ValueError, Exception):  # noqa: BLE001
            # _generate_jwt() can raise FileNotFoundError (bad key_path),
            # OSError (disk read failure), or PyJWT errors (invalid key).
            # We catch broadly here because PyJWT doesn't export a stable
            # base exception we can import without depending on its internals.
            logger.exception("Failed to generate APNs JWT")
            return SendResult(success=False, reason="jwt_error")

        try:
            response = await self._http_client.post(  # type: ignore[attr-defined]
                f"{APNS_URL}/{device_token}",
                json=payload.model_dump(mode="json"),
                headers={
                    "authorization": f"bearer {jwt_token}",
                    "apns-topic": self.bundle_id,
                    "apns-push-type": "alert",
                },
            )
        except Exception:  # noqa: BLE001
            # httpx.HTTPError is the base, but the HTTP/2 client may raise
            # transport-layer errors not derived from it (e.g. h2 protocol errors).
            logger.exception(
                "APNs send failed for device_token=%s", device_token
            )
            return SendResult(success=False, reason="transport_error")

        status_code = response.status_code

        if status_code == 200:
            return SendResult(success=True)

        body = (
            response.json()
            if callable(getattr(response, "json", None))
            else {}
        )
        reason = body.get("reason", "unknown")

        if status_code == 410:
            logger.warning(
                "Device token expired (410): token=%s reason=%s",
                device_token,
                reason,
            )
            return SendResult(success=False, expired=True, reason=reason)

        if status_code == 400:
            logger.warning(
                "Bad device token (400): token=%s reason=%s",
                device_token,
                reason,
            )
            return SendResult(success=False, reason=reason)

        logger.warning(
            "APNs returned %d for token=%s reason=%s",
            status_code,
            device_token,
            reason,
        )
        return SendResult(success=False, reason=reason)

    def should_notify(self, *, event_type: str, risk_tier: str) -> bool:
        """Determine whether a push notification should be sent.

        Low-risk auto-approved actions do NOT trigger push (SPEC.md §29.6).
        """
        silent = (
            event_type in _SILENT_EVENT_TYPES
            and risk_tier in _SILENT_RISK_TIERS
        )
        return not silent
