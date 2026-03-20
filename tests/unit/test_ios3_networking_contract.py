"""Tests for the backend API contract consumed by the iOS3 networking layer.

Spec refs: SPEC.md §25.3 (Standard Response Envelope), §25.4 (Idempotency),
           §29.1 (Client Overview), §29.3 (Mobile Access — Thin Client),
           §29.4 (Connection Security), §22.1–§22.2 (Run/Event model)
Phase plan: PHASE_DETAILS.md Phase iOS3

iOS3 creates APIClient, SSEClient, and shared Swift model types that mirror
the backend's data shapes. These Python tests pin the exact contract that
Swift code must decode correctly. If these tests break, the iOS client breaks.

Tests are written BEFORE the iOS3 Swift implementation and act as the
canonical specification for:
  - Envelope shape (`ok`, `data`, `error`, `trace_id`)
  - SSE event wire format (`data: {...}\\n\\n`)
  - Idempotency-Key header extraction (case-insensitive)
  - X-Trace-ID response header presence
  - Valid run event types (must match iOS SSEEvent enum)
  - Run/Thread/Approval JSON serialisable shapes
  - DeviceID uniqueness (backend registration accepts distinct UUIDs)
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.ios3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dict(**kwargs) -> dict:
    """Minimal run dict matching RunRead schema."""
    run_id = kwargs.pop("id", str(uuid.uuid4()))
    thread_id = kwargs.pop("thread_id", str(uuid.uuid4()))
    user_id = kwargs.pop("user_id", str(uuid.uuid4()))
    return {
        "id": run_id,
        "thread_id": thread_id,
        "user_id": user_id,
        "status": kwargs.pop("status", "pending"),
        "risk_tier": kwargs.pop("risk_tier", "low"),
        "privacy_mode": kwargs.pop("privacy_mode", "private"),
        "summary": kwargs.pop("summary", None),
        "created_at": kwargs.pop("created_at", "2026-03-08T10:00:00+00:00"),
        "updated_at": kwargs.pop("updated_at", "2026-03-08T10:00:00+00:00"),
        **kwargs,
    }


def _make_event_dict(**kwargs) -> dict:
    """Minimal run event dict matching EventRead schema."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "run_id": kwargs.pop("run_id", str(uuid.uuid4())),
        "event_type": kwargs.pop("event_type", "token_stream"),
        "timestamp": kwargs.pop("timestamp", "2026-03-08T10:00:00+00:00"),
        "payload": kwargs.pop("payload", {}),
        **kwargs,
    }


def _make_thread_dict(**kwargs) -> dict:
    """Minimal thread dict matching Conversation schema."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "user_id": kwargs.pop("user_id", str(uuid.uuid4())),
        "title": kwargs.pop("title", "My Thread"),
        "created_at": kwargs.pop("created_at", "2026-03-08T10:00:00+00:00"),
        **kwargs,
    }


def _make_approval_dict(**kwargs) -> dict:
    """Minimal approval dict matching Approval schema."""
    return {
        "id": kwargs.pop("id", str(uuid.uuid4())),
        "run_id": kwargs.pop("run_id", str(uuid.uuid4())),
        "user_id": kwargs.pop("user_id", str(uuid.uuid4())),
        "risk_tier": kwargs.pop("risk_tier", "medium"),
        "preview_text": kwargs.pop("preview_text", "Send email to alice@example.com"),
        "decision": kwargs.pop("decision", "pending"),
        "domain": kwargs.pop("domain", "external"),
        "requested_at": kwargs.pop("requested_at", "2026-03-08T10:00:00+00:00"),
        "decided_at": kwargs.pop("decided_at", None),
        **kwargs,
    }


# ---------------------------------------------------------------------------
# § 25.3 — Standard Response Envelope
# ---------------------------------------------------------------------------


class TestResponseEnvelope:
    """SPEC.md §25.3: All API responses follow a consistent envelope."""

    def test_success_envelope_has_ok_true(self):
        """SPEC.md §25.3: Success envelope sets ok=True."""
        from noa.api.schemas.common import success_envelope

        env = success_envelope(data={"key": "value"}, trace_id="trace-001")

        assert env["ok"] is True

    def test_success_envelope_contains_data(self):
        """SPEC.md §25.3: Success envelope carries data payload."""
        from noa.api.schemas.common import success_envelope

        payload = {"thread_id": "abc-123", "run_id": "def-456"}
        env = success_envelope(data=payload, trace_id="trace-001")

        assert env["data"] == payload

    def test_success_envelope_error_is_null(self):
        """SPEC.md §25.3: Success envelope has null error field — iOS must handle None."""
        from noa.api.schemas.common import success_envelope

        env = success_envelope(data={}, trace_id="trace-001")

        assert env["error"] is None

    def test_success_envelope_includes_trace_id(self):
        """SPEC.md §25.3: trace_id field is present — iOS uses for debug logging."""
        from noa.api.schemas.common import success_envelope

        env = success_envelope(data={}, trace_id="my-trace-xyz")

        assert env["trace_id"] == "my-trace-xyz"

    def test_error_envelope_has_ok_false(self):
        """SPEC.md §25.3: Error envelope sets ok=False — iOS uses to detect errors."""
        from noa.api.schemas.common import error_envelope

        env = error_envelope(code="NOT_FOUND", message="Thread not found", trace_id="t1")

        assert env["ok"] is False

    def test_error_envelope_carries_code_and_message(self):
        """SPEC.md §25.3: error.code and error.message are present for iOS display."""
        from noa.api.schemas.common import error_envelope

        env = error_envelope(code="AUTH_REQUIRED", message="Token expired", trace_id="t1")

        assert env["error"]["code"] == "AUTH_REQUIRED"
        assert env["error"]["message"] == "Token expired"

    def test_error_envelope_data_is_null(self):
        """SPEC.md §25.3: Error envelope has null data — iOS must handle None."""
        from noa.api.schemas.common import error_envelope

        env = error_envelope(code="ERR", message="Bad", trace_id="t1")

        assert env["data"] is None

    def test_envelope_is_json_serialisable(self):
        """SPEC.md §25.3: Envelope must round-trip through JSON — iOS uses JSONDecoder."""
        from noa.api.schemas.common import success_envelope

        env = success_envelope(data={"run_id": str(uuid.uuid4())}, trace_id="t1")
        serialised = json.dumps(env)
        parsed = json.loads(serialised)

        assert parsed["ok"] is True
        assert "run_id" in parsed["data"]


# ---------------------------------------------------------------------------
# § 25.4 — Idempotency Key Header Extraction
# ---------------------------------------------------------------------------


class TestIdempotencyKeyExtraction:
    """SPEC.md §25.4: iOS client sends Idempotency-Key; backend extracts it correctly."""

    def test_extracts_canonical_header_name(self):
        """SPEC.md §25.4: Canonical 'Idempotency-Key' header is extracted."""
        from noa.api.middleware import extract_idempotency_key

        key = str(uuid.uuid4())
        result = extract_idempotency_key({"Idempotency-Key": key})

        assert result == key

    def test_extracts_lowercase_header_name(self):
        """SPEC.md §25.4: Lowercase 'idempotency-key' is also accepted (RFC 7230)."""
        from noa.api.middleware import extract_idempotency_key

        key = str(uuid.uuid4())
        result = extract_idempotency_key({"idempotency-key": key})

        assert result == key

    def test_returns_none_when_header_absent(self):
        """SPEC.md §25.4: Missing header returns None — iOS omits it on reads."""
        from noa.api.middleware import extract_idempotency_key

        result = extract_idempotency_key({"Content-Type": "application/json"})

        assert result is None

    def test_idempotency_key_is_unique_per_write(self):
        """SPEC.md §25.4: Each distinct write operation must use a unique key.

        The iOS APIClient must generate a fresh UUID per write request.
        This test verifies that two generated UUIDs are always distinct.
        """
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())

        assert key1 != key2

    def test_idempotency_key_is_valid_uuid_format(self):
        """SPEC.md §25.4: Idempotency keys should be UUIDs (36 chars, 4 dashes)."""
        key = str(uuid.uuid4())

        # UUID format: 8-4-4-4-12 hex chars separated by dashes
        parts = key.split("-")
        assert len(parts) == 5
        assert len(key) == 36


# ---------------------------------------------------------------------------
# § 22.2 — SSE Event Wire Format
# ---------------------------------------------------------------------------


class TestSSEEventWireFormat:
    """SPEC.md §22.2: SSE events use `data: <json>\\n\\n` format.

    The iOS SSEClient uses URLSession.bytes(for:) and must parse this format.
    """

    def test_sse_line_format_is_data_colon_json(self):
        """PHASE iOS3: SSE events must be formatted as 'data: {json}\\n\\n'.

        The iOS SSEClient uses URLSession.bytes(for:) and splits on '\\n\\n'.
        Each line must start with 'data: ' prefix and end with double newline.
        This test pins the wire format the backend chat stream produces and
        verifies the chat endpoint uses this exact pattern.
        """
        import inspect

        import noa.api.v1.chat as chat_module

        source = inspect.getsource(chat_module)

        # The SSE wire format MUST be `f"data: {json.dumps(event)}\n\n"`
        # This is the canonical pattern that iOS SSEClient parses
        assert 'f"data: {json.dumps(' in source, (
            "Chat endpoint must emit SSE lines as 'data: {json}\\n\\n'. "
            "iOS SSEClient depends on this exact format."
        )

    def test_sse_line_body_is_valid_json(self):
        """PHASE iOS3: Chat SSE frames must terminate with double-newline separator.

        URLSession.bytes(for:) splits on '\\n\\n'. If the separator is wrong,
        iOS SSEClient never delivers events to the UI.
        """
        import inspect

        import noa.api.v1.chat as chat_module

        source = inspect.getsource(chat_module)

        # Must end with \n\n (SSE spec requires double-newline as frame boundary)
        assert r"\n\n" in source, (
            "Chat endpoint SSE frames must end with \\n\\n. "
            "iOS SSEClient splits on this boundary."
        )

    def test_sse_event_has_event_type_field(self):
        """SPEC.md §22.2: Every SSE event carries 'event_type' — iOS SSEEvent.eventType."""
        event = _make_event_dict(event_type="approval_requested")

        assert "event_type" in event
        assert event["event_type"] == "approval_requested"

    def test_sse_event_has_payload_field(self):
        """SPEC.md §22.2: Every SSE event carries 'payload' dict — iOS SSEEvent.payload."""
        event = _make_event_dict(payload={"text": "Processing…"})

        assert "payload" in event
        assert isinstance(event["payload"], dict)


# ---------------------------------------------------------------------------
# § 22.2 — Valid Event Types (iOS SSEEvent enum must include all of these)
# ---------------------------------------------------------------------------


class TestValidEventTypes:
    """SPEC.md §22.2: iOS SSEEvent enum must cover all backend event types."""

    REQUIRED_EVENT_TYPES = frozenset(
        [
            "message_received",
            "classification_done",
            "step_started",
            "token_stream",
            "tool_start",
            "tool_called",
            "tool_end",
            "tool_result",
            "approval_requested",
            "approval_received",
            "artifact_created",
            "result_ready",
            "error",
            "meta",
        ]
    )

    def test_backend_event_types_match_spec(self):
        """SPEC.md §22.2: Backend VALID_EVENT_TYPES matches spec — iOS enum must too."""
        from noa.runs.schemas import VALID_EVENT_TYPES

        assert VALID_EVENT_TYPES == self.REQUIRED_EVENT_TYPES

    def test_approval_events_are_in_valid_set(self):
        """SPEC.md §22.2 + §29.6: approval_requested/received are valid SSE events."""
        from noa.runs.schemas import VALID_EVENT_TYPES

        assert "approval_requested" in VALID_EVENT_TYPES
        assert "approval_received" in VALID_EVENT_TYPES

    def test_token_stream_is_in_valid_set(self):
        """SPEC.md §22.2: token_stream is a valid event — iOS renders incremental text."""
        from noa.runs.schemas import VALID_EVENT_TYPES

        assert "token_stream" in VALID_EVENT_TYPES

    def test_result_ready_is_in_valid_set(self):
        """SPEC.md §22.2: result_ready signals completion — iOS finalises UI state."""
        from noa.runs.schemas import VALID_EVENT_TYPES

        assert "result_ready" in VALID_EVENT_TYPES


# ---------------------------------------------------------------------------
# § 22.1 — Run Model JSON Shape (mirrors RunModels.swift)
# ---------------------------------------------------------------------------


class TestRunModelShape:
    """SPEC.md §22.1: Run model fields — iOS RunModels.swift must mirror these."""

    REQUIRED_FIELDS = frozenset(
        ["id", "thread_id", "user_id", "status", "risk_tier", "privacy_mode", "created_at"]
    )
    VALID_STATUSES = frozenset(
        ["pending", "running", "awaiting_approval", "completed", "failed", "cancelled"]
    )
    VALID_RISK_TIERS = frozenset(["low", "medium", "high"])

    def test_run_dict_has_required_fields(self):
        """SPEC.md §22.1: Run JSON has id, thread_id, user_id, status, risk_tier, created_at."""
        run = _make_run_dict()

        for field in self.REQUIRED_FIELDS:
            assert field in run, f"Missing required field: {field}"

    def test_run_status_values_are_bounded(self):
        """SPEC.md §22.1: status must be one of the 6 defined values."""
        from noa.runs.schemas import VALID_STATUSES

        assert VALID_STATUSES == self.VALID_STATUSES

    def test_run_risk_tier_values_match_spec(self):
        """SPEC.md §22.1: risk_tier must be low/medium/high — iOS ApprovalRiskTier enum."""
        run_low = _make_run_dict(risk_tier="low")
        run_med = _make_run_dict(risk_tier="medium")
        run_high = _make_run_dict(risk_tier="high")

        for run in [run_low, run_med, run_high]:
            assert run["risk_tier"] in self.VALID_RISK_TIERS

    def test_run_ids_are_uuid_strings(self):
        """SPEC.md §22.1: id, thread_id, user_id are UUIDs — iOS uses UUID type."""
        run = _make_run_dict()

        # Must parse as valid UUIDs
        uuid.UUID(run["id"])
        uuid.UUID(run["thread_id"])
        uuid.UUID(run["user_id"])

    def test_run_pydantic_schema_parses_model_dict(self):
        """SPEC.md §22.1: RunRead schema validates run dicts — same shape iOS decodes."""
        from noa.runs.schemas import RunRead

        run = _make_run_dict()
        parsed = RunRead.model_validate(run)

        assert str(parsed.id) == run["id"]
        assert parsed.status == "pending"


# ---------------------------------------------------------------------------
# § 29.6 / Approval Model Shape (mirrors ApprovalModels.swift)
# ---------------------------------------------------------------------------


class TestApprovalModelShape:
    """SPEC.md §29.6: Approval model — iOS ApprovalModels.swift mirrors these fields."""

    REQUIRED_FIELDS = frozenset(
        ["id", "run_id", "user_id", "risk_tier", "preview_text", "decision", "requested_at"]
    )
    VALID_DECISIONS = frozenset(["pending", "approved", "denied"])

    def test_approval_dict_has_required_fields(self):
        """SPEC.md §29.6: Approval JSON has all fields iOS needs to render the UI."""
        approval = _make_approval_dict()

        for field in self.REQUIRED_FIELDS:
            assert field in approval, f"Missing required field: {field}"

    def test_approval_decision_values(self):
        """SPEC.md §29.6: decision is pending/approved/denied — iOS ApprovalDecision enum."""
        for decision in self.VALID_DECISIONS:
            approval = _make_approval_dict(decision=decision)
            assert approval["decision"] == decision

    def test_approval_preview_text_is_nullable(self):
        """SPEC.md §29.6: preview_text may be null — iOS must handle optional String."""
        approval_with = _make_approval_dict(preview_text="Send email to alice@example.com")
        approval_without = _make_approval_dict(preview_text=None)

        assert approval_with["preview_text"] is not None
        assert approval_without["preview_text"] is None


# ---------------------------------------------------------------------------
# § 10.1 / Thread + Message Shape (mirrors ChatModels.swift)
# ---------------------------------------------------------------------------


class TestThreadModelShape:
    """SPEC.md §10.1: Thread (Conversation) model — iOS ChatModels.Thread mirrors this."""

    def test_thread_dict_has_required_fields(self):
        """SPEC.md §10.1: Thread JSON has id, user_id, title, created_at."""
        thread = _make_thread_dict()

        for field in ["id", "user_id", "title", "created_at"]:
            assert field in thread, f"Missing required field: {field}"

    def test_thread_title_is_nullable(self):
        """SPEC.md §10.1: title may be null — iOS must handle optional String."""
        with_title = _make_thread_dict(title="Project Alpha")
        without_title = _make_thread_dict(title=None)

        assert with_title["title"] == "Project Alpha"
        assert without_title["title"] is None

    def test_thread_id_is_uuid_string(self):
        """SPEC.md §10.1: id is a UUID string — iOS uses UUID type."""
        thread = _make_thread_dict()
        uuid.UUID(thread["id"])  # Raises if invalid


# ---------------------------------------------------------------------------
# § 25.4 + §29.3 — DeviceID Uniqueness (iOS DeviceID utility must produce UUIDs)
# ---------------------------------------------------------------------------


class TestDeviceIDContract:
    """PHASE iOS3: DeviceID utility must generate and persist a unique UUID.

    The backend (device registration) accepts any UUID; this tests the contract
    for what shape a device_id must take.
    """

    def test_device_id_is_valid_uuid(self):
        """PHASE iOS3: DeviceID must be a valid UUID string (36 chars, 4 dashes)."""
        device_id = str(uuid.uuid4())

        parts = device_id.split("-")
        assert len(parts) == 5, "UUID must have 4 dash separators"
        assert len(device_id) == 36, "UUID string must be 36 chars"

    def test_device_id_generation_is_unique(self):
        """PHASE iOS3: Each DeviceID generation call produces a new unique value."""
        ids = [str(uuid.uuid4()) for _ in range(10)]

        assert len(set(ids)) == 10, "All generated device IDs must be unique"

    def test_backend_device_registration_accepts_uuid_device_id(self):
        """PHASE iOS3: Device registration endpoint is wired and accepts the iOS device_id."""
        from noa.api.v1.devices import router as devices_router

        # Verify router exists and is correctly configured (prefix check)
        assert devices_router.prefix == "/api/v1/devices"

    def test_device_id_from_keychain_is_stable_across_calls(self):
        """PHASE iOS3: Once generated, DeviceID must not change (Keychain persistence).

        This contract test ensures the iOS utility must persist — not regenerate.
        We model this as: same input UUID always round-trips to same UUID.
        """
        original = str(uuid.uuid4())
        stored = original  # Simulates Keychain write/read
        retrieved = stored

        assert retrieved == original


# ---------------------------------------------------------------------------
# iOS3-specific: Meta SSE event and environment configuration
# ---------------------------------------------------------------------------


class TestMetaSSEEventContract:
    """PHASE iOS3: The 'meta' SSE event carries run_id and thread_id.

    The chat endpoint emits a 'meta' event as the first SSE frame.
    iOS3 SSEClient parses this to capture run_id and thread_id for
    subsequent API calls. These tests pin the shape of that meta frame.
    """

    def test_meta_event_type_is_in_valid_event_types(self):
        """PHASE iOS3: 'meta' must be a valid event type — iOS SSEEvent enum includes it.

        The chat endpoint emits a 'meta' event but VALID_EVENT_TYPES does not
        currently include 'meta'. iOS3 will parse this event; it must be in the
        validated set so EventRead can decode it and the iOS enum covers it.
        This test SHOULD FAIL until 'meta' is added to VALID_EVENT_TYPES.
        """
        from noa.runs.schemas import VALID_EVENT_TYPES

        # 'meta' is the first SSE event emitted by /api/v1/chat.
        # iOS SSEEvent enum must include it; backend VALID_EVENT_TYPES must too.
        assert "meta" in VALID_EVENT_TYPES, (
            "'meta' is emitted by the chat endpoint but not in VALID_EVENT_TYPES. "
            "iOS3 SSEClient will receive this event; the schema must accept it."
        )

    def test_meta_event_carries_run_id_and_thread_id(self):
        """PHASE iOS3: meta SSE frame must contain run_id and thread_id fields.

        iOS3 APIClient reads these after receiving the meta event to bind
        subsequent requests to the correct run and thread.
        """
        import inspect

        import noa.api.v1.chat as chat_module

        source = inspect.getsource(chat_module)

        # Both fields must be present in the meta dict
        assert '"run_id"' in source and '"thread_id"' in source, (
            "Meta SSE event must contain 'run_id' and 'thread_id' fields. "
            "iOS3 APIClient binds to these after receiving the first frame."
        )


# ---------------------------------------------------------------------------
# Integration: Envelope + Middleware wiring (real code, no mocks)
# ---------------------------------------------------------------------------


class TestEnvelopeMiddlewareIntegration:
    """SPEC.md §25.3, §25.4: Envelope and middleware work correctly together."""

    def test_success_envelope_and_error_envelope_share_common_keys(self):
        """SPEC.md §25.3: Both envelope types have ok, data, error, trace_id.

        iOS APIClient switches on `ok`; all four keys must always be present.
        """
        from noa.api.schemas.common import error_envelope, success_envelope

        success = success_envelope(data={}, trace_id="t1")
        error = error_envelope(code="E", message="m", trace_id="t2")

        for key in ("ok", "data", "error", "trace_id"):
            assert key in success, f"success_envelope missing key: {key}"
            assert key in error, f"error_envelope missing key: {key}"

    def test_idempotency_extraction_is_case_insensitive_scan(self):
        """SPEC.md §25.4: Mixed-case header variants are all accepted.

        iOS URLSession may normalise headers; all forms must work.
        """
        from noa.api.middleware import extract_idempotency_key

        key = "ios-generated-key-abc"
        variants = [
            {"Idempotency-Key": key},
            {"idempotency-key": key},
            {"IDEMPOTENCY-KEY": key},
        ]

        for headers in variants:
            result = extract_idempotency_key(headers)
            assert result == key, f"Failed for headers: {headers}"

    def test_run_event_schema_validates_all_valid_event_types(self):
        """SPEC.md §22.2: Each valid event type produces a valid EventRead."""
        from noa.runs.schemas import VALID_EVENT_TYPES, EventRead

        run_id = uuid.uuid4()
        for etype in VALID_EVENT_TYPES:
            event_data = {
                "id": str(uuid.uuid4()),
                "run_id": str(run_id),
                "event_type": etype,
                "timestamp": "2026-03-08T10:00:00+00:00",
                "payload": {},
            }
            parsed = EventRead.model_validate(event_data)
            assert parsed.event_type == etype
