"""Push notification schemas — iOS1.

Spec refs: SPEC.md §29.5 (Push Notifications)
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class DeviceTokenRequest(BaseModel):
    """Schema for device push-token registration requests."""

    device_id: str
    platform: str
    push_token: str


class PushPayload(BaseModel):
    """APNs push payload — restricted to non-private metadata only.

    Extra fields are forbidden to prevent private data leaking into
    push notifications (SPEC.md §29.5).
    """

    model_config = ConfigDict(extra="forbid")

    notification_type: str
    request_id: uuid.UUID
    risk_tier: str
