"""OI5 Audit Trail UI — backend endpoint tests.

Spec refs: SPEC.md §28.1, §28.2
Phase: OI5

Test plan:
- Happy path: GET /entries returns paginated audit entries for the authed user
- Happy path: GET /verify returns valid=True for empty audit log
- Happy path: GET /export returns JSON file download
- Filter: domain, tool_name, privacy_classification filters work
- Negative: unauthenticated requests get 401
- Integration: full flow — write entries to DB, query via endpoint, export
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audit_entry(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": uuid.uuid4(),
        "timestamp": datetime.now(UTC),
        "user_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "device_id": uuid.uuid4(),
        "trace_id": uuid.uuid4(),
        "domain": "external",
        "model_provider": "anthropic",
        "model_name": "claude-3-haiku",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": Decimal("0.001234"),
        "tool_name": None,
        "tool_args": None,
        "tool_result_summary": None,
        "side_effects": None,
        "privacy_classification": "public",
        "classification_confidence": 0.9,
        "classification_reasoning": None,
        "previous_entry_hash": None,
    }
    base.update(overrides)
    return base


def _orm_entry(user_id: uuid.UUID, **overrides: Any) -> Any:
    """Create a mock ORM AuditLog object with the given user_id."""
    from noa.db.models.audit import AuditLog

    data = _make_audit_entry(user_id=user_id, **overrides)
    obj = AuditLog(**data)
    return obj


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/audit/entries
# ---------------------------------------------------------------------------


class TestAuditEntries:
    """Tests for GET /api/v1/audit/entries endpoint."""

    def _client(self) -> TestClient:
        from noa.api.app import app
        return TestClient(app, raise_server_exceptions=True)

    def test_unauthenticated_returns_401(self) -> None:
        """No auth token → 401."""
        client = self._client()
        resp = client.get("/api/v1/audit/entries")
        assert resp.status_code == 401

    def test_returns_empty_entries_when_no_db(self) -> None:
        """When no DB session factory is configured, returns empty list."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=None):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/entries")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["entries"] == []
        assert body["data"]["total"] == 0

    def test_returns_entries_from_db(self) -> None:
        """When DB has entries for the user, they are returned."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        # Build a real ORM entry (no DB needed — we patch session factory)
        entry = _orm_entry(user_id=fake_user_id)

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = [entry]
        mock_scalar_result.scalar_one.return_value = 1  # total count

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/entries")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert len(body["data"]["entries"]) == 1
        assert body["data"]["entries"][0]["domain"] == "external"
        assert body["data"]["entries"][0]["model_name"] == "claude-3-haiku"

    def test_pagination_params_forwarded(self) -> None:
        """limit and offset query params are accepted."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = []
        mock_scalar_result.scalar_one.return_value = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/entries?limit=10&offset=20")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["limit"] == 10
        assert data["offset"] == 20

    def test_filter_params_accepted(self) -> None:
        """domain, tool_name, privacy_classification filters return 200."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = []
        mock_scalar_result.scalar_one.return_value = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                "/api/v1/audit/entries"
                "?domain=external&tool_name=web_search&privacy_classification=public"
            )

        app.dependency_overrides.clear()

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/audit/verify
# ---------------------------------------------------------------------------


class TestAuditVerify:
    """Tests for GET /api/v1/audit/verify endpoint."""

    def test_unauthenticated_returns_401(self) -> None:
        """No auth → 401."""
        from noa.api.app import app
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/v1/audit/verify")
        assert resp.status_code == 401

    def test_returns_valid_true_for_empty_log(self) -> None:
        """Empty audit log → valid=True, entries_checked=0."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/verify")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is True
        assert data["entries_checked"] == 0
        assert data["broken_at_entry_id"] is None

    def test_returns_no_database_when_factory_none(self) -> None:
        """No DB factory → returns error='no database', valid=True (degraded mode)."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=None):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/verify")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is True
        assert "no database" in data.get("error", "")

    def test_detects_broken_chain(self) -> None:
        """Entry with wrong previous_entry_hash → valid=False, broken_at_entry_id set."""

        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        # Entry 1 with no previous hash (correct for first)
        entry1 = _orm_entry(user_id=fake_user_id)
        entry1.previous_entry_hash = None

        # Entry 2 with WRONG previous hash (tampered)
        entry2 = _orm_entry(user_id=fake_user_id)
        entry2.previous_entry_hash = "deadbeef" * 8  # wrong hash

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = [entry1, entry2]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/verify")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is False
        assert data["broken_at_entry_id"] == str(entry2.id)


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/audit/export
# ---------------------------------------------------------------------------


class TestAuditExport:
    """Tests for GET /api/v1/audit/export endpoint."""

    def test_unauthenticated_returns_401(self) -> None:
        from noa.api.app import app
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/v1/audit/export")
        assert resp.status_code == 401

    def test_returns_json_download(self) -> None:
        """Export returns JSON with attachment content-disposition."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        entry = _orm_entry(user_id=fake_user_id, tool_name="web_search")

        mock_scalar_result = MagicMock()
        mock_scalar_result.scalars.return_value.all.return_value = [entry]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=mock_factory):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/export")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert "audit_export.json" in resp.headers.get("content-disposition", "")

        payload = resp.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["tool_name"] == "web_search"

    def test_export_empty_when_no_db(self) -> None:
        """No DB → returns empty JSON array."""
        from noa.api.app import app
        from noa.auth.middleware import AuthUser, require_auth

        fake_user_id = uuid.uuid4()
        mock_auth_user = AuthUser(user_id=fake_user_id, session_id=uuid.uuid4())

        app.dependency_overrides[require_auth] = lambda: mock_auth_user

        with patch("noa.api.app_state.get_session_factory", return_value=None):
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/api/v1/audit/export")

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        payload = resp.json()
        assert payload == []
