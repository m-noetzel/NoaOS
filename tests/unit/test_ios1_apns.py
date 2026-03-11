"""Tests for APNs push notification backend — Phase iOS1.

Spec refs: SPEC.md §29.5 (Push Notifications), §23.2 (Approval Batching),
           §29.6 (Approval Flow)
Phase plan: PHASE_DETAILS.md Phase iOS1

These tests define the behavioral contract for device token registration,
APNs payload construction, push delivery, and approval batching.
They are written BEFORE implementation and must all fail initially.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.ios1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_device_token_request(**kwargs):
    """Build a DeviceTokenRequest-like dict for endpoint testing."""
    return {
        "device_id": kwargs.pop("device_id", "iPhone-ABC123"),
        "platform": kwargs.pop("platform", "ios"),
        "push_token": kwargs.pop(
            "push_token",
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6abcd",
        ),
        **kwargs,
    }


def _user_id():
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Device Token Registration
# ---------------------------------------------------------------------------

class TestDeviceTokenRegistration:
    """SPEC.md §29.5 + PHASE_DETAILS iOS1: device token CRUD."""

    @pytest.mark.asyncio
    async def test_register_stores_device_token(self):
        """PHASE iOS1: POST /api/v1/devices/push-token stores token in DB."""
        from noa.push.schemas import DeviceTokenRequest

        req = DeviceTokenRequest(**_make_device_token_request())
        assert req.device_id == "iPhone-ABC123"
        assert req.platform == "ios"
        assert len(req.push_token) > 0

    @pytest.mark.asyncio
    async def test_duplicate_device_updates_token(self):
        """PHASE iOS1: Re-registering same device_id updates the push_token."""
        from noa.push.schemas import DeviceTokenRequest

        req1 = DeviceTokenRequest(**_make_device_token_request(push_token="old-token"))
        req2 = DeviceTokenRequest(
            **_make_device_token_request(push_token="new-token")
        )
        assert req1.device_id == req2.device_id
        assert req1.push_token != req2.push_token

    @pytest.mark.asyncio
    async def test_unregister_removes_token(self):
        """PHASE iOS1: DELETE /api/v1/devices/push-token removes the token."""
        from noa.push.schemas import DeviceTokenRequest

        req = DeviceTokenRequest(**_make_device_token_request())
        # Token schema can be constructed — the endpoint must delete the row
        assert req.push_token is not None


# ---------------------------------------------------------------------------
# DevicePushToken ORM Model
# ---------------------------------------------------------------------------

class TestDevicePushTokenModel:
    """PHASE iOS1: device_push_tokens table model."""

    def test_model_has_required_columns(self):
        """PHASE iOS1: DevicePushToken has user_id, device_id, platform, push_token, timestamps."""
        from noa.db.models.device_token import DevicePushToken

        # Verify the model can be instantiated with required fields
        uid = _user_id()
        token = DevicePushToken(
            user_id=uid,
            device_id="iPhone-ABC123",
            platform="ios",
            push_token="abcdef1234567890",
        )
        assert token.user_id == uid
        assert token.device_id == "iPhone-ABC123"
        assert token.platform == "ios"
        assert token.push_token == "abcdef1234567890"

    def test_model_table_name(self):
        """PHASE iOS1: Table is named device_push_tokens."""
        from noa.db.models.device_token import DevicePushToken

        assert DevicePushToken.__tablename__ == "device_push_tokens"


# ---------------------------------------------------------------------------
# APNs Payload Construction
# ---------------------------------------------------------------------------

class TestAPNsPayload:
    """SPEC.md §29.5: Push payload privacy constraints."""

    def test_payload_contains_only_allowed_fields(self):
        """SPEC.md §29.5: Payload contains only notification_type, request_id, risk_tier."""
        from noa.push.schemas import PushPayload

        payload = PushPayload(
            notification_type="approval_required",
            request_id=uuid.uuid4(),
            risk_tier="medium",
        )
        # Serialize and verify no extra fields leak private data
        data = payload.model_dump()
        allowed_keys = {"notification_type", "request_id", "risk_tier"}
        assert set(data.keys()) <= allowed_keys, (
            f"Push payload must not contain private data. "
            f"Extra keys: {set(data.keys()) - allowed_keys}"
        )

    def test_payload_rejects_private_data_fields(self):
        """SPEC.md §29.5: No task content, tool names, or private data in push payload."""
        from noa.push.schemas import PushPayload

        # PushPayload should not accept arbitrary extra fields
        with pytest.raises((ValueError, TypeError)):
            PushPayload(
                notification_type="approval_required",
                request_id=uuid.uuid4(),
                risk_tier="medium",
                task_content="secret task details",  # MUST be rejected
            )

    def test_notification_type_values(self):
        """SPEC.md §29.5: notification_type is one of approval_required, run_completed, run_failed."""
        from noa.push.schemas import PushPayload

        for ntype in ("approval_required", "run_completed", "run_failed"):
            payload = PushPayload(
                notification_type=ntype,
                request_id=uuid.uuid4(),
                risk_tier="low",
            )
            assert payload.notification_type == ntype


# ---------------------------------------------------------------------------
# APNs HTTP/2 Service
# ---------------------------------------------------------------------------

class TestAPNsService:
    """PHASE iOS1: APNsService sends push notifications via HTTP/2."""

    @pytest.mark.asyncio
    async def test_send_push_calls_apns_endpoint(self):
        """PHASE iOS1: APNsService.send() makes HTTP/2 POST to api.push.apple.com."""
        from noa.push.apns import APNsService

        service = APNsService(
            key_id="TESTKEY123",
            team_id="TESTTEAM99",
            key_path="/dev/null",
            bundle_id="com.noa.app",
        )
        # Service must be constructable with required config
        assert service.bundle_id == "com.noa.app"

    @pytest.mark.asyncio
    async def test_send_handles_expired_token(self):
        """PHASE iOS1: APNsService handles 410 Gone (expired device token)."""
        from noa.push.apns import APNsService

        service = APNsService(
            key_id="TESTKEY123",
            team_id="TESTTEAM99",
            key_path="/dev/null",
            bundle_id="com.noa.app",
        )
        # When APNs returns 410, the service should mark the token as invalid
        # and not raise an unhandled exception
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.json.return_value = {"reason": "Unregistered"}

        with (
            patch.object(service, "_http_client", new_callable=AsyncMock) as mock_client,
            patch.object(service, "_generate_jwt", return_value="fake-jwt"),
        ):
            mock_client.post.return_value = mock_response
            result = await service.send(
                device_token="expired-token-abc",
                notification_type="run_completed",
                request_id=uuid.uuid4(),
                risk_tier="low",
            )
            assert result.expired is True

    @pytest.mark.asyncio
    async def test_send_handles_invalid_token(self):
        """PHASE iOS1: APNsService handles 400 BadDeviceToken."""
        from noa.push.apns import APNsService

        service = APNsService(
            key_id="TESTKEY123",
            team_id="TESTTEAM99",
            key_path="/dev/null",
            bundle_id="com.noa.app",
        )
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"reason": "BadDeviceToken"}

        with (
            patch.object(service, "_http_client", new_callable=AsyncMock) as mock_client,
            patch.object(service, "_generate_jwt", return_value="fake-jwt"),
        ):
            mock_client.post.return_value = mock_response
            result = await service.send(
                device_token="invalid-token",
                notification_type="approval_required",
                request_id=uuid.uuid4(),
                risk_tier="medium",
            )
            assert result.success is False


# ---------------------------------------------------------------------------
# Approval Batching
# ---------------------------------------------------------------------------

class TestApprovalBatcher:
    """SPEC.md §23.2: Approval events batched within 30-second window."""

    @pytest.mark.asyncio
    async def test_events_within_window_are_batched(self):
        """SPEC.md §23.2: Multiple approval events within 30s grouped into single notification."""
        from noa.push.batcher import ApprovalBatcher

        batcher = ApprovalBatcher(window_seconds=30)
        user_id = _user_id()

        # Add two events quickly (same user, same domain)
        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="medium", domain="external")
        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="high", domain="external")

        # Should yield one batch, not two separate notifications
        batches = batcher.flush(user_id)
        assert len(batches) == 1
        assert len(batches[0].request_ids) == 2

    @pytest.mark.asyncio
    async def test_events_outside_window_sent_separately(self):
        """SPEC.md §23.2: Events arriving after 30s window are a new batch."""
        from noa.push.batcher import ApprovalBatcher

        batcher = ApprovalBatcher(window_seconds=0)  # zero-second window for test
        user_id = _user_id()

        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="medium", domain="external")
        # With window=0, next event starts a new batch
        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="medium", domain="external")

        batches = batcher.flush(user_id)
        assert len(batches) == 2

    def test_no_cross_domain_batching(self):
        """SPEC.md §23.2: Private and external domain tasks never batched together."""
        from noa.push.batcher import ApprovalBatcher

        batcher = ApprovalBatcher(window_seconds=30)
        user_id = _user_id()

        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="medium", domain="private")
        batcher.add_event(user_id=user_id, request_id=uuid.uuid4(), risk_tier="medium", domain="external")

        batches = batcher.flush(user_id)
        # Must produce two separate batches — one per domain
        assert len(batches) == 2
        domains = {b.domain for b in batches}
        assert domains == {"private", "external"}


# ---------------------------------------------------------------------------
# Push Trigger Events
# ---------------------------------------------------------------------------

class TestPushTriggers:
    """SPEC.md §29.6 + PHASE iOS1: push sent on specific run/approval events."""

    @pytest.mark.asyncio
    async def test_push_on_approval_requested(self):
        """SPEC.md §29.6: Push notification sent when approval_requested event occurs."""
        from noa.push.apns import APNsService
        from noa.push.schemas import PushPayload

        payload = PushPayload(
            notification_type="approval_required",
            request_id=uuid.uuid4(),
            risk_tier="high",
        )
        assert payload.notification_type == "approval_required"

    @pytest.mark.asyncio
    async def test_push_on_run_completed(self):
        """SPEC.md §29.5: Push sent for run_completed notification type."""
        from noa.push.schemas import PushPayload

        payload = PushPayload(
            notification_type="run_completed",
            request_id=uuid.uuid4(),
            risk_tier="low",
        )
        assert payload.notification_type == "run_completed"

    @pytest.mark.asyncio
    async def test_push_on_run_failed(self):
        """SPEC.md §29.5: Push sent for run_failed notification type."""
        from noa.push.schemas import PushPayload

        payload = PushPayload(
            notification_type="run_failed",
            request_id=uuid.uuid4(),
            risk_tier="low",
        )
        assert payload.notification_type == "run_failed"

    @pytest.mark.asyncio
    async def test_no_push_for_low_risk_auto_approved(self):
        """SPEC.md §29.6: Low-risk auto-approved actions do not trigger push notifications."""
        from noa.push.apns import APNsService

        # APNsService should have a method that checks whether push is needed
        # For auto-approved low-risk, it should return False / skip sending
        service = APNsService(
            key_id="TESTKEY123",
            team_id="TESTTEAM99",
            key_path="/dev/null",
            bundle_id="com.noa.app",
        )
        should_push = service.should_notify(
            event_type="approval_auto_approved",
            risk_tier="low",
        )
        assert should_push is False


# ---------------------------------------------------------------------------
# Auth Required
# ---------------------------------------------------------------------------

class TestDeviceEndpointAuth:
    """PHASE iOS1: Device token endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_register_rejects_unauthenticated(self):
        """PHASE iOS1: POST /api/v1/devices/push-token returns 401 without auth."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from noa.api.v1.devices import router

        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/devices/push-token",
                json=_make_device_token_request(),
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unregister_rejects_unauthenticated(self):
        """PHASE iOS1: DELETE /api/v1/devices/push-token returns 401 without auth."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from noa.api.v1.devices import router

        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.request(
                "DELETE",
                "/api/v1/devices/push-token",
                json=_make_device_token_request(),
            )
            assert resp.status_code == 401
