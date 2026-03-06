"""Tests for MR3: Tool Call Audit Trail.

Verifies that every ToolGateway.dispatch() path produces an audit callback
invocation, with correct status, and that AuditService.create_entry_async()
writes to an async session with hash chaining.
"""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAdapter:
    """Adapter that returns a fixed response."""

    def __init__(self, result: dict[str, Any] | None = None, error: str | None = None):
        self._result = result
        self._error = error

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self._error:
            raise RuntimeError(self._error)
        return ToolResponse(result=self._result or {"ok": True}, provider="fake")


# ---------------------------------------------------------------------------
# ToolRequest field tests
# ---------------------------------------------------------------------------


class TestToolRequestUserContext:
    """ToolRequest should carry optional user_id, session_id, trace_id."""

    def test_has_user_id_field(self) -> None:
        req = ToolRequest(tool="t", function="f", args={})
        assert hasattr(req, "user_id")

    def test_has_session_id_field(self) -> None:
        req = ToolRequest(tool="t", function="f", args={})
        assert hasattr(req, "session_id")

    def test_has_trace_id_field(self) -> None:
        req = ToolRequest(tool="t", function="f", args={})
        assert hasattr(req, "trace_id")

    def test_defaults_are_none(self) -> None:
        req = ToolRequest(tool="t", function="f", args={})
        assert req.user_id is None
        assert req.session_id is None
        assert req.trace_id is None

    def test_fields_accept_uuid(self) -> None:
        uid = uuid.uuid4()
        sid = uuid.uuid4()
        tid = uuid.uuid4()
        req = ToolRequest(
            tool="t", function="f", args={},
            user_id=uid, session_id=sid, trace_id=tid,
        )
        assert req.user_id == uid
        assert req.session_id == sid
        assert req.trace_id == tid


# ---------------------------------------------------------------------------
# Audit callback tests
# ---------------------------------------------------------------------------


class TestDispatchAuditCallback:
    """dispatch() must invoke audit_callback on every exit path."""

    @pytest.mark.asyncio
    async def test_success_calls_audit(self) -> None:
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("echo", _FakeAdapter())
        uid = uuid.uuid4()
        req = ToolRequest(tool="echo", function="run", args={}, user_id=uid)
        await gw.dispatch(req)
        cb.assert_awaited_once()
        assert cb.call_args[0][2] == "ok"

    @pytest.mark.asyncio
    async def test_error_calls_audit(self) -> None:
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("fail", _FakeAdapter(error="boom"))
        uid = uuid.uuid4()
        req = ToolRequest(tool="fail", function="run", args={}, user_id=uid)
        await gw.dispatch(req)
        cb.assert_awaited_once()
        assert cb.call_args[0][2] == "error"

    @pytest.mark.asyncio
    async def test_rate_limited_calls_audit(self) -> None:
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("rl", _FakeAdapter())
        gw.set_rate_limit("rl", max_calls=0, window_seconds=60)
        uid = uuid.uuid4()
        req = ToolRequest(tool="rl", function="run", args={}, user_id=uid)
        await gw.dispatch(req)
        cb.assert_awaited_once()
        assert cb.call_args[0][2] == "rate_limited"

    @pytest.mark.asyncio
    async def test_dry_run_calls_audit(self) -> None:
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("dr", _FakeAdapter())
        uid = uuid.uuid4()
        req = ToolRequest(tool="dr", function="run", args={}, user_id=uid)
        await gw.dispatch(req, dry_run=True)
        cb.assert_awaited_once()
        assert cb.call_args[0][2] == "dry_run"

    @pytest.mark.asyncio
    async def test_cached_calls_audit(self) -> None:
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("cache", _FakeAdapter())
        uid = uuid.uuid4()
        key = "idem-123"
        req = ToolRequest(
            tool="cache", function="run", args={},
            idempotency_key=key, user_id=uid,
        )
        await gw.dispatch(req)  # first call populates cache
        cb.reset_mock()
        await gw.dispatch(req)  # second call hits cache
        cb.assert_awaited_once()
        assert cb.call_args[0][2] == "cached"

    @pytest.mark.asyncio
    async def test_skips_audit_when_no_callback(self) -> None:
        """dispatch() works fine without audit_callback (backward compat)."""
        gw = ToolGateway()  # no audit_callback
        gw.register("echo", _FakeAdapter())
        req = ToolRequest(tool="echo", function="run", args={}, user_id=uuid.uuid4())
        resp = await gw.dispatch(req)
        assert resp.error is None  # no crash

    @pytest.mark.asyncio
    async def test_skips_audit_when_no_user_id(self) -> None:
        """Callback not called when request.user_id is None."""
        cb = AsyncMock()
        gw = ToolGateway(audit_callback=cb)
        gw.register("echo", _FakeAdapter())
        req = ToolRequest(tool="echo", function="run", args={})  # user_id=None
        await gw.dispatch(req)
        cb.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_callback_error_does_not_fail_dispatch(self) -> None:
        """If audit callback raises, dispatch still returns the response."""
        cb = AsyncMock(side_effect=RuntimeError("audit db down"))
        gw = ToolGateway(audit_callback=cb)
        gw.register("echo", _FakeAdapter())
        uid = uuid.uuid4()
        req = ToolRequest(tool="echo", function="run", args={}, user_id=uid)
        resp = await gw.dispatch(req)
        assert resp.error is None
        assert resp.result == {"ok": True}


# ---------------------------------------------------------------------------
# AuditService.create_entry_async tests
# ---------------------------------------------------------------------------


class TestCreateEntryAsync:
    """AuditService.create_entry_async() writes via AsyncSession."""

    @pytest.mark.asyncio
    async def test_writes_to_session(self) -> None:
        from noa.audit.service import AuditService

        mock_session = AsyncMock()
        # scalars().first() returns None (no previous entry)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.scalars.return_value = mock_result

        svc = AuditService.__new__(AuditService)  # bypass __init__
        entry = await svc.create_entry_async(
            session=mock_session,
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="external",
            model_provider="tool_gateway",
            model_name="n/a",
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal("0"),
            tool_name="echo",
            tool_args={"x": 1},
            tool_result_summary="ok",
            privacy_classification="external",
            classification_confidence=1.0,
        )
        mock_session.add.assert_called_once()
        assert entry is not None

    @pytest.mark.asyncio
    async def test_chains_hash_from_previous(self) -> None:
        import json

        from noa.audit.service import AuditService

        # Create a fake previous entry as a MagicMock with hash_chain_data
        prev_data = {
            "id": str(uuid.uuid4()),
            "timestamp": None,
            "user_id": str(uuid.uuid4()),
            "trace_id": str(uuid.uuid4()),
            "domain": "external",
            "model_provider": "openai",
            "model_name": "gpt-4",
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": "0.01",
            "tool_name": None,
            "privacy_classification": "external",
            "previous_entry_hash": None,
        }
        chain_str = json.dumps(prev_data, sort_keys=True)
        prev = MagicMock()
        prev.hash_chain_data.return_value = chain_str

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = prev
        mock_session.scalars.return_value = mock_result

        svc = AuditService.__new__(AuditService)
        entry = await svc.create_entry_async(
            session=mock_session,
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="external",
            model_provider="tool_gateway",
            model_name="n/a",
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal("0"),
            tool_name="echo",
            privacy_classification="external",
            classification_confidence=1.0,
        )
        expected_hash = hashlib.sha256(chain_str.encode()).hexdigest()
        assert entry.previous_entry_hash == expected_hash

    @pytest.mark.asyncio
    async def test_flushes_not_commits(self) -> None:
        from noa.audit.service import AuditService

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.scalars.return_value = mock_result

        svc = AuditService.__new__(AuditService)
        await svc.create_entry_async(
            session=mock_session,
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="external",
            model_provider="tool_gateway",
            model_name="n/a",
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal("0"),
            tool_name="echo",
            privacy_classification="external",
            classification_confidence=1.0,
        )
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_not_awaited()
