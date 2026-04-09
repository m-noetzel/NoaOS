"""Tests for DI3 — RLS endpoint wiring (W24B-L1).

Verifies that set_domain_context() is called from the approvals endpoints,
and that threads.py (already wired) still passes. Also tests that the
set_domain_context helper is a no-op on SQLite so unit tests are unaffected.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from noa.api.app import create_app
from noa.auth.middleware import AuthUser, require_auth


def _fake_user() -> AuthUser:
    return AuthUser(user_id=uuid.uuid4())


def _make_app() -> Any:
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user
    return app


def _make_db_session(rows: list[Any] | None = None) -> AsyncMock:
    """Create an AsyncMock session that returns empty scalars results."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows or []
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestRLSHelperSQLiteNoOp:
    """set_domain_context is a no-op on SQLite connections."""

    @pytest.mark.asyncio
    async def test_no_op_on_sqlite(self) -> None:
        from noa.db.rls import set_domain_context

        # Simulate a SQLite-backed session (dialect name != 'postgresql')
        # Use MagicMock (not AsyncMock) to avoid unawaited-coroutine warnings
        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"
        mock_session.sync_session.get_bind.return_value = mock_bind
        mock_session.execute = AsyncMock(return_value=MagicMock())

        # Should not call session.execute (no SQL emitted for SQLite)
        await set_domain_context(mock_session, "private")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_execute_on_postgres(self) -> None:
        from sqlalchemy.sql.elements import TextClause

        from noa.db.rls import set_domain_context

        # Build mock session with sync_session.get_bind returning a postgres dialect
        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        mock_session.sync_session.get_bind.return_value = mock_bind

        # execute() is the async coroutine called by set_domain_context
        mock_session.execute = AsyncMock(return_value=MagicMock())

        await set_domain_context(mock_session, "private")
        # execute must have been called with the SET CONFIG text
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0]
        assert len(call_args) >= 1
        assert isinstance(call_args[0], TextClause)


class TestApprovalsRLSWiring:
    """set_domain_context is called from approval endpoints."""

    def _make_session_dep(self) -> tuple[AsyncMock, Any]:
        """Return (mock_session, override_dep) for injecting into the app."""

        sess = _make_db_session()
        async def _dep() -> Any:
            return sess

        return sess, _dep

    def test_list_pending_calls_set_domain_context(self) -> None:
        """GET /pending activates RLS domain context."""
        from noa.api.deps import get_db_session

        app = _make_app()
        sess, dep = self._make_session_dep()
        app.dependency_overrides[get_db_session] = dep

        with patch("noa.api.v1.approvals.set_domain_context", new_callable=AsyncMock) as mock_rls:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/approvals/pending",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        mock_rls.assert_called_once()
        # First positional arg is the session, second is the domain
        called_domain = mock_rls.call_args[0][1]
        # Default domain is "" (show all) when no query param given
        assert called_domain == ""

    def test_list_pending_passes_domain_param(self) -> None:
        """GET /pending?domain=private passes 'private' to set_domain_context."""
        from noa.api.deps import get_db_session

        app = _make_app()
        sess, dep = self._make_session_dep()
        app.dependency_overrides[get_db_session] = dep

        with patch("noa.api.v1.approvals.set_domain_context", new_callable=AsyncMock) as mock_rls:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/approvals/pending?domain=private",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        mock_rls.assert_called_once()
        called_domain = mock_rls.call_args[0][1]
        assert called_domain == "private"

    def test_list_history_calls_set_domain_context(self) -> None:
        """GET /history activates RLS domain context."""
        from noa.api.deps import get_db_session

        app = _make_app()
        sess, dep = self._make_session_dep()
        app.dependency_overrides[get_db_session] = dep

        with patch("noa.api.v1.approvals.set_domain_context", new_callable=AsyncMock) as mock_rls:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/approvals/history",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        mock_rls.assert_called_once()

    def test_decide_approval_calls_set_domain_context(self) -> None:
        """POST /{id}/decide activates RLS domain context."""
        from noa.api.deps import get_db_session
        from noa.db.models.approval import Approval

        approval_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Build a mock approval that passes IDOR check
        mock_approval = MagicMock(spec=Approval)
        mock_approval.id = approval_id
        mock_approval.user_id = user_id
        mock_approval.decision = "pending"
        mock_approval.run_id = uuid.uuid4()
        mock_approval.risk_tier = "low"
        mock_approval.preview_text = ""
        mock_approval.requested_at = __import__("datetime").datetime.utcnow()
        mock_approval.decided_at = None
        mock_approval.domain = "external"

        sess = _make_db_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        sess.execute = AsyncMock(return_value=mock_result)

        # Patch the user so IDOR check passes
        def fake_user() -> AuthUser:
            return AuthUser(user_id=user_id)

        app = create_app()
        app.dependency_overrides[require_auth] = fake_user

        async def _dep() -> Any:
            return sess

        app.dependency_overrides[get_db_session] = _dep

        with (
            patch("noa.api.v1.approvals.set_domain_context", new_callable=AsyncMock) as mock_rls,
            patch("noa.api.v1.approvals._resume_graph", new_callable=AsyncMock),
            patch("noa.api.v1.approvals._handle_memory_approval"),
            patch("asyncio.ensure_future"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                f"/api/v1/approvals/{approval_id}/decide",
                json={"decision": "approved"},
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        mock_rls.assert_called_once()
        # decide_approval uses empty domain (cross-domain access for single lookup)
        called_domain = mock_rls.call_args[0][1]
        assert called_domain == ""


class TestThreadsRLSAlreadyWired:
    """Verify threads.py still calls set_domain_context (already wired pre-DI3)."""

    def test_list_threads_calls_set_domain_context(self) -> None:
        from noa.api.deps import get_db_session

        app = _make_app()

        sess = _make_db_session()
        # Simulate the execute for conversations query
        mock_rows = MagicMock()
        mock_rows.__iter__ = MagicMock(return_value=iter([]))
        sess.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))

        async def _dep() -> Any:
            return sess

        app.dependency_overrides[get_db_session] = _dep

        with patch("noa.api.v1.threads.set_domain_context", new_callable=AsyncMock) as mock_rls:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/threads",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        mock_rls.assert_called()
