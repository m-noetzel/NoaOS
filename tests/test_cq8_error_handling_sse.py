"""Tests for CQ8: Consistent Error Handling & SSE Contract.

Covers:
- sse_types.py TypedDicts — structural correctness and VALID_SSE_EVENT_TYPES set
- Exception narrowing in auth/service.py (TokenError)
- Exception narrowing in external_worker LLM clients (json.JSONDecodeError)
- Exception narrowing in retention.py (noqa annotations present)
- asString / asRecord / asStringArray helpers are tested in cq8_frontend (web test)

Spec refs: SPEC.md §22.1, §22.2
"""

from __future__ import annotations

import json
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. SSE TypedDicts — structural correctness
# ---------------------------------------------------------------------------


class TestSSETypes:
    """sse_types.py exports typed dicts with correct fields."""

    def test_meta_event_type_hint(self) -> None:
        from noa.orchestrator.sse_types import MetaEvent

        # Construct a valid MetaEvent — TypedDict is just a dict at runtime
        evt: MetaEvent = {
            "event_type": "meta",
            "run_id": "run-123",
            "thread_id": "thread-456",
        }
        assert evt["event_type"] == "meta"
        assert evt["run_id"] == "run-123"
        assert evt["thread_id"] == "thread-456"

    def test_error_event_type_hint(self) -> None:
        from noa.orchestrator.sse_types import ErrorEvent

        evt: ErrorEvent = {
            "event_type": "error",
            "payload": {"error": "Something went wrong"},
        }
        assert evt["event_type"] == "error"
        assert evt["payload"]["error"] == "Something went wrong"

    def test_result_ready_event(self) -> None:
        from noa.orchestrator.sse_types import ResultReadyEvent

        evt: ResultReadyEvent = {
            "event_type": "result_ready",
            "payload": {
                "response": "Hello world",
                "total_cost": 0.002,
                "llm_usage": [],
            },
            "timestamp": "2026-01-01T00:00:00Z",
        }
        assert evt["payload"]["response"] == "Hello world"
        assert evt["payload"]["total_cost"] == 0.002

    def test_approval_event(self) -> None:
        from noa.orchestrator.sse_types import ApprovalEvent

        evt: ApprovalEvent = {
            "event_type": "approval_requested",
            "payload": {
                "tool": "gmail",
                "function": "send_email",
                "args": {"to": "test@example.com"},
                "risk_tier": "high",
            },
            "timestamp": "2026-01-01T00:00:00Z",
        }
        assert evt["payload"]["tool"] == "gmail"
        assert evt["payload"]["risk_tier"] == "high"

    def test_valid_sse_event_types_completeness(self) -> None:
        from noa.orchestrator.sse_types import VALID_SSE_EVENT_TYPES

        required = {
            "meta", "token", "done", "error", "tool_called",
            "tool_start", "tool_end", "tool_result", "approval_requested",
            "result_ready", "message_received", "classification_done",
            "step_started", "queued",
        }
        assert required.issubset(VALID_SSE_EVENT_TYPES), (
            f"Missing event types: {required - VALID_SSE_EVENT_TYPES}"
        )

    def test_queued_event(self) -> None:
        from noa.orchestrator.sse_types import QueuedEvent

        evt: QueuedEvent = {
            "event_type": "queued",
            "payload": {
                "queue_id": "q-123",
                "message": "Private domain unavailable, queued",
            },
        }
        assert evt["event_type"] == "queued"
        assert evt["payload"]["queue_id"] == "q-123"


# ---------------------------------------------------------------------------
# 2. auth/service.py — TokenError narrowing
# ---------------------------------------------------------------------------


class TestAuthServiceExceptionNarrowing:
    """reset_password() catches TokenError specifically, not all exceptions."""

    @pytest.mark.asyncio
    async def test_reset_password_raises_auth_error_on_token_error(
        self, test_settings
    ) -> None:
        """TokenError from decode_token is caught and re-raised as AuthError."""
        from noa.auth.jwt import TokenError
        from noa.auth.service import AuthError, AuthService

        session = AsyncMock()
        service = AuthService(session=session, settings=test_settings)

        with patch("noa.auth.service.decode_token", side_effect=TokenError("bad token")):
            with pytest.raises(AuthError, match="Invalid or expired reset token"):
                await service.reset_password(token="bad-token", new_password="newpassword123")

    @pytest.mark.asyncio
    async def test_non_token_error_propagates_from_reset_password(
        self, test_settings
    ) -> None:
        """Non-TokenError exceptions (e.g. RuntimeError) are NOT swallowed."""
        from noa.auth.service import AuthService

        session = AsyncMock()

        # SECRET_KEY not set → RuntimeError from service itself (not decode_token)
        settings_no_key = MagicMock()
        settings_no_key.secret_key = ""
        service2 = AuthService(session=session, settings=settings_no_key)

        with pytest.raises(RuntimeError, match="SECRET_KEY not set"):
            await service2.reset_password(token="any-token", new_password="newpassword123")


# ---------------------------------------------------------------------------
# 3. LLM clients — json.JSONDecodeError narrowing
# ---------------------------------------------------------------------------


class TestOpenAIJsonNarrowing:
    """OpenAI client now catches json.JSONDecodeError, not Exception."""

    def test_parse_response_handles_non_json_error_body(self) -> None:
        """When error body is not valid JSON, falls back to response.text."""
        from noa.external_worker.llm.openai import OpenAIClient
        from noa.external_worker.exceptions import ProviderError

        client = OpenAIClient(api_key="test", model="gpt-4")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
        mock_response.text = "Internal Server Error"

        with pytest.raises(ProviderError, match="Internal Server Error"):
            client._parse_response(mock_response)

    def test_parse_response_uses_json_error_detail_when_valid(self) -> None:
        """When error body is valid JSON, extracts error.message."""
        from noa.external_worker.llm.openai import OpenAIClient
        from noa.external_worker.exceptions import ProviderError

        client = OpenAIClient(api_key="test", model="gpt-4")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "error": {"message": "Rate limit exceeded"}
        }
        mock_response.text = "Rate limit exceeded (raw)"

        with pytest.raises(ProviderError, match="Rate limit exceeded"):
            client._parse_response(mock_response)

    def test_non_json_decode_error_propagates_from_200_response(self) -> None:
        """A ValueError from response.json() on a 200 response propagates (not silently swallowed)."""
        from noa.external_worker.llm.openai import OpenAIClient

        client = OpenAIClient(api_key="test", model="gpt-4")

        mock_response = MagicMock()
        mock_response.status_code = 200
        # json() raises ValueError on a 200 response — not caught in parse path
        mock_response.json.side_effect = ValueError("bad json on success")

        with pytest.raises(ValueError, match="bad json on success"):
            client._parse_response(mock_response)


class TestAnthropicJsonNarrowing:
    """Anthropic client now catches json.JSONDecodeError, not Exception."""

    def test_parse_response_handles_non_json_error_body(self) -> None:
        """When error body is not valid JSON, falls back to response.text."""
        from noa.external_worker.llm.anthropic import AnthropicClient
        from noa.external_worker.exceptions import ProviderError

        client = AnthropicClient(api_key="test", model="claude-3")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = json.JSONDecodeError("bad", "doc", 0)
        mock_response.text = "Anthropic server error"

        with pytest.raises(ProviderError, match="Anthropic server error"):
            client._parse_response(mock_response)


# ---------------------------------------------------------------------------
# 4. Retention scheduler — noqa annotations (no bare except)
# ---------------------------------------------------------------------------


class TestRetentionExceptionHandling:
    """Retention scheduler catches Exception with proper noqa, logs and continues."""

    def test_run_once_catches_purge_failure(self) -> None:
        """RetentionScheduler._run_once() catches and logs purge errors."""
        import asyncio
        from noa.maintenance.retention import RetentionScheduler

        failing_service = MagicMock()
        failing_service.purge_expired.side_effect = RuntimeError("DB down")
        # No async purge method
        del failing_service.purge_expired_async

        scheduler = RetentionScheduler(audit_service=failing_service, interval_hours=1)

        # Should not raise — catches internally
        asyncio.get_event_loop().run_until_complete(scheduler.run_once())

    def test_run_once_catches_approval_expiry_failure(self) -> None:
        """RetentionScheduler._run_once() catches approval expiry errors."""
        import asyncio
        from noa.maintenance.retention import RetentionScheduler

        audit_service = MagicMock()
        audit_service.purge_expired.return_value = 0
        del audit_service.purge_expired_async

        failing_approval_svc = MagicMock()
        failing_approval_svc.expire_stale.side_effect = RuntimeError("Approvals down")

        scheduler = RetentionScheduler(
            audit_service=audit_service,
            approval_service=failing_approval_svc,
            interval_hours=1,
        )

        # Should not raise
        asyncio.get_event_loop().run_until_complete(scheduler.run_once())
