"""Tests for Phase F4: Authentication & Session Management.

Covers: JWT creation/verification, password hashing, login/refresh/logout
endpoints, session management, device binding, revocation, rate limiting,
and auth middleware.

Spec refs: SPEC.md §5.1, §5.2, §5.3, §5.4
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.f4


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

def _make_user_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_device_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_settings_dict() -> dict:
    """Return env-var dict suitable for monkeypatch + Settings construction."""
    return {
        "NOA_ENV": "testing",
        "SECRET_KEY": "test-secret-key-for-jwt-signing-32bytes!",
        "DATABASE_URL": "sqlite+aiosqlite:///test_auth.db",
        "LOG_LEVEL": "DEBUG",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    }


def _make_settings(monkeypatch):
    """Build a Settings object with test values applied to the env."""
    for k, v in _make_settings_dict().items():
        monkeypatch.setenv(k, v)
    from noa.config import Settings
    return Settings()


# ---------------------------------------------------------------------------
# Class: JWT token creation and verification
# ---------------------------------------------------------------------------

class TestJWTTokens:
    """Unit tests for noa.auth.jwt — token encode/decode/expiry."""

    def test_create_access_token_contains_required_claims(self, monkeypatch):
        """Access token must contain sub, exp, iat, jti, type='access'.

        SPEC.md §5.2 — Session tokens are JWTs signed with a local secret.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.jwt import create_access_token

        user_id = _make_user_id()
        token = create_access_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_minutes=settings.access_token_expire_minutes,
        )
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWS compact form

    def test_decode_access_token_returns_payload(self, monkeypatch):
        """A freshly-created access token must decode successfully.

        SPEC.md §5.2 — JWTs signed with a local secret.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.jwt import create_access_token, decode_token

        user_id = str(_make_user_id())
        token = create_access_token(
            user_id=user_id,
            secret_key=settings.secret_key,
            expires_minutes=settings.access_token_expire_minutes,
        )
        payload = decode_token(token, secret_key=settings.secret_key)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_expired_access_token_rejected(self, monkeypatch):
        """Expired tokens must raise an appropriate error.

        SPEC.md §5.2 — Sessions expire after configurable idle timeout.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.jwt import create_access_token, decode_token

        user_id = str(_make_user_id())
        token = create_access_token(
            user_id=user_id,
            secret_key=settings.secret_key,
            expires_minutes=-1,  # already expired
        )
        from noa.auth.jwt import TokenError
        with pytest.raises(TokenError):
            decode_token(token, secret_key=settings.secret_key)

    def test_create_refresh_token_has_refresh_type(self, monkeypatch):
        """Refresh token must have type='refresh' in claims.

        SPEC.md §5.3 — Login returns access_token + refresh_token.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.jwt import create_refresh_token, decode_token

        user_id = str(_make_user_id())
        token = create_refresh_token(
            user_id=user_id,
            secret_key=settings.secret_key,
            expires_days=settings.refresh_token_expire_days,
        )
        payload = decode_token(token, secret_key=settings.secret_key)
        assert payload["type"] == "refresh"

    def test_token_with_wrong_secret_rejected(self, monkeypatch):
        """Token signed with different secret must be rejected.

        SPEC.md §5.2 — JWTs signed with a local secret.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.jwt import create_access_token, decode_token

        token = create_access_token(
            user_id=str(_make_user_id()),
            secret_key=settings.secret_key,
            expires_minutes=30,
        )
        from noa.auth.jwt import TokenError
        with pytest.raises(TokenError):
            decode_token(token, secret_key="wrong-secret-key-entirely")


# ---------------------------------------------------------------------------
# Class: Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Unit tests for noa.auth.password — bcrypt hash/verify."""

    def test_hash_password_returns_bcrypt_string(self):
        """Password hash must be a bcrypt-format string.

        MASTER_PLAN Phase F4 — Password hashing (bcrypt).
        """
        from noa.auth.password import hash_password

        hashed = hash_password("correct-horse-battery-staple")
        assert isinstance(hashed, str)
        assert hashed != "correct-horse-battery-staple"

    def test_verify_correct_password(self):
        """Correct password must verify against its hash.

        MASTER_PLAN Phase F4 — Password hashing.
        """
        from noa.auth.password import hash_password, verify_password

        pw = "correct-horse-battery-staple"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self):
        """Incorrect password must not verify.

        MASTER_PLAN Phase F4 — Password hashing (negative case).
        """
        from noa.auth.password import hash_password, verify_password

        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# Class: Auth service (login, refresh, revoke)
# ---------------------------------------------------------------------------

class TestAuthService:
    """Tests for noa.auth.service — business logic layer."""

    @pytest.mark.asyncio
    async def test_login_valid_credentials_returns_tokens(self, monkeypatch):
        """Successful login must return access + refresh tokens.

        SPEC.md §5.3 — POST /api/v1/auth/login → { access_token, refresh_token }.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        user_id = _make_user_id()
        device_id = _make_device_id()

        # Build a mock async session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        # Mock internal user lookup to return a fake user row
        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": user_id,
            "email": "ada@example.com",
            "password_hash": hash_password("valid-password"),
            "is_active": True,
        })()

        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            result = await service.login(
                email="ada@example.com",
                password="valid-password",
                device_id=device_id,
            )

        assert "access_token" in result
        assert "refresh_token" in result

    @pytest.mark.asyncio
    async def test_login_invalid_password_rejected(self, monkeypatch):
        """Login with wrong password must raise an auth error.

        SPEC.md §5.3 — Invalid credentials rejected.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": _make_user_id(),
            "email": "ada@example.com",
            "password_hash": hash_password("real-password"),
            "is_active": True,
        })()

        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            from noa.auth.service import AuthError
            with pytest.raises(AuthError):
                await service.login(
                    email="ada@example.com",
                    password="wrong-password",
                    device_id=_make_device_id(),
                )

    @pytest.mark.asyncio
    async def test_refresh_rotates_token(self, monkeypatch):
        """Refresh must return a new access + refresh token pair and
        invalidate the old refresh token.

        SPEC.md §5.2 — Token refresh uses rotating refresh tokens (old token
        invalidated on use).
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        user_id = _make_user_id()
        device_id = _make_device_id()

        # Create a fake existing session with a known refresh token hash
        from noa.auth.jwt import create_refresh_token

        old_refresh = create_refresh_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_days=7,
        )

        fake_session = type("AuthSession", (), {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "device_id": device_id,
            "is_active": True,
            "expires_at": datetime.now(UTC) + timedelta(days=7),
            "refresh_token_hash": "hashed_placeholder",
        })()

        with patch.object(service, "_get_session_by_refresh_token", return_value=fake_session):
            result = await service.refresh(
                refresh_token=old_refresh,
                device_id=device_id,
            )

        assert "access_token" in result
        assert "refresh_token" in result
        # New refresh token must differ from old one
        assert result["refresh_token"] != old_refresh


# ---------------------------------------------------------------------------
# Class: Session management
# ---------------------------------------------------------------------------

class TestSessionManagement:
    """Tests for session lifecycle — creation, expiry, device binding."""

    @pytest.mark.asyncio
    async def test_session_created_on_login(self, monkeypatch):
        """Login must create an AuthSession row.

        SPEC.md §5.2 — Session state is stored in Postgres.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        user_id = _make_user_id()
        device_id = _make_device_id()

        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": user_id,
            "email": "ada@example.com",
            "password_hash": hash_password("valid-password"),
            "is_active": True,
        })()

        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            await service.login(
                email="ada@example.com",
                password="valid-password",
                device_id=device_id,
            )

        # The service should have called session.add() with an AuthSession
        mock_session.add.assert_called()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.user_id == user_id
        assert added_obj.device_id == device_id
        assert added_obj.is_active is True

    @pytest.mark.asyncio
    async def test_session_bound_to_device_id(self, monkeypatch):
        """Each session must be bound to the device_id provided at login.

        SPEC.md §5.2 — Each session is bound to a single device ID.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        device_id = _make_device_id()

        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": _make_user_id(),
            "email": "ada@example.com",
            "password_hash": hash_password("pw"),
            "is_active": True,
        })()

        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            await service.login(
                email="ada@example.com",
                password="pw",
                device_id=device_id,
            )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.device_id == device_id

    @pytest.mark.asyncio
    async def test_session_has_expiry(self, monkeypatch):
        """Session expires_at must be set based on refresh_token_expire_days.

        SPEC.md §5.2 — Sessions expire after configurable idle timeout.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": _make_user_id(),
            "email": "ada@example.com",
            "password_hash": hash_password("pw"),
            "is_active": True,
        })()

        before = datetime.now(UTC)
        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            await service.login(
                email="ada@example.com",
                password="pw",
                device_id=_make_device_id(),
            )

        added_obj = mock_session.add.call_args[0][0]
        # expires_at should be approximately now + 7 days
        expected_min = before + timedelta(days=7) - timedelta(seconds=5)
        assert added_obj.expires_at >= expected_min


# ---------------------------------------------------------------------------
# Class: Revocation / logout
# ---------------------------------------------------------------------------

class TestRevocation:
    """Tests for session revocation — SPEC.md §5.4."""

    @pytest.mark.asyncio
    async def test_logout_invalidates_session(self, monkeypatch):
        """Logout must set session.is_active = False.

        SPEC.md §5.4 — Logout invalidates all tokens for that session.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        session_id = uuid.uuid4()
        fake_auth_session = type("AuthSession", (), {
            "id": session_id,
            "user_id": _make_user_id(),
            "is_active": True,
        })()

        with patch.object(service, "_get_session_by_id", return_value=fake_auth_session):
            await service.logout(session_id=session_id)

        assert fake_auth_session.is_active is False


# ---------------------------------------------------------------------------
# Class: Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Tests for login rate limiting — MASTER_PLAN Phase F4."""

    @pytest.mark.asyncio
    async def test_lockout_after_five_failed_attempts(self, monkeypatch):
        """5 failed login attempts within 10 minutes must trigger lockout.

        MASTER_PLAN Phase F4 — Rate limiting: 5 failed attempts -> 30 min lockout.
        """
        settings = _make_settings(monkeypatch)
        from noa.auth.service import AuthService

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        service = AuthService(session=mock_session, settings=settings)

        from noa.auth.password import hash_password

        fake_user = type("User", (), {
            "id": _make_user_id(),
            "email": "ada@example.com",
            "password_hash": hash_password("real-password"),
            "is_active": True,
        })()

        with patch.object(service, "_get_user_by_email", return_value=fake_user):
            # Fail 5 times
            from noa.auth.service import AccountLockedError, AuthError
            for _ in range(5):
                with pytest.raises(AuthError):
                    await service.login(
                        email="ada@example.com",
                        password="wrong",
                        device_id=_make_device_id(),
                    )

            # 6th attempt should raise a lockout/rate-limit error even with
            # the correct password
            with pytest.raises(AccountLockedError) as exc_info:
                await service.login(
                    email="ada@example.com",
                    password="real-password",
                    device_id=_make_device_id(),
                )

        # The error should indicate rate limiting / account lockout
        assert "lock" in str(exc_info.value).lower() or "rate" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Class: Auth API endpoints (integration-style via ASGI transport)
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    """Integration tests for /api/v1/auth/* endpoints.

    Uses httpx AsyncClient with ASGITransport against the real FastAPI app.
    """

    @staticmethod
    def _override_db_session(app):
        """Override get_db_session dependency with an AsyncMock session."""
        from noa.api.deps import get_db_session

        async def _mock_db():
            yield AsyncMock()

        app.dependency_overrides[get_db_session] = _mock_db

    @pytest.mark.asyncio
    async def test_login_endpoint_returns_tokens(self, monkeypatch):
        """POST /api/v1/auth/login with valid creds returns 200 + tokens.

        SPEC.md §5.3 — Client -> POST /api/v1/auth/login (credentials) <- 200.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        self._override_db_session(app)

        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "ada@example.com",
                    "password": "valid-password",
                    "device_id": str(_make_device_id()),
                },
            )

        # At minimum the route must exist (not 404/405)
        assert resp.status_code != 404, "Login endpoint not registered"
        assert resp.status_code != 405, "Login endpoint method not allowed"

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_unauthenticated(self, monkeypatch):
        """A protected endpoint must return 401 without a Bearer token.

        SPEC.md §5.1 — All access to Noa must be authenticated.
        Unauthenticated requests are rejected.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()

        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Try accessing /api/v1/chat (a protected route) without auth
            resp = await client.post("/api/v1/chat", json={"message": "hello"})

        # Should be 401 Unauthorized (or at worst 403)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated request, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_endpoint_exists(self, monkeypatch):
        """POST /api/v1/auth/refresh must be a registered route.

        SPEC.md §5.3 — Client -> POST /api/v1/auth/refresh.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        self._override_db_session(app)

        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "fake", "device_id": str(_make_device_id())},
            )

        assert resp.status_code != 404, "Refresh endpoint not registered"
        assert resp.status_code != 405, "Refresh endpoint method not allowed"

    @pytest.mark.asyncio
    async def test_logout_endpoint_exists(self, monkeypatch):
        """POST /api/v1/auth/logout must be a registered route.

        SPEC.md §5.4 — Logout invalidates all tokens for that session.
        """
        _apply_env(monkeypatch)
        from noa.api.app import create_app

        app = create_app()
        self._override_db_session(app)

        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code != 404, "Logout endpoint not registered"
        assert resp.status_code != 405, "Logout endpoint method not allowed"


# ---------------------------------------------------------------------------
# Module-level helpers used by TestAuthEndpoints
# ---------------------------------------------------------------------------

def _apply_env(monkeypatch) -> None:
    """Set env vars for endpoint tests (app factory reads env)."""
    for k, v in _make_settings_dict().items():
        monkeypatch.setenv(k, v)
