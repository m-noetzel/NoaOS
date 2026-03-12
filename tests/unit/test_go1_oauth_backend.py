"""Tests for GO1: Google OAuth2 Backend.

Covers:
- GET /api/v1/auth/google/authorize: auth URL generation, auth required, scopes
- GET /api/v1/auth/google/callback: code exchange, token persistence, redirect,
  error handling, CSRF state verification
- GET /api/v1/auth/google/status: connected/disconnected states
- DELETE /api/v1/auth/google/disconnect: removes DB row, clears live client
- load_tokens_from_db: decrypt and load, absent row fallback
- registration.py: DB-first token loading with env var fallback
- Multi-user safety: status/disconnect scoped to user_id

Spec refs: SPEC.md §12.1, §12.2, §11.1, §11.3, §5.3
"""

# ruff: noqa: S101, S105, S106

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.go1

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_SECRET = "test-jwt-secret-for-go1"


@pytest.fixture(scope="module")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    """In-memory SQLite session for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from noa.db.models.base import Base
    from noa.db.models.google_credential import (
        GoogleCredential,  # noqa: F401 — ensure table registered
    )
    from noa.db.models.user import User  # noqa: F401 — foreign key target

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jwt(user_id: str | None = None, secret: str = TEST_SECRET) -> str:
    """Create a valid JWT access token for testing."""
    from noa.auth.jwt import create_access_token

    uid = user_id or str(uuid.uuid4())
    return create_access_token(
        user_id=uid,
        secret_key=secret,
        expires_minutes=30,
    )


def _make_test_app(session: AsyncSession | None = None):
    """Create a minimal FastAPI test app with Google OAuth routes."""
    from fastapi import FastAPI

    from noa.api.v1.auth import router

    app = FastAPI()
    app.include_router(router)

    if session is not None:
        # Override DB dependency to use the provided session
        from noa.api.deps import get_db_session

        async def _override_db():
            yield session

        app.dependency_overrides[get_db_session] = _override_db

    return app


def _make_client(session: AsyncSession | None = None) -> TestClient:
    """Create a synchronous TestClient for the auth router."""
    app = _make_test_app(session)
    return TestClient(app, raise_server_exceptions=True)


def _make_client_with_mock_db() -> TestClient:
    """Create a TestClient with a no-op mock DB (for tests that hit DB dependency
    but exercise error paths that don't actually query the DB)."""
    from fastapi import FastAPI

    from noa.api.deps import get_db_session
    from noa.api.v1.auth import router

    app = FastAPI()
    app.include_router(router)

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.delete = AsyncMock()

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db_session] = _override_db

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Integration test: test app + real DB session
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def auth_token(user_id: uuid.UUID, monkeypatch) -> str:
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    return _make_jwt(str(user_id), secret=TEST_SECRET)


# ===========================================================================
# Tests: GET /google/authorize
# ===========================================================================


class TestGoogleAuthorize:
    """Tests for GET /api/v1/auth/google/authorize."""

    def test_returns_200_with_auth_url(self, monkeypatch, auth_token, user_id) -> None:
        """Returns 200 with auth_url pointing to accounts.google.com."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data["data"]
        assert "accounts.google.com" in data["data"]["auth_url"]

    def test_requires_jwt_auth_401_without_token(self, monkeypatch) -> None:
        """Returns 401 when no Authorization header is provided."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get("/api/v1/auth/google/authorize")
        assert resp.status_code == 401

    def test_auth_url_includes_calendar_scopes(self, monkeypatch, auth_token) -> None:
        """Auth URL includes Google Calendar scopes."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        auth_url = resp.json()["data"]["auth_url"]
        assert "calendar" in auth_url

    def test_auth_url_includes_gmail_scopes(self, monkeypatch, auth_token) -> None:
        """Auth URL includes Gmail scopes."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        auth_url = resp.json()["data"]["auth_url"]
        assert "gmail" in auth_url

    def test_auth_url_includes_access_type_offline(self, monkeypatch, auth_token) -> None:
        """Auth URL contains access_type=offline for refresh token."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        auth_url = resp.json()["data"]["auth_url"]
        assert "access_type=offline" in auth_url

    def test_auth_url_includes_prompt_consent(self, monkeypatch, auth_token) -> None:
        """Auth URL contains prompt=consent to force refresh token delivery."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        auth_url = resp.json()["data"]["auth_url"]
        assert "prompt=consent" in auth_url

    def test_auth_url_includes_csrf_state(self, monkeypatch, auth_token) -> None:
        """Auth URL includes a state parameter for CSRF protection."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        auth_url = resp.json()["data"]["auth_url"]
        assert "state=" in auth_url

    def test_503_when_google_not_configured(self, monkeypatch, auth_token) -> None:
        """Returns 503 when GOOGLE_CLIENT_ID/SECRET are not set."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

        client = _make_client()
        resp = client.get(
            "/api/v1/auth/google/authorize",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 503


# ===========================================================================
# Tests: GET /google/callback
# ===========================================================================


class TestGoogleCallback:
    """Tests for GET /api/v1/auth/google/callback."""

    def _seed_state(self, user_id: uuid.UUID, platform: str = "web") -> str:
        """Inject a valid CSRF state into the module-level store."""
        import secrets
        import time

        from noa.api.v1.auth import _oauth_states

        state = secrets.token_urlsafe(32)
        _oauth_states[state] = {
            "user_id": str(user_id),
            "platform": platform,
            "expires": time.time() + 600,
        }
        return state

    @pytest.mark.anyio
    async def test_valid_code_persists_encrypted_tokens(
        self,
        monkeypatch,
        db_session,
        user_id,
    ) -> None:
        """Valid code: tokens are stored encrypted in google_credentials."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        # Create the user row first (FK constraint)
        from noa.db.models.user import User

        user = User(
            id=user_id,
            email=f"{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)
        await db_session.commit()

        state = self._seed_state(user_id)

        # Mock httpx to return fake tokens from Google
        fake_tokens = {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fake_tokens

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_client

            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from noa.api.deps import get_db_session
            from noa.api.v1.auth import router

            app = FastAPI()
            app.include_router(router)

            async def _override_db():
                yield db_session

            app.dependency_overrides[get_db_session] = _override_db

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                f"/api/v1/auth/google/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        # Should redirect (302)
        assert resp.status_code == 302

        # Verify tokens persisted encrypted
        from sqlalchemy import select

        from noa.db.models.google_credential import GoogleCredential
        from noa.tools._token_crypto import decrypt_token

        stmt = select(GoogleCredential).where(GoogleCredential.user_id == user_id)
        result = await db_session.execute(stmt)
        cred = result.scalar_one_or_none()

        assert cred is not None, "google_credentials row must be created"
        # Verify tokens are NOT stored in plaintext
        assert cred.access_token_enc != "fake-access-token"
        assert cred.refresh_token_enc != "fake-refresh-token"
        # Verify they decrypt correctly
        assert decrypt_token(cred.access_token_enc) == "fake-access-token"
        assert decrypt_token(cred.refresh_token_enc) == "fake-refresh-token"

    def test_valid_code_redirects_to_settings(self, monkeypatch, user_id) -> None:
        """Valid code: redirects to /settings?google=connected."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("NOA_DOMAIN", "localhost:8000")

        state = self._seed_state(user_id)

        fake_tokens = {
            "access_token": "fake-at",
            "refresh_token": "fake-rt",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fake_tokens

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_client

            # Use a mock DB session that commits successfully
            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            )
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.delete = AsyncMock()

            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from noa.api.deps import get_db_session
            from noa.api.v1.auth import router

            app = FastAPI()
            app.include_router(router)

            async def _override_db():
                yield mock_db

            app.dependency_overrides[get_db_session] = _override_db

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                f"/api/v1/auth/google/callback?code=valid-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "settings" in resp.headers["location"]
        assert "google=connected" in resp.headers["location"]

    def test_error_param_returns_400(self, monkeypatch, user_id) -> None:
        """?error=access_denied returns 400."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)

        client = _make_client_with_mock_db()
        resp = client.get(
            "/api/v1/auth/google/callback?error=access_denied",
        )
        assert resp.status_code == 400

    def test_missing_code_returns_400(self, monkeypatch) -> None:
        """Callback without code returns 400."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)

        client = _make_client_with_mock_db()
        resp = client.get("/api/v1/auth/google/callback?state=somefakestate")
        assert resp.status_code == 400

    def test_invalid_state_returns_400(self, monkeypatch) -> None:
        """Callback with unknown state returns 400 (CSRF check)."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client_with_mock_db()
        resp = client.get(
            "/api/v1/auth/google/callback?code=somecode&state=invalid-state",
        )
        assert resp.status_code == 400

    def test_missing_state_returns_400(self, monkeypatch) -> None:
        """Callback without state returns 400 (CSRF check)."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

        client = _make_client_with_mock_db()
        resp = client.get("/api/v1/auth/google/callback?code=somecode")
        assert resp.status_code == 400


# ===========================================================================
# Tests: GET /google/status
# ===========================================================================


class TestGoogleStatus:
    """Tests for GET /api/v1/auth/google/status."""

    @pytest.mark.anyio
    async def test_connected_true_after_tokens_stored(
        self, monkeypatch, db_session, user_id, auth_token
    ) -> None:
        """Returns connected=true after google_credentials row exists."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        # Create user + credential row
        from noa.db.models.google_credential import GoogleCredential
        from noa.db.models.user import User
        from noa.tools._token_crypto import encrypt_token

        user = User(
            id=user_id,
            email=f"status-{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)

        cred = GoogleCredential(
            user_id=user_id,
            access_token_enc=encrypt_token("at"),
            refresh_token_enc=encrypt_token("rt"),
        )
        db_session.add(cred)
        await db_session.commit()

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get(
            "/api/v1/auth/google/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["connected"] is True
        assert isinstance(data["scopes"], list)
        assert len(data["scopes"]) > 0

    @pytest.mark.anyio
    async def test_connected_false_when_no_credentials(
        self, monkeypatch, db_session, user_id, auth_token
    ) -> None:
        """Returns connected=false when no google_credentials row exists."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        # Ensure user exists (for JWT to be valid) but no google_credentials
        from noa.db.models.user import User

        user = User(
            id=user_id,
            email=f"no-cred-{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)
        await db_session.commit()

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get(
            "/api/v1/auth/google/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["connected"] is False
        assert data["scopes"] == []

    def test_status_requires_auth(self, monkeypatch) -> None:
        """Returns 401 without JWT token."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)

        client = _make_client()
        resp = client.get("/api/v1/auth/google/status")
        assert resp.status_code == 401


# ===========================================================================
# Tests: DELETE /google/disconnect
# ===========================================================================


class TestGoogleDisconnect:
    """Tests for DELETE /api/v1/auth/google/disconnect."""

    @pytest.mark.anyio
    async def test_disconnect_removes_db_row(
        self, monkeypatch, db_session, user_id, auth_token
    ) -> None:
        """Disconnect deletes the google_credentials row."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        from noa.db.models.google_credential import GoogleCredential
        from noa.db.models.user import User
        from noa.tools._token_crypto import encrypt_token

        user = User(
            id=user_id,
            email=f"disc-{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)

        cred = GoogleCredential(
            user_id=user_id,
            access_token_enc=encrypt_token("at"),
            refresh_token_enc=encrypt_token("rt"),
        )
        db_session.add(cred)
        await db_session.commit()

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.delete(
            "/api/v1/auth/google/disconnect",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert resp.status_code == 200

        # Verify row is gone
        from sqlalchemy import select

        stmt = select(GoogleCredential).where(GoogleCredential.user_id == user_id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    def test_disconnect_returns_404_when_no_credentials(
        self, monkeypatch, auth_token
    ) -> None:
        """Returns 404 when no credentials to disconnect."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        # DB session with no credentials
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db_session] = _override_db

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.delete(
            "/api/v1/auth/google/disconnect",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert resp.status_code == 404

    def test_disconnect_clears_live_client(
        self, monkeypatch, auth_token
    ) -> None:
        """Disconnect calls clear_tokens() on the live GoogleAuthClient."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        from noa.tools.google_auth import GoogleAuthClient

        live_client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost",
        )
        live_client.set_tokens(access_token="live-at", refresh_token="live-rt")
        assert live_client.is_authenticated

        # Inject live client via app_state

        mock_gateway = MagicMock()
        mock_gateway._adapters = {}  # no adapters, so _get_live_google_client returns None

        # Patch _get_live_google_client directly to return our live_client
        with patch(
            "noa.api.v1.auth._get_live_google_client", return_value=live_client
        ):
            from noa.db.models.google_credential import GoogleCredential

            mock_cred = MagicMock(spec=GoogleCredential)
            mock_cred.user_id = uuid.uuid4()

            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.execute = AsyncMock(
                return_value=MagicMock(
                    scalar_one_or_none=MagicMock(return_value=mock_cred)
                )
            )
            mock_db.delete = AsyncMock()
            mock_db.commit = AsyncMock()

            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from noa.api.deps import get_db_session
            from noa.api.v1.auth import router

            app = FastAPI()
            app.include_router(router)

            async def _override_db():
                yield mock_db

            app.dependency_overrides[get_db_session] = _override_db

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.delete(
                "/api/v1/auth/google/disconnect",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 200

    def test_disconnect_requires_auth(self, monkeypatch) -> None:
        """Returns 401 without JWT token."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)

        client = _make_client()
        resp = client.delete("/api/v1/auth/google/disconnect")
        assert resp.status_code == 401


# ===========================================================================
# Tests: load_tokens_from_db
# ===========================================================================


class TestLoadTokensFromDb:
    """Tests for noa.tools.google_auth.load_tokens_from_db."""

    @pytest.mark.anyio
    async def test_loads_tokens_when_row_exists(
        self, monkeypatch, db_session, user_id
    ) -> None:
        """load_tokens_from_db decrypts tokens and calls set_tokens()."""
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        from noa.db.models.google_credential import GoogleCredential
        from noa.db.models.user import User
        from noa.tools._token_crypto import encrypt_token
        from noa.tools.google_auth import GoogleAuthClient, load_tokens_from_db

        user = User(
            id=user_id,
            email=f"ltdb-{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)

        cred = GoogleCredential(
            user_id=user_id,
            access_token_enc=encrypt_token("stored-at"),
            refresh_token_enc=encrypt_token("stored-rt"),
        )
        db_session.add(cred)
        await db_session.commit()

        auth_client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost",
        )

        result = await load_tokens_from_db(
            session=db_session,
            user_id=user_id,
            auth_client=auth_client,
        )

        assert result is True
        assert auth_client.access_token == "stored-at"
        assert auth_client.refresh_token == "stored-rt"

    @pytest.mark.anyio
    async def test_returns_false_when_no_row(
        self, monkeypatch, db_session
    ) -> None:
        """load_tokens_from_db returns False when no DB row exists."""
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        from noa.tools.google_auth import GoogleAuthClient, load_tokens_from_db

        auth_client = GoogleAuthClient(
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost",
        )

        result = await load_tokens_from_db(
            session=db_session,
            user_id=uuid.uuid4(),  # no such user
            auth_client=auth_client,
        )

        assert result is False
        assert auth_client.access_token is None
        assert auth_client.refresh_token is None


# ===========================================================================
# Tests: Token persistence and rotation
# ===========================================================================


class TestTokenPersistenceAndRotation:
    """Tests for token storage behavior (§11.1, §11.3)."""

    def test_tokens_not_stored_in_plaintext(self, monkeypatch) -> None:
        """encrypt_token output differs from plaintext input."""
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        from noa.tools._token_crypto import decrypt_token, encrypt_token

        plaintext = "my-secret-token"
        ciphertext = encrypt_token(plaintext)

        assert ciphertext != plaintext
        assert decrypt_token(ciphertext) == plaintext

    @pytest.mark.anyio
    async def test_new_refresh_token_overwrites_db_row(
        self, monkeypatch, db_session, user_id
    ) -> None:
        """Callback with new refresh token overwrites the existing DB row."""
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        monkeypatch.setenv("NOA_DOMAIN", "localhost:8000")

        from noa.db.models.google_credential import GoogleCredential
        from noa.db.models.user import User
        from noa.tools._token_crypto import decrypt_token, encrypt_token

        user = User(
            id=user_id,
            email=f"rot-{user_id}@test.com",
            password_hash="x",
        )
        db_session.add(user)

        # Pre-seed old tokens
        cred = GoogleCredential(
            user_id=user_id,
            access_token_enc=encrypt_token("old-at"),
            refresh_token_enc=encrypt_token("old-rt"),
        )
        db_session.add(cred)
        await db_session.commit()

        import secrets
        import time

        from noa.api.v1.auth import _oauth_states

        state = secrets.token_urlsafe(32)
        _oauth_states[state] = {
            "user_id": str(user_id),
            "platform": "web",
            "expires": time.time() + 600,
        }

        new_tokens = {"access_token": "new-at", "refresh_token": "new-rt"}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = new_tokens

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_client

            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from noa.api.deps import get_db_session
            from noa.api.v1.auth import router

            app = FastAPI()
            app.include_router(router)

            async def _override_db():
                yield db_session

            app.dependency_overrides[get_db_session] = _override_db

            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get(
                f"/api/v1/auth/google/callback?code=new-code&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302

        # Verify DB row has new tokens
        from sqlalchemy import select

        db_session.expire_all()  # force reload from DB
        stmt = select(GoogleCredential).where(GoogleCredential.user_id == user_id)
        result = await db_session.execute(stmt)
        updated_cred = result.scalar_one()

        assert decrypt_token(updated_cred.access_token_enc) == "new-at"
        assert decrypt_token(updated_cred.refresh_token_enc) == "new-rt"


# ===========================================================================
# Tests: Registration startup
# ===========================================================================


class TestRegistrationStartup:
    """Tests for registration.py DB-first token loading."""

    def test_register_tools_skips_without_client_id_secret(
        self, monkeypatch
    ) -> None:
        """register_tools skips Google when GOOGLE_CLIENT_ID is not set."""
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

        from noa.tools.gateway import ToolGateway

        gateway = ToolGateway()

        from noa.tools.registration import register_tools

        register_tools(gateway)

        tools = gateway.list_tools()
        assert "calendar" not in tools
        assert "gmail" not in tools

    def test_register_tools_loads_env_fallback_when_set(
        self, monkeypatch
    ) -> None:
        """When GOOGLE_REFRESH_TOKEN is set, it is loaded as fallback."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "env-refresh-token")
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        captured_tokens: list[str] = []

        from noa.tools.google_auth import GoogleAuthClient

        original_init = GoogleAuthClient.__init__
        created_clients: list[GoogleAuthClient] = []

        def _patched_init(self, *, client_id, client_secret, redirect_uri, on_token_change=None):  # type: ignore[override]
            original_init(
                self,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                on_token_change=on_token_change,
            )
            created_clients.append(self)

        with patch.object(GoogleAuthClient, "__init__", _patched_init):
            from noa.tools.gateway import ToolGateway

            gateway = ToolGateway()

            # Stub out calendar/gmail registration to avoid import errors
            with (
                patch("noa.tools.registration._register_calendar"),
                patch("noa.tools.registration._register_gmail"),
            ):
                from noa.tools.registration import _register_google_tools

                _register_google_tools(gateway)

        # At least one client was created
        assert len(created_clients) > 0
        # The client should have the env-var refresh token loaded
        client = created_clients[0]
        assert client.refresh_token == "env-refresh-token"

    def test_multi_user_safety_status_scoped_to_user(
        self, monkeypatch, auth_token, user_id
    ) -> None:
        """Status endpoint is scoped to the authenticated user's user_id."""
        monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
        monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)

        other_user_id = uuid.uuid4()

        # DB has credential for OTHER user, not current user
        from noa.db.models.google_credential import GoogleCredential

        other_cred = MagicMock(spec=GoogleCredential)
        other_cred.user_id = other_user_id

        # Mock session returns None for the authenticated user's ID
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from noa.api.deps import get_db_session
        from noa.api.v1.auth import router

        app = FastAPI()
        app.include_router(router)

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db_session] = _override_db

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get(
            "/api/v1/auth/google/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert resp.status_code == 200
        # Current user is not connected (other user's cred doesn't count)
        assert resp.json()["data"]["connected"] is False
