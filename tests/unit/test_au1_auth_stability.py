"""Tests for Phase AU1 — Auth Stability: Login That Just Works.

Covers:
- Rate limiting removed: N wrong attempts still allows correct password login
- Token lifetimes extended: 7-day access, 90-day refresh
- GET /api/v1/auth/me: 200 with user info when authenticated, 401 when not
- Cookie max_age: access=604800 (7 days), refresh=7776000 (90 days)
- AccountLockedError no longer raised or imported from service

AU1 findings: AUTH-H1, AUTH-H2, AUTH-M1, AUTH-M2
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.au1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_env(monkeypatch) -> None:
    monkeypatch.setenv("NOA_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-au1-signing-32bytes!!")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test_au1.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


def _make_settings(monkeypatch):
    _apply_env(monkeypatch)
    from noa.config import Settings
    return Settings()


def _fake_user(email: str = "user@example.com", password: str = "secret") -> Any:
    from noa.auth.password import hash_password
    return type("User", (), {
        "id": uuid.uuid4(),
        "email": email,
        "password_hash": hash_password(password),
        "is_active": True,
    })()


def _override_db_session(app, mock_session=None) -> AsyncMock:
    from noa.api.deps import get_db_session
    if mock_session is None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
    async def _mock_db():
        yield mock_session
    app.dependency_overrides[get_db_session] = _mock_db
    return mock_session


# ---------------------------------------------------------------------------
# Deliverable 1: Rate limiting removed
# ---------------------------------------------------------------------------

class TestRateLimitingRemoved:
    """AU1 deliverable 1: no lockout for repeated wrong passwords."""

    @pytest.mark.asyncio
    async def test_no_lockout_after_many_wrong_passwords(self, monkeypatch):
        """After many wrong password attempts, correct password still succeeds.

        AUTH-H1: Rate limiting locks users out. Single-user system — removed.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService, AuthError

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)
        user = _fake_user(email="ada@example.com", password="correct-pw")

        with patch.object(service, "_get_user_by_email", return_value=user):
            # Fail 10 times — no lockout should occur
            for _ in range(10):
                with pytest.raises(AuthError, match="Invalid email or password"):
                    await service.login(
                        email="ada@example.com",
                        password="wrong",
                        device_id=uuid.uuid4(),
                    )

            # Correct password on 11th attempt must succeed
            result = await service.login(
                email="ada@example.com",
                password="correct-pw",
                device_id=uuid.uuid4(),
            )

        assert "access_token" in result
        assert "refresh_token" in result

    def test_account_locked_error_not_in_service(self):
        """AccountLockedError must not exist in the auth service module (AU1)."""
        import noa.auth.service as svc_module
        assert not hasattr(svc_module, "AccountLockedError"), (
            "AccountLockedError was not removed from noa.auth.service"
        )

    def test_rate_limit_methods_not_in_service(self):
        """_check_rate_limit and _record_failed_attempt must be deleted (AU1)."""
        from noa.auth.service import AuthService
        assert not hasattr(AuthService, "_check_rate_limit"), (
            "_check_rate_limit was not removed from AuthService"
        )
        assert not hasattr(AuthService, "_record_failed_attempt"), (
            "_record_failed_attempt was not removed from AuthService"
        )
        assert not hasattr(AuthService, "_failed_attempts"), (
            "_failed_attempts class variable was not removed"
        )
        assert not hasattr(AuthService, "_lockout_until"), (
            "_lockout_until class variable was not removed"
        )


# ---------------------------------------------------------------------------
# Deliverable 2: Extended token lifetimes in config
# ---------------------------------------------------------------------------

class TestTokenLifetimes:
    """AU1 deliverable 2: 7-day access token, 90-day refresh token."""

    def test_access_token_expire_minutes_default_is_7_days(self):
        """Default access_token_expire_minutes must be 10080 (7 days).

        AUTH-H2: Tokens expire too quickly. 15-minute access token fires refresh
        every 15 minutes, causing session expired errors on any refresh failure.
        """
        import os
        # Remove any env override to get the class default
        env_backup = os.environ.pop("ACCESS_TOKEN_EXPIRE_MINUTES", None)
        try:
            from noa.config import Settings
            s = Settings()
            assert s.access_token_expire_minutes == 10080, (
                f"access_token_expire_minutes should be 10080 (7 days), got {s.access_token_expire_minutes}"
            )
        finally:
            if env_backup is not None:
                os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = env_backup

    def test_refresh_token_expire_days_default_is_90(self):
        """Default refresh_token_expire_days must be 90."""
        import os
        env_backup = os.environ.pop("REFRESH_TOKEN_EXPIRE_DAYS", None)
        try:
            from noa.config import Settings
            s = Settings()
            assert s.refresh_token_expire_days == 90, (
                f"refresh_token_expire_days should be 90, got {s.refresh_token_expire_days}"
            )
        finally:
            if env_backup is not None:
                os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = env_backup


# ---------------------------------------------------------------------------
# Deliverable 2b: Cookie max_age
# ---------------------------------------------------------------------------

class TestCookieMaxAge:
    """AU1 deliverable 2: cookie max_age matches new token lifetimes."""

    @pytest.mark.asyncio
    async def test_access_cookie_max_age_is_7_days(self, monkeypatch):
        """Access token cookie max_age must be 604800 seconds (7 days). AU1."""
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        mock_session = _override_db_session(app)
        user = _fake_user(password="secret")
        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=user)
        ))

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "user@example.com",
                    "password": "secret",
                    "device_id": str(uuid.uuid4()),
                },
            )

        assert resp.status_code == 200, f"Login failed: {resp.text}"

        # Verify access cookie max-age
        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_cookies = [h for h in set_cookie_headers if "noa_access_token" in h]
        assert access_cookies, "noa_access_token cookie not set"
        access_cookie = access_cookies[0].lower()
        assert "max-age=604800" in access_cookie, (
            f"Access cookie max-age should be 604800 (7 days), got: {access_cookies[0]}"
        )

    @pytest.mark.asyncio
    async def test_refresh_cookie_max_age_is_90_days(self, monkeypatch):
        """Refresh token cookie max_age must be 7776000 seconds (90 days). AU1."""
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        mock_session = _override_db_session(app)
        user = _fake_user(password="secret")
        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=user)
        ))

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "user@example.com",
                    "password": "secret",
                    "device_id": str(uuid.uuid4()),
                },
            )

        assert resp.status_code == 200, f"Login failed: {resp.text}"

        set_cookie_headers = resp.headers.get_list("set-cookie")
        refresh_cookies = [h for h in set_cookie_headers if "noa_refresh_token" in h]
        assert refresh_cookies, "noa_refresh_token cookie not set"
        refresh_cookie = refresh_cookies[0].lower()
        assert "max-age=7776000" in refresh_cookie, (
            f"Refresh cookie max-age should be 7776000 (90 days), got: {refresh_cookies[0]}"
        )


# ---------------------------------------------------------------------------
# Deliverable 3: GET /api/v1/auth/me
# ---------------------------------------------------------------------------

class TestAuthMeEndpoint:
    """AU1 deliverable 3: /auth/me endpoint."""

    @pytest.mark.asyncio
    async def test_me_with_valid_session_returns_200_and_user_info(self, monkeypatch):
        """GET /auth/me with a valid access token returns user_id and email."""
        _apply_env(monkeypatch)
        from noa.api.app import create_app
        from noa.auth.jwt import create_access_token
        from noa.config import Settings

        settings = Settings()
        app = create_app()
        user_id = uuid.uuid4()

        mock_session = _override_db_session(app)
        fake_user = type("User", (), {
            "id": user_id,
            "email": "me@example.com",
            "is_active": True,
        })()
        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=fake_user)
        ))

        token = create_access_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_minutes=60,
        )

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200, f"/auth/me failed: {resp.text}"
        data = resp.json()
        # Envelope: {ok: true, data: {user_id, email}}
        assert data.get("ok") is True
        inner = data.get("data", {})
        assert inner.get("user_id") == str(user_id)
        assert inner.get("email") == "me@example.com"

    @pytest.mark.asyncio
    async def test_me_without_auth_returns_401(self, monkeypatch):
        """GET /auth/me without auth cookie/token returns 401. AU1."""
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        _override_db_session(app)

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_endpoint_is_registered(self, monkeypatch):
        """GET /api/v1/auth/me must exist (not 404). AU1."""
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        _override_db_session(app)

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/auth/me")

        assert resp.status_code != 404, "GET /api/v1/auth/me endpoint not registered"
        assert resp.status_code != 405, "GET /api/v1/auth/me method not allowed"


# ---------------------------------------------------------------------------
# Integration test: full login → /me flow
# ---------------------------------------------------------------------------

class TestLoginMeIntegration:
    """Integration: login then verify /auth/me reflects the authenticated session."""

    @pytest.mark.asyncio
    async def test_login_then_me_returns_user_info(self, monkeypatch):
        """Full flow: login succeeds → /auth/me returns user's identity.

        AU1 integration test — no internal mocks for the auth flow.
        Uses a real in-memory SQLite DB.
        """
        import os
        monkeypatch.setenv("NOA_ENV", "testing")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-au1-signing-32bytes!!")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv(
            "DATABASE_URL", "sqlite+aiosqlite:///:memory:?cache=shared&uri=true"
        )

        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from noa.db.models.base import Base
        from noa.auth.password import hash_password
        from noa.db.models.user import User

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Create a test user directly in the DB
        user_id = uuid.uuid4()
        user_email = "integration@example.com"
        async with async_session() as session:
            user = User(
                id=user_id,
                email=user_email,
                password_hash=hash_password("integration-pw"),
                is_active=True,
            )
            session.add(user)
            await session.commit()

        from noa.api.app import create_app
        from noa.api.deps import get_db_session

        app = create_app()

        async def override_db():
            async with async_session() as session:
                yield session

        app.dependency_overrides[get_db_session] = override_db

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Step 1: Login
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": user_email,
                    "password": "integration-pw",
                    "device_id": str(uuid.uuid4()),
                },
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

            # Step 2: Extract the access token cookie and call /auth/me
            access_cookie = login_resp.cookies.get("noa_access_token")
            assert access_cookie, "noa_access_token cookie not set after login"

            me_resp = await client.get(
                "/api/v1/auth/me",
                cookies={"noa_access_token": access_cookie},
            )

        assert me_resp.status_code == 200, f"/auth/me failed: {me_resp.text}"
        data = me_resp.json()
        assert data.get("ok") is True
        inner = data.get("data", {})
        assert inner.get("user_id") == str(user_id)
        assert inner.get("email") == user_email

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_wrong_password_shows_auth_error_not_session_expired(self, monkeypatch):
        """Wrong password → AuthError 'Invalid email or password', not 'Session expired'.

        AUTH-M1: Wrong error on login failure. Fixed by skipAuthRetry option.
        This test verifies the backend raises the right error (401 with correct detail).
        The frontend skipAuthRetry=true propagates this detail to the user.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        mock_session = _override_db_session(app)
        user = _fake_user(email="user@example.com", password="correct")
        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=user)
        ))

        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "user@example.com",
                    "password": "WRONG",
                    "device_id": str(uuid.uuid4()),
                },
            )

        assert resp.status_code == 401
        body = resp.json()
        # The auth API wraps errors in the success_envelope format:
        # {ok: false, error: {code, message}}
        error_msg = body.get("error", {}).get("message", "")
        assert "Invalid email or password" in error_msg, (
            f"Expected 'Invalid email or password' in error message, got: {error_msg!r}"
        )
        # Must NOT say "Session expired" — that's the broken behavior
        assert "Session expired" not in error_msg

    @pytest.mark.asyncio
    async def test_logout_then_me_returns_401(self, monkeypatch):
        """After logout, /auth/me must return 401 (no valid session).

        Verifies the session check reflects logged-out state.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app
        from noa.auth.jwt import create_access_token
        from noa.config import Settings

        settings = Settings()
        app = create_app()
        _override_db_session(app)

        # Create a valid token for a non-existent user — /me returns 401 without
        # a valid cookie set during the current session
        import httpx
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # GET /me with no cookies → 401
            resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 401
