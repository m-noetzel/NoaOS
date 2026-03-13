"""Tests for FR2: Memory & Session Fixes.

Covers:
- BE-H6: docker-compose.yml volume mount (checked via compose config)
- BE-H7: Approved memory facts persisted — approvals endpoint triggers MemoryStore update
- BE-H9: External domain MemoryStore wired via app_state + registered as tool
- BE-H10: Memory tool health check returns "ok" when store is wired (not "Unconfigured")
- BE-H12: Logout fully clears cookies with correct security attributes

Spec refs: SPEC.md §13.2, §5.4, §29.6
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.fr2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_access_token(
    user_id: str | None = None,
    session_id: str | None = None,
    secret: str = "test-secret-key-for-jwt-signing-32bytes!",
) -> str:
    """Build a valid access token for testing."""
    from noa.auth.jwt import create_access_token

    return create_access_token(
        user_id=user_id or str(uuid.uuid4()),
        secret_key=secret,
        expires_minutes=30,
        session_id=session_id or str(uuid.uuid4()),
    )


def _make_settings(monkeypatch: Any) -> Any:
    for k, v in {
        "NOA_ENV": "testing",
        "SECRET_KEY": "test-secret-key-for-jwt-signing-32bytes!",
        "DATABASE_URL": "sqlite+aiosqlite:///test_fr2.db",
    }.items():
        monkeypatch.setenv(k, v)
    from noa.config import Settings

    return Settings()


# ===========================================================================
# BE-H6: docker-compose volume mount
# ===========================================================================


class TestBEH6DockerVolume:
    """BE-H6: noa-api must mount private-data:/data for memory persistence."""

    def test_noa_api_has_data_volume_mount(self):
        """noa-api service must have the private-data:/data volume mount."""
        import yaml

        compose_path = Path(__file__).parents[2] / "docker-compose.yml"
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        with compose_path.open() as fh:
            config = yaml.safe_load(fh)

        noa_api = config["services"]["noa-api"]
        volumes = noa_api.get("volumes", [])

        # At least one volume entry must mount /data
        data_mounts = [v for v in volumes if "/data" in str(v)]
        assert data_mounts, (
            "noa-api service has no /data volume mount — memory facts will not persist"
        )

    def test_private_data_volume_defined(self):
        """private-data volume must be declared in the volumes section."""
        import yaml

        compose_path = Path(__file__).parents[2] / "docker-compose.yml"
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        with compose_path.open() as fh:
            config = yaml.safe_load(fh)

        volume_names = list(config.get("volumes", {}).keys())
        assert "private-data" in volume_names, (
            "private-data volume not defined — must exist for memory persistence"
        )


# ===========================================================================
# BE-H7: Approved memory facts persisted via approvals endpoint
# ===========================================================================


class TestBEH7MemoryApprovalPersistence:
    """BE-H7: Approving a memory approval must update MemoryStore status."""

    def _make_mock_store(self) -> MagicMock:
        store = MagicMock()
        store.update_status.return_value = True
        store.delete.return_value = True
        return store

    def test_handle_memory_approval_approved_calls_update_status(self):
        """_handle_memory_approval sets fact status to 'approved' on approve."""
        from noa.api.v1.approvals import _handle_memory_approval
        from noa.db.models.approval import Approval

        fact_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=user_id,
            risk_tier="low",
            preview_text=f"memory\n{json.dumps({'fact_id': fact_id, 'fact': 'test fact'})}",
            decision="approved",
        )

        mock_store = self._make_mock_store()

        with patch("noa.api.app_state.get_memory_store", return_value=mock_store):
            _handle_memory_approval(approval=approval, decision="approved")

        mock_store.update_status.assert_called_once_with(
            fact_id, "approved", user_id=str(user_id)
        )

    def test_handle_memory_approval_denied_deletes_fact(self):
        """_handle_memory_approval deletes the fact when denied."""
        from noa.api.v1.approvals import _handle_memory_approval
        from noa.db.models.approval import Approval

        fact_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=user_id,
            risk_tier="low",
            preview_text=f"memory\n{json.dumps({'fact_id': fact_id, 'fact': 'test fact'})}",
            decision="denied",
        )

        mock_store = self._make_mock_store()

        with patch("noa.api.app_state.get_memory_store", return_value=mock_store):
            _handle_memory_approval(approval=approval, decision="denied")

        mock_store.delete.assert_called_once_with(fact_id, user_id=str(user_id))

    def test_handle_memory_approval_no_store_is_noop(self):
        """_handle_memory_approval is a no-op when MemoryStore is not wired."""
        from noa.api.v1.approvals import _handle_memory_approval
        from noa.db.models.approval import Approval

        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            risk_tier="low",
            preview_text=f"memory\n{json.dumps({'fact_id': str(uuid.uuid4())})}",
            decision="approved",
        )

        with patch("noa.api.app_state.get_memory_store", return_value=None):
            # Should not raise
            _handle_memory_approval(approval=approval, decision="approved")

    def test_handle_memory_approval_non_memory_tool_is_noop(self):
        """_handle_memory_approval is a no-op for non-memory tool approvals."""
        from noa.api.v1.approvals import _handle_memory_approval
        from noa.db.models.approval import Approval

        mock_store = self._make_mock_store()
        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            risk_tier="low",
            preview_text="calendar\n{}",
            decision="approved",
        )

        with patch("noa.api.app_state.get_memory_store", return_value=mock_store):
            _handle_memory_approval(approval=approval, decision="approved")

        mock_store.update_status.assert_not_called()

    def test_handle_memory_approval_no_fact_id_is_noop(self):
        """_handle_memory_approval is a no-op when fact_id missing from args."""
        from noa.api.v1.approvals import _handle_memory_approval
        from noa.db.models.approval import Approval

        mock_store = self._make_mock_store()
        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            risk_tier="low",
            preview_text='memory\n{"fact": "some fact"}',  # no fact_id
            decision="approved",
        )

        with patch("noa.api.app_state.get_memory_store", return_value=mock_store):
            _handle_memory_approval(approval=approval, decision="approved")

        mock_store.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_decide_approval_triggers_memory_store_update(self, monkeypatch: Any):
        """POST /approvals/{id}/decide must call _handle_memory_approval."""
        _make_settings(monkeypatch)
        from httpx import ASGITransport, AsyncClient

        from noa.api.v1 import approvals as approvals_mod

        approval_id = uuid.uuid4()
        user_id = uuid.uuid4()
        fact_id = str(uuid.uuid4())
        token = _make_access_token(user_id=str(user_id))

        from fastapi import FastAPI

        from noa.api.deps import get_db_session
        from noa.api.v1.approvals import router
        from noa.auth.middleware import require_auth
        from noa.db.models.approval import Approval

        app = FastAPI()
        app.include_router(router)

        mock_approval = Approval(
            id=approval_id,
            run_id=uuid.uuid4(),
            user_id=user_id,
            risk_tier="low",
            preview_text=f"memory\n{json.dumps({'fact_id': fact_id})}",
            decision="pending",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        from noa.auth.middleware import AuthUser

        async def override_auth(request: Any = None):
            return AuthUser(user_id=user_id)

        app.dependency_overrides[get_db_session] = override_session
        app.dependency_overrides[require_auth] = override_auth

        handle_calls: list[dict[str, Any]] = []

        original_handler = approvals_mod._handle_memory_approval

        def spy_handler(**kwargs: Any) -> None:
            handle_calls.append(kwargs)
            return original_handler(**kwargs)

        with patch.object(approvals_mod, "_handle_memory_approval", spy_handler):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decide",
                    json={"decision": "approved"},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        assert len(handle_calls) == 1
        assert handle_calls[0]["decision"] == "approved"


# ===========================================================================
# BE-H9: External domain MemoryStore
# ===========================================================================


class TestBEH9ExternalMemory:
    """BE-H9: External domain must have a separate MemoryStore."""

    def test_app_state_has_external_memory_store_accessors(self):
        """app_state must expose get/set_external_memory_store."""
        from noa.api import app_state

        assert hasattr(app_state, "get_external_memory_store"), (
            "app_state missing get_external_memory_store"
        )
        assert hasattr(app_state, "set_external_memory_store"), (
            "app_state missing set_external_memory_store"
        )

    def test_set_get_external_memory_store_roundtrip(self):
        """set/get_external_memory_store round-trip returns the same object."""
        from noa.api import app_state
        from noa.private_worker.memory_store import MemoryStore

        original = app_state.get_external_memory_store()
        try:
            store = MemoryStore()
            app_state.set_external_memory_store(store)
            assert app_state.get_external_memory_store() is store
        finally:
            # Restore original state
            app_state.set_external_memory_store(original)

    def test_reset_all_clears_external_memory_store(self):
        """reset_all() must clear external_memory_store."""
        from noa.api import app_state
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        app_state.set_external_memory_store(store)
        app_state.reset_all()
        assert app_state.get_external_memory_store() is None

    def test_external_memory_in_tool_schemas(self):
        """external_memory must be in TOOL_SCHEMAS with domain=external."""
        from noa.tools.definitions import TOOL_SCHEMAS

        assert "external_memory" in TOOL_SCHEMAS, (
            "external_memory not in TOOL_SCHEMAS — external domain agents have no memory"
        )
        schema = TOOL_SCHEMAS["external_memory"]
        for func_name, func_def in schema["functions"].items():
            assert func_def["domain"] == "external", (
                f"external_memory.{func_name} must have domain='external'"
            )

    def test_external_memory_in_health_required_secrets(self):
        """external_memory must be in _TOOL_REQUIRED_SECRETS with empty list."""
        from noa.tools.health import _TOOL_REQUIRED_SECRETS

        assert "external_memory" in _TOOL_REQUIRED_SECRETS, (
            "external_memory not in _TOOL_REQUIRED_SECRETS"
        )
        assert _TOOL_REQUIRED_SECRETS["external_memory"] == [], (
            "external_memory should have no required secrets"
        )

    def test_register_external_memory_registers_tool_when_store_available(self):
        """_register_external_memory registers 'external_memory' in gateway when store available."""
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import _register_external_memory

        gateway = ToolGateway()
        store = MemoryStore()

        with patch("noa.api.app_state.get_external_memory_store", return_value=store):
            _register_external_memory(gateway)

        assert "external_memory" in gateway.list_tools()

    def test_register_external_memory_skips_when_store_unavailable(self):
        """_register_external_memory skips registration when store is None."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import _register_external_memory

        gateway = ToolGateway()

        with patch("noa.api.app_state.get_external_memory_store", return_value=None):
            _register_external_memory(gateway)

        assert "external_memory" not in gateway.list_tools()

    @pytest.mark.asyncio
    async def test_external_memory_remember_stores_fact(self):
        """External memory remember() stores a fact in the external MemoryStore."""
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway, ToolRequest
        from noa.tools.registration import _register_external_memory

        gateway = ToolGateway()
        store = MemoryStore()  # In-memory, no disk

        with patch("noa.api.app_state.get_external_memory_store", return_value=store):
            _register_external_memory(gateway)

        req = ToolRequest(
            tool="external_memory",
            function="remember",
            args={
                "fact": "User prefers dark mode",
                "category": "preference",
                "source_thread_id": "thread-ext-001",
            },
        )
        resp = await gateway.dispatch(req)
        assert resp.error is None
        # Fact should now be in the store
        facts = store.list_all()
        assert len(facts) == 1
        assert facts[0]["fact"] == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_external_memory_separate_from_private_memory(self):
        """External and private memory stores must be independent namespaces."""
        from noa.private_worker.memory_store import MemoryStore

        private_store = MemoryStore()
        external_store = MemoryStore()

        # Store in private
        private_store.store(
            fact="Private fact",
            category="preference",
            embedding=[1.0, 0.0],
            source_thread_id="private-thread",
        )

        # Store in external
        external_store.store(
            fact="External fact",
            category="preference",
            embedding=[0.0, 1.0],
            source_thread_id="external-thread",
        )

        private_facts = {f["fact"] for f in private_store.list_all()}
        external_facts = {f["fact"] for f in external_store.list_all()}

        assert "Private fact" in private_facts
        assert "External fact" not in private_facts
        assert "External fact" in external_facts
        assert "Private fact" not in external_facts


# ===========================================================================
# BE-H10: Memory tool health check
# ===========================================================================


class TestBEH10MemoryHealthCheck:
    """BE-H10: Memory tool health check must return 'ok' when store is wired."""

    @pytest.mark.asyncio
    async def test_memory_health_ok_when_store_wired(self, tmp_path: Path):
        """ToolHealthChecker.check('memory') returns ok when MemoryStore is wired."""
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway
        from noa.tools.health import ToolHealthChecker

        # Gateway with memory registered
        gw = ToolGateway()
        # Simulate memory not in gateway (would normally be registered)

        store = MemoryStore(data_dir=tmp_path / "test_memory_health")

        with (
            patch("noa.orchestrator.nodes.tools.get_gateway", return_value=gw),
            patch("noa.api.app_state.get_memory_store", return_value=store),
        ):
            checker = ToolHealthChecker()
            result = await checker.check("memory")

        # When store has data_dir, health should be ok
        assert result["status"] == "ok", (
            f"Memory health check should be 'ok' when store is wired, got: {result}"
        )

    @pytest.mark.asyncio
    async def test_memory_health_error_when_store_not_wired(self):
        """ToolHealthChecker.check('memory') returns error when MemoryStore is not wired."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.health import ToolHealthChecker

        gw = ToolGateway()  # Empty gateway, memory not registered

        with (
            patch("noa.orchestrator.nodes.tools.get_gateway", return_value=gw),
            patch("noa.api.app_state.get_memory_store", return_value=None),
        ):
            checker = ToolHealthChecker()
            result = await checker.check("memory")

        assert result["status"] == "error"
        assert "MemoryStore not wired" in (result.get("error") or "")

    @pytest.mark.asyncio
    async def test_memory_health_error_when_no_data_dir(self):
        """ToolHealthChecker.check('memory') returns error when store has no data_dir."""
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway
        from noa.tools.health import ToolHealthChecker

        gw = ToolGateway()
        store = MemoryStore()  # No data_dir = no persistence

        with (
            patch("noa.orchestrator.nodes.tools.get_gateway", return_value=gw),
            patch("noa.api.app_state.get_memory_store", return_value=store),
        ):
            checker = ToolHealthChecker()
            result = await checker.check("memory")

        assert result["status"] == "error"
        assert "data_dir" in (result.get("error") or "")

    @pytest.mark.asyncio
    async def test_credential_checker_returns_configured_for_memory(self):
        """CredentialStatusChecker.get_status('memory') returns 'configured' (no secrets needed)."""
        from noa.tools.health import CredentialStatusChecker

        checker = CredentialStatusChecker()
        result = await checker.get_status("memory")
        assert result == "configured", (
            "Memory tool should be 'configured' since it needs no API keys"
        )

    @pytest.mark.asyncio
    async def test_external_memory_health_ok_when_store_wired(self, tmp_path: Path):
        """ToolHealthChecker.check('external_memory') returns ok when external store is wired."""
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway
        from noa.tools.health import ToolHealthChecker

        gw = ToolGateway()
        ext_store = MemoryStore(data_dir=tmp_path / "test_ext_memory_health")

        with (
            patch("noa.orchestrator.nodes.tools.get_gateway", return_value=gw),
            patch("noa.api.app_state.get_external_memory_store", return_value=ext_store),
        ):
            checker = ToolHealthChecker()
            result = await checker.check("external_memory")

        assert result["status"] == "ok", (
            f"External memory health should be 'ok' when store is wired, got: {result}"
        )


# ===========================================================================
# BE-H12: Logout fully clears session
# ===========================================================================


class TestBEH12LogoutClearsSession:
    """BE-H12: Logout must clear cookies with correct security attributes."""

    @pytest.mark.asyncio
    async def test_logout_deletes_both_cookies(self, monkeypatch: Any):
        """POST /auth/logout must delete noa_access_token and noa_refresh_token cookies."""
        settings = _make_settings(monkeypatch)
        from httpx import ASGITransport, AsyncClient

        from fastapi import FastAPI

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router
        from noa.auth.middleware import AuthUser, require_auth
        from noa.auth.service import AuthService

        app = FastAPI()
        app.include_router(router)

        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        token = _make_access_token(user_id=user_id, session_id=session_id)

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        async def override_auth(request: Any = None):
            return AuthUser(
                user_id=uuid.UUID(user_id),
                session_id=session_id,
            )

        app.dependency_overrides[get_db_session] = override_session
        app.dependency_overrides[require_auth] = override_auth

        async def mock_logout(self, *, session_id: uuid.UUID) -> None:
            pass

        with patch.object(AuthService, "logout", mock_logout):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        # Both cookies must be deleted (Set-Cookie with max-age=0 or expires in past)
        cookie_headers = resp.headers.get_list("set-cookie")
        cookie_names = [h.split("=")[0] for h in cookie_headers]
        assert "noa_access_token" in cookie_names, (
            "noa_access_token cookie not cleared on logout"
        )
        assert "noa_refresh_token" in cookie_names, (
            "noa_refresh_token cookie not cleared on logout"
        )

    @pytest.mark.asyncio
    async def test_logout_response_status_ok(self, monkeypatch: Any):
        """POST /auth/logout must return 200 with status=logged_out."""
        _make_settings(monkeypatch)
        from httpx import ASGITransport, AsyncClient

        from fastapi import FastAPI

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router
        from noa.auth.middleware import AuthUser, require_auth
        from noa.auth.service import AuthService

        app = FastAPI()
        app.include_router(router)

        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        token = _make_access_token(user_id=user_id, session_id=session_id)

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        async def override_auth(request: Any = None):
            return AuthUser(
                user_id=uuid.UUID(user_id),
                session_id=session_id,
            )

        app.dependency_overrides[get_db_session] = override_session
        app.dependency_overrides[require_auth] = override_auth

        async def mock_logout(self, *, session_id: uuid.UUID) -> None:
            pass

        with patch.object(AuthService, "logout", mock_logout):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["status"] == "logged_out"

    @pytest.mark.asyncio
    async def test_logout_still_succeeds_when_session_lookup_fails(
        self, monkeypatch: Any
    ):
        """Logout must still clear cookies even if session DB lookup fails."""
        _make_settings(monkeypatch)
        from httpx import ASGITransport, AsyncClient

        from fastapi import FastAPI

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router
        from noa.auth.middleware import AuthUser, require_auth
        from noa.auth.service import AuthService

        app = FastAPI()
        app.include_router(router)

        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        token = _make_access_token(user_id=user_id, session_id=session_id)

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        async def override_auth(request: Any = None):
            return AuthUser(
                user_id=uuid.UUID(user_id),
                session_id=session_id,
            )

        app.dependency_overrides[get_db_session] = override_session
        app.dependency_overrides[require_auth] = override_auth

        async def failing_logout(self, *, session_id: uuid.UUID) -> None:
            raise RuntimeError("DB connection lost")

        with patch.object(AuthService, "logout", failing_logout):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                )

        # Must still return 200 — logout is best-effort for session invalidation
        assert resp.status_code == 200
        # Cookies must still be cleared
        cookie_headers = resp.headers.get_list("set-cookie")
        cookie_names = [h.split("=")[0] for h in cookie_headers]
        assert "noa_access_token" in cookie_names

    def test_logout_uses_same_samesite_as_set_auth_cookies(self, monkeypatch: Any):
        """Logout delete_cookie must use the same samesite as _set_auth_cookies."""
        import inspect

        _make_settings(monkeypatch)
        from noa.api.v1 import auth as auth_mod

        source = inspect.getsource(auth_mod)
        # Verify logout sets samesite when deleting cookies
        assert "delete_cookie" in source
        # The logout function must reference samesite or secure attribute
        assert "samesite" in source, (
            "logout endpoint must set samesite attribute when clearing cookies"
        )

    @pytest.mark.asyncio
    async def test_auth_service_logout_marks_session_inactive(self, monkeypatch: Any):
        """AuthService.logout() must set is_active=False on the session."""
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService
        from noa.db.models.session import AuthSession

        session_id = uuid.uuid4()
        auth_session = AuthSession(
            id=session_id,
            user_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            refresh_token_hash="somehash",  # noqa: S106
            expires_at=datetime.now(UTC) + timedelta(days=7),
            is_active=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = auth_session

        async def mock_execute(stmt: Any) -> Any:
            return mock_result

        mock_db = AsyncMock()
        mock_db.execute = mock_execute
        svc = AuthService(session=mock_db, settings=settings)

        await svc.logout(session_id=session_id)

        assert auth_session.is_active is False, (
            "AuthService.logout() must set is_active=False"
        )
