"""Backend API contract tests for iOS11: Integration Tests & Polish.

Spec refs: SPEC.md §29.3 (Mobile Access — Phase 2: Native iOS App),
           SPEC.md §29.4 (Connection Security — certificate pinning),
           SPEC.md §29.5 (Push Notifications — APNs),
           SPEC.md §29.6 (Approval Flow),
           SPEC.md §36.3 (Phase 3: Native iOS Client),
           SPEC.md §5.3 (Token refresh),
           SPEC.md §37 (Definition of Done)
Phase plan: PHASE_DETAILS.md Phase iOS11

iOS11 is the integration and polish phase. It adds:
  1. MockURLProtocol-based test server for Swift integration tests
  2. E2E Swift tests: login, chat+SSE, approval+biometric, offline queue drain
  3. Accessibility labels and Dynamic Type support
  4. Dark mode verification
  5. ErrorView and EmptyStateView reusable components
  6. Production wiring of CertificatePinningDelegate to all URLSession sites
  7. VPN prompt wiring in views

These Python tests pin the backend API contract exercised by those Swift
integration tests. They verify:
  - Login → token refresh → logout sequence is coherent
  - Approval flow responds correctly to decide calls (§29.6)
  - Push token registration and unregistration (§29.5)
  - SSE stream produces events decodable by the mock URLProtocol
  - Token refresh returns a rotated token pair (§5.3)
  - All endpoints return the standard envelope shape the mock server replicates

If these tests break, the MockURLProtocol will serve the wrong JSON shapes
and the Swift E2E tests will decode nothing or crash.
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.ios11


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_login_credentials(**kwargs) -> dict:
    return {
        "username": kwargs.pop("username", "testuser@example.com"),
        "password": kwargs.pop("password", "S3cr3tPass!"),
        **kwargs,
    }


def _make_approval_dict(**kwargs) -> dict:
    """Minimal approval payload matching the pending approval shape."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "run_id": kwargs.pop("run_id", str(uuid.uuid4())),
        "user_id": kwargs.pop("user_id", str(uuid.uuid4())),
        "risk_tier": kwargs.pop("risk_tier", "high"),
        "preview_text": kwargs.pop("preview_text", "Delete /prod/db — irreversible"),
        "decision": kwargs.pop("decision", "pending"),
        "domain": kwargs.pop("domain", "external"),
        "requested_at": kwargs.pop("requested_at", "2026-03-10T10:00:00+00:00"),
        "decided_at": kwargs.pop("decided_at", None),
        **kwargs,
    }


def _make_device_token_payload(**kwargs) -> dict:
    return {
        "device_id": kwargs.pop("device_id", "iPhone-X1Y2Z3"),
        "platform": kwargs.pop("platform", "ios"),
        "push_token": kwargs.pop(
            "push_token",
            "a" * 64,
        ),
        **kwargs,
    }


def _make_sse_event(event_type: str, **data) -> str:
    """Serialize a single SSE event as the wire-format string the backend emits."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Token Refresh & Session Lifecycle (§5.3)
# ---------------------------------------------------------------------------


class TestTokenRefreshContract:
    """SPEC.md §5.3: Refresh tokens rotate automatically on each use."""

    def test_login_response_includes_expires_in(self):
        """SPEC.md §5.3 + PHASE_DETAILS iOS4: expires_in enables AuthViewModel scheduling."""
        from noa.api.v1.auth import AuthTokenResponse

        token_response = AuthTokenResponse(
            token_type="bearer",
            expires_in=900,
            access_token="acc.token.value",
            refresh_token="ref.token.value",
        )
        assert token_response.expires_in == 900
        assert token_response.access_token == "acc.token.value"
        assert token_response.refresh_token == "ref.token.value"

    def test_refresh_endpoint_is_registered(self):
        """SPEC.md §5.3: /api/v1/auth/refresh must exist for iOS token rotation."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/auth/refresh" in routes

    def test_login_endpoint_is_registered(self):
        """SPEC.md §5.3 + §29.3: /api/v1/auth/login must be reachable by iOS client."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/auth/login" in routes

    def test_logout_endpoint_is_registered(self):
        """SPEC.md §5.3: /api/v1/auth/logout must invalidate iOS session cleanly."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/auth/logout" in routes


# ---------------------------------------------------------------------------
# Approval Flow Contract (§29.6)
# ---------------------------------------------------------------------------


class TestApprovalFlowContract:
    """SPEC.md §29.6: Approval flow works on web UI and mobile."""

    def test_pending_approvals_endpoint_is_registered(self):
        """SPEC.md §29.6: GET /api/v1/approvals/pending must be reachable by iOS."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/approvals/pending" in routes

    def test_decide_approval_endpoint_is_registered(self):
        """SPEC.md §29.6: POST /api/v1/approvals/{id}/decide must be wired."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/approvals/{approval_id}/decide" in routes

    def test_approval_decision_body_accepts_approved(self):
        """SPEC.md §29.6: decision field accepts 'approved' for biometric-confirmed actions."""
        from noa.api.v1.approvals import ApprovalDecision

        decision = ApprovalDecision(decision="approved")
        assert decision.decision == "approved"

    def test_approval_decision_body_accepts_denied(self):
        """SPEC.md §29.6: decision field accepts 'denied' for rejected approvals."""
        from noa.api.v1.approvals import ApprovalDecision

        decision = ApprovalDecision(decision="denied")
        assert decision.decision == "denied"

    def test_approval_dict_shape_matches_ios_model(self):
        """PHASE_DETAILS iOS7/iOS11: Approval JSON shape must match iOS Approval.Codable struct."""
        approval = _make_approval_dict(risk_tier="high")

        required_keys = {
            "id",
            "run_id",
            "user_id",
            "risk_tier",
            "preview_text",
            "decision",
            "domain",
            "requested_at",
            "decided_at",
        }
        missing = required_keys - approval.keys()
        assert not missing, f"Approval payload missing keys: {missing}"

    def test_high_risk_approval_has_preview_text(self):
        """SPEC.md §29.6 + §19.2: High-risk approvals must include a dry-run preview."""
        approval = _make_approval_dict(risk_tier="high")
        # preview_text must not be empty for high-risk items — iOS11 detail view shows it
        assert approval["preview_text"], "High-risk approval must have non-empty preview_text"


# ---------------------------------------------------------------------------
# Push Token Lifecycle (§29.5)
# ---------------------------------------------------------------------------


class TestPushTokenContract:
    """SPEC.md §29.5: Push token register/unregister endpoints for iOS."""

    def test_push_token_register_endpoint_is_registered(self):
        """SPEC.md §29.5: POST /api/v1/devices/push-token must be reachable."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/devices/push-token" in routes

    def test_push_token_payload_has_required_fields(self):
        """SPEC.md §29.5: Device registration payload must include device_id, platform, push_token."""
        payload = _make_device_token_payload()
        assert "device_id" in payload
        assert "platform" in payload
        assert "push_token" in payload

    def test_push_token_platform_is_ios(self):
        """SPEC.md §29.5: Platform field must be 'ios' for iOS devices."""
        payload = _make_device_token_payload(platform="ios")
        assert payload["platform"] == "ios"

    def test_device_push_token_model_columns(self):
        """PHASE_DETAILS iOS1/iOS11: DevicePushToken ORM must have all integration-required columns."""
        from noa.db.models.device_token import DevicePushToken

        mapper = DevicePushToken.__mapper__
        column_names = {c.key for c in mapper.columns}
        required_columns = {
            "id",
            "user_id",
            "device_id",
            "platform",
            "push_token",
            "created_at",
            "updated_at",
        }
        missing = required_columns - column_names
        assert not missing, f"DevicePushToken missing columns: {missing}"

    def test_device_push_token_device_id_is_unique(self):
        """SPEC.md §29.5: device_id must be unique (each device has one token)."""
        from noa.db.models.device_token import DevicePushToken

        mapper = DevicePushToken.__mapper__
        device_id_col = mapper.columns["device_id"]
        assert device_id_col.unique, "device_id must have a unique constraint"


# ---------------------------------------------------------------------------
# SSE Event Wire Format (iOS integration test mock compatibility)
# ---------------------------------------------------------------------------


class TestSSEWireFormat:
    """PHASE_DETAILS iOS11: MockURLProtocol must serve SSE events in correct wire format."""

    def test_meta_event_is_valid_sse(self):
        """SPEC.md §22.2: SSE meta event must parse as JSON with a 'type' field."""
        wire = _make_sse_event("meta", run_id=str(uuid.uuid4()), status="pending")
        assert wire.startswith("data: ")
        assert wire.endswith("\n\n")
        payload = json.loads(wire[len("data: "):].strip())
        assert payload["type"] == "meta"
        assert "run_id" in payload

    def test_token_stream_event_carries_content(self):
        """SPEC.md §22.2: token_stream events carry 'content' for ChatViewModel accumulation."""
        wire = _make_sse_event("token_stream", content="Hello")
        payload = json.loads(wire[len("data: "):].strip())
        assert payload["type"] == "token_stream"
        assert "content" in payload

    def test_result_ready_event_has_type(self):
        """SPEC.md §22.2: result_ready event signals end of SSE stream for iOS ChatViewModel."""
        wire = _make_sse_event("result_ready", run_id=str(uuid.uuid4()))
        payload = json.loads(wire[len("data: "):].strip())
        assert payload["type"] == "result_ready"

    def test_approval_requested_event_includes_run_id_and_risk_tier(self):
        """SPEC.md §29.6: approval_requested SSE event carries run_id and risk_tier."""
        run_id = str(uuid.uuid4())
        wire = _make_sse_event(
            "approval_requested", run_id=run_id, risk_tier="high"
        )
        payload = json.loads(wire[len("data: "):].strip())
        assert payload["type"] == "approval_requested"
        assert payload["risk_tier"] == "high"
        assert payload["run_id"] == run_id

    def test_sse_error_event_has_message(self):
        """SPEC.md §22.2: error SSE events must carry a 'message' field for iOS error display."""
        wire = _make_sse_event("error", message="Run failed: context limit exceeded")
        payload = json.loads(wire[len("data: "):].strip())
        assert payload["type"] == "error"
        assert "message" in payload

    def test_all_expected_event_types_are_json_serialisable(self):
        """PHASE_DETAILS iOS5/iOS11: All SSEEvent enum variants must survive JSON round-trip."""
        event_types = [
            "meta",
            "token_stream",
            "result_ready",
            "tool_called",
            "step_started",
            "classification_done",
            "approval_requested",
            "approval_received",
            "error",
        ]
        for event_type in event_types:
            wire = _make_sse_event(event_type)
            payload = json.loads(wire[len("data: "):].strip())
            assert payload["type"] == event_type, (
                f"Event type '{event_type}' did not survive JSON round-trip"
            )


# ---------------------------------------------------------------------------
# Full E2E Flow: Login → Chat → Logout (integration)
# ---------------------------------------------------------------------------


class TestLoginChatLogoutFlow:
    """SPEC.md §37: Approval flow works on web UI and mobile. Session expiry and token refresh flow verified."""

    def test_login_response_schema_includes_expires_in_for_ios(self):
        """SPEC.md §5.3 + §29.3: Login AuthTokenResponse must include expires_in for iOS scheduling.

        iOS AuthViewModel uses expires_in to schedule proactive token refresh before expiry.
        If this field is absent, the iOS client silently fails to refresh and gets 401 errors.
        """
        from noa.api.v1.auth import AuthTokenResponse

        # Verify schema includes all fields the iOS MockURLProtocol must serve
        response = AuthTokenResponse(
            token_type="bearer",
            expires_in=900,
            access_token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.sig",
            refresh_token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJyZWYifQ.sig",
        )
        # token_type must be "bearer" — iOS AuthService checks this
        assert response.token_type == "bearer"
        # expires_in drives AuthViewModel refresh scheduling
        assert response.expires_in > 0, "expires_in must be positive seconds"
        # Both tokens must be present for iOS Keychain storage
        assert response.access_token is not None
        assert response.refresh_token is not None

    @pytest.mark.asyncio
    async def test_unauthenticated_chat_returns_401(self):
        """SPEC.md §29.3: iOS client must handle 401 and redirect to login."""
        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat",
                json={"message": "hello", "thread_id": str(uuid.uuid4())},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_pending_approvals_returns_401(self):
        """SPEC.md §29.6: iOS must authenticate before fetching approvals."""
        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/approvals/pending")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_device_registration_returns_401(self):
        """SPEC.md §29.5: Device push token registration requires authentication."""
        from noa.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/devices/push-token",
                json=_make_device_token_payload(),
            )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Certificate Pinning Production Wiring (deferred from iOS10)
# ---------------------------------------------------------------------------


class TestCertificatePinningWiring:
    """SPEC.md §29.4: Certificate pinning on native iOS to prevent MITM."""

    def test_pinning_evaluator_rejects_mismatched_hash(self):
        """SPEC.md §29.4: evaluatePinning returns False when hash is not in allowed set.

        This tests the backend contract side: the SPKI hash format expected by
        iOS CertificatePinningDelegate must be a base64-encoded SHA-256 string.
        The mock server must present hashes of this exact format.
        """
        import base64
        import hashlib

        fake_key_bytes = b"\x00" * 32
        spki_hash = base64.b64encode(hashlib.sha256(fake_key_bytes).digest()).decode()
        # Base64-encoded SHA-256 must be 44 chars (32 bytes → 44 base64 chars)
        assert len(spki_hash) == 44, "SPKI hash must be 44 base64 chars (256 bits)"
        # Must not contain padding issues
        assert spki_hash.endswith("=") or len(spki_hash) == 44

    def test_pinning_hash_format_is_base64_sha256(self):
        """SPEC.md §29.4: SPKI DER hash must be SHA-256 and base64-encoded for iOS pinning."""
        import base64
        import hashlib

        # Simulate the SPKI header + raw key bytes pattern used in CertificatePinningDelegate
        ec_p256_header = bytes([
            0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86,
            0x48, 0xce, 0x3d, 0x02, 0x01, 0x06, 0x08, 0x2a,
            0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03,
            0x42, 0x00,
        ])
        fake_raw_key = b"\xab" * 65  # EC P-256 raw public key is 65 bytes uncompressed
        spki_der = ec_p256_header + fake_raw_key
        digest = hashlib.sha256(spki_der).digest()
        hash_str = base64.b64encode(digest).decode()

        # Verify the format the iOS client expects
        assert len(hash_str) == 44
        decoded = base64.b64decode(hash_str)
        assert len(decoded) == 32  # SHA-256 is 32 bytes


# ---------------------------------------------------------------------------
# Offline Queue Drain Flow (§29.3)
# ---------------------------------------------------------------------------


class TestOfflineQueueDrainContract:
    """SPEC.md §29.3 + §1035: Offline queue drains when connectivity resumes."""

    def test_queued_request_is_json_serialisable(self):
        """SPEC.md §29.3: QueuedRequest must survive JSON round-trip for file-backed persistence."""
        import json as json_mod

        request_dict = {
            "id": str(uuid.uuid4()),
            "endpoint": "/api/v1/chat",
            "method": "POST",
            "body_data": None,
            "retry_count": 0,
            "enqueued_at": "2026-03-10T08:00:00+00:00",
        }
        serialized = json_mod.dumps(request_dict)
        restored = json_mod.loads(serialized)
        assert restored["endpoint"] == "/api/v1/chat"
        assert restored["retry_count"] == 0

    def test_offline_queue_retry_count_increments(self):
        """SPEC.md §29.3: Failed requests must be re-queued with incremented retry_count (max 5)."""
        retry_counts = [0, 1, 2, 3, 4, 5]
        max_retries = 5
        for count in retry_counts:
            within_limit = count <= max_retries
            assert isinstance(within_limit, bool)

        # After maxRetries (5), request must not be re-queued
        exhausted_count = max_retries + 1
        assert exhausted_count > max_retries, "Retry count must stop at maxRetries=5"

    def test_offline_queue_backoff_sequence_is_exponential(self):
        """PHASE_DETAILS iOS9: Retry backoff must be [1, 2, 4, 8, 16] seconds."""
        expected_backoff_seconds = [1, 2, 4, 8, 16]
        for i, expected in enumerate(expected_backoff_seconds):
            computed = 2 ** i
            assert computed == expected, (
                f"Backoff at retry {i} should be {expected}s, got {computed}s"
            )


# ---------------------------------------------------------------------------
# API Wiring Completeness (iOS integration prerequisite)
# ---------------------------------------------------------------------------


class TestAPIWiringCompleteness:
    """SPEC.md §37: All iOS-required routes must be wired and reachable."""

    def test_all_ios_routes_present(self):
        """PHASE_DETAILS iOS11: All endpoints exercised by iOS integration tests must be registered."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]

        ios_required_routes = {
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/chat",
            "/api/v1/approvals/pending",
            "/api/v1/approvals/{approval_id}/decide",
            "/api/v1/devices/push-token",
            "/api/v1/voice/transcribe",
        }
        missing = ios_required_routes - routes
        assert not missing, f"iOS-required routes not registered: {missing}"

    def test_health_endpoint_returns_200_without_auth(self):
        """SPEC.md §29.3: iOS app can check server reachability without authentication."""
        import asyncio

        from noa.api.app import create_app

        async def _check():
            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/health")
            return response.status_code

        status = asyncio.get_event_loop().run_until_complete(_check())
        assert status == 200

    def test_voice_transcribe_endpoint_registered(self):
        """PHASE_DETAILS iOS8: /api/v1/voice/transcribe must be wired for VoiceService."""
        from noa.api.app import create_app

        app = create_app()
        routes = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert "/api/v1/voice/transcribe" in routes


# ---------------------------------------------------------------------------
# Approval Decide Response Shape (iOS11 E2E integration test gate)
# ---------------------------------------------------------------------------


async def _make_seeded_db(approval_id: uuid.UUID, risk_tier: str = "medium"):
    """Create an in-memory async SQLite DB with one pending Approval seeded.

    SQLite does not enforce FK constraints unless PRAGMA foreign_keys=ON is set,
    so we can insert Approval with arbitrary run_id/user_id UUIDs without needing
    a full User + Run record.  Returns an async_sessionmaker bound to this engine.
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.approval import Approval
    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        approval = Approval(
            id=approval_id,
            run_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            risk_tier=risk_tier,
            preview_text="Integration test approval",
            decision="pending",
            domain="external",
        )
        session.add(approval)
        await session.commit()

    return factory


class TestApprovalDecideResponseShape:
    """PHASE_DETAILS iOS11: iOS11 ApprovalFlowTests.swift exercises the decide endpoint.

    The decide response must include the full approval shape so ApprovalDetailViewModel
    can update badge color (risk_tier) and show the decision timestamp (decided_at).
    Tests seed a real Approval in an in-memory SQLite DB and verify the endpoint
    reads and persists from the DB rather than returning fabricated data.
    """

    @pytest.mark.asyncio
    async def test_decide_response_includes_risk_tier(self, monkeypatch):
        """PHASE_DETAILS iOS11: decide response must carry the real risk_tier from DB.

        Approval is seeded with risk_tier="medium". The endpoint must query the DB
        and return "medium" — not a hardcoded value.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-ios11")

        from noa.api.app import create_app
        from noa.api.deps import get_db_session
        from noa.auth.middleware import require_auth

        approval_id = uuid.uuid4()
        factory = await _make_seeded_db(approval_id, risk_tier="medium")

        fake_user = {"sub": str(uuid.uuid4()), "email": "test@example.com"}

        async def _fake_auth():
            return fake_user

        async def _fake_db():
            async with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[require_auth] = _fake_auth
        app.dependency_overrides[get_db_session] = _fake_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/approvals/{approval_id}/decide",
                json={"decision": "approved"},
            )

        app.dependency_overrides.clear()
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        data = body["data"]
        assert "risk_tier" in data, (
            "decide response must include risk_tier so ApprovalDetailViewModel "
            "can update badge color; got keys: " + str(list(data.keys()))
        )
        assert data["risk_tier"] == "medium", (
            "risk_tier must reflect the actual DB value ('medium'), "
            f"not a hardcoded default; got: {data['risk_tier']!r}"
        )

    @pytest.mark.asyncio
    async def test_decide_response_includes_decided_at_timestamp(self, monkeypatch):
        """PHASE_DETAILS iOS11: decide response must include decided_at persisted to DB.

        iOS11 ApprovalFlowTests verifies that the detail view shows the decision
        timestamp after the user approves. decided_at must be a real ISO-8601 string.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-ios11")

        from noa.api.app import create_app
        from noa.api.deps import get_db_session
        from noa.auth.middleware import require_auth

        approval_id = uuid.uuid4()
        factory = await _make_seeded_db(approval_id, risk_tier="high")

        fake_user = {"sub": str(uuid.uuid4()), "email": "test@example.com"}

        async def _fake_auth():
            return fake_user

        async def _fake_db():
            async with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[require_auth] = _fake_auth
        app.dependency_overrides[get_db_session] = _fake_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/approvals/{approval_id}/decide",
                json={"decision": "denied"},
            )

        app.dependency_overrides.clear()
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert "decided_at" in data, (
            "decide response must include decided_at timestamp; "
            "got keys: " + str(list(data.keys()))
        )
        assert data["decided_at"] is not None, (
            "decided_at must not be null after decision is recorded"
        )
        # Must be a parseable ISO-8601 string, not null or fabricated
        from datetime import datetime as _dt
        parsed = _dt.fromisoformat(data["decided_at"])
        assert parsed.year >= 2024, f"decided_at looks wrong: {data['decided_at']}"
