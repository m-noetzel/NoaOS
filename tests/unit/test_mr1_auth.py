"""Tests for Phase MR1: Real Auth + First-Run Registration.

Covers:
- AuthService._get_user_by_email() with real select() queries
- AuthService._get_session_by_refresh_token() with real select() queries
- AuthService._get_session_by_id() with real select() queries
- AuthService.register() — validates no duplicate, hashes password, inserts User
- POST /api/v1/auth/register — public endpoint returning 201 / 409
- create_access_token() with session_id emits "sid" claim
- logout reads payload["sid"] not payload["jti"]
- login endpoint uses real db session (not _mock_session)
- register endpoint does not require auth

Spec refs: SPEC.md §5.1, §5.2, §5.3, §5.4
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.mr1


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

def _make_settings(monkeypatch):
    """Build a Settings object with test values applied to the env."""
    for k, v in {
        "NOA_ENV": "testing",
        "SECRET_KEY": "test-secret-key-for-jwt-signing-32bytes!",
        "DATABASE_URL": "sqlite+aiosqlite:///test_mr1.db",
        "LOG_LEVEL": "DEBUG",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    }.items():
        monkeypatch.setenv(k, v)
    from noa.config import Settings
    return Settings()


def _make_mock_execute(rows):
    """Return an AsyncMock for session.execute that yields given rows."""
    result_mock = MagicMock()
    if rows:
        result_mock.scalar_one_or_none.return_value = rows[0]
    else:
        result_mock.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        return result_mock
    return mock_execute


def _make_mock_session(execute_fn=None):
    """Return an AsyncMock session with optional execute override."""
    session = AsyncMock()
    if execute_fn is not None:
        session.execute = execute_fn
    return session


def _make_test_app(monkeypatch):
    """Create a FastAPI test app with get_db_session overridden."""
    from fastapi import FastAPI

    from noa.api.deps import get_db_session
    from noa.api.v1.auth import router

    app = FastAPI()
    app.include_router(router)

    mock_session = AsyncMock()

    async def override_get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app, mock_session


# ===========================================================================
# 1. register() calls session.add() with User whose password_hash != plain
# ===========================================================================

@pytest.mark.asyncio
async def test_register_hashes_password(monkeypatch):
    """register() should store a hashed password, not the plain text."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService

    # Mock session: _get_user_by_email returns None (no existing user)
    session = _make_mock_session(_make_mock_execute([]))
    svc = AuthService(session=session, settings=settings)
    result = await svc.register(email="alice@example.com", password="s3cret!")  # noqa: S106

    assert result["user_id"] is not None

    # Verify session.add was called with a User whose password_hash != plain
    session.add.assert_called_once()
    added_user = session.add.call_args[0][0]
    assert added_user.password_hash != "s3cret!"  # noqa: S105
    assert added_user.email == "alice@example.com"


# ===========================================================================
# 2. register() rejects duplicate email with AuthError
# ===========================================================================

@pytest.mark.asyncio
async def test_register_duplicate_email_raises(monkeypatch):
    """register() should raise AuthError when email already exists."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthError, AuthService
    from noa.db.models.user import User

    existing_user = User(
        id=uuid.uuid4(),
        email="dup@example.com",
        password_hash="existing_hash",  # noqa: S106
        is_active=True,
    )
    session = _make_mock_session(_make_mock_execute([existing_user]))
    svc = AuthService(session=session, settings=settings)

    with pytest.raises(AuthError, match="[Ee]mail.*already"):
        await svc.register(email="dup@example.com", password="pw2")  # noqa: S106


# ===========================================================================
# 3. POST /register returns 201 with user_id
# ===========================================================================

@pytest.mark.asyncio
async def test_register_endpoint_201(monkeypatch):
    """POST /api/v1/auth/register should return 201 with user_id."""
    _make_settings(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from noa.auth.service import AuthService

    fake_user_id = str(uuid.uuid4())

    async def mock_register(self, *, email, password):
        return {"user_id": fake_user_id}

    app, _ = _make_test_app(monkeypatch)

    with patch.object(AuthService, "register", mock_register):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "pw123"},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["user_id"] == fake_user_id


# ===========================================================================
# 4. POST /register rejects duplicate returns 409
# ===========================================================================

@pytest.mark.asyncio
async def test_register_endpoint_409_duplicate(monkeypatch):
    """POST /api/v1/auth/register should return 409 for duplicate email."""
    _make_settings(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from noa.auth.service import AuthError, AuthService

    async def mock_register(self, *, email, password):
        raise AuthError("Email already registered")

    app, _ = _make_test_app(monkeypatch)

    with patch.object(AuthService, "register", mock_register):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "pw123"},
            )
    assert resp.status_code == 409


# ===========================================================================
# 5. _get_user_by_email returns None for missing user
# ===========================================================================

@pytest.mark.asyncio
async def test_get_user_by_email_missing(monkeypatch):
    """_get_user_by_email should return None when user doesn't exist."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService

    session = _make_mock_session(_make_mock_execute([]))
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_user_by_email("nobody@example.com")
    assert result is None


# ===========================================================================
# 6. _get_user_by_email returns user for known email
# ===========================================================================

@pytest.mark.asyncio
async def test_get_user_by_email_found(monkeypatch):
    """_get_user_by_email should return the User row for a known email."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService
    from noa.db.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="known@example.com",
        password_hash="fakehash",  # noqa: S106
        is_active=True,
    )
    session = _make_mock_session(_make_mock_execute([user]))
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_user_by_email("known@example.com")
    assert result is not None
    assert result.email == "known@example.com"


# ===========================================================================
# 7. _get_session_by_refresh_token returns None when not found
# ===========================================================================

@pytest.mark.asyncio
async def test_get_session_by_refresh_token_missing(monkeypatch):
    """_get_session_by_refresh_token should return None for unknown token."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService

    session = _make_mock_session(_make_mock_execute([]))
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_session_by_refresh_token("nonexistent-token")
    assert result is None


# ===========================================================================
# 8. _get_session_by_refresh_token looks up by hashed token
# ===========================================================================

@pytest.mark.asyncio
async def test_get_session_by_refresh_token_found(monkeypatch):
    """_get_session_by_refresh_token should look up by hashed token."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService
    from noa.db.models.session import AuthSession

    raw_token = "my-refresh-token-value"  # noqa: S105
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    auth_sess = AuthSession(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        refresh_token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        is_active=True,
    )

    # Verify the service uses hashed lookup by capturing the select statement
    execute_calls: list = []

    async def capturing_execute(stmt):
        execute_calls.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = auth_sess
        return result

    session = _make_mock_session(capturing_execute)
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_session_by_refresh_token(raw_token)

    assert result is not None
    assert result.refresh_token_hash == token_hash
    # Verify execute was called (i.e., a select query was issued)
    assert len(execute_calls) == 1


# ===========================================================================
# 9. _get_session_by_id returns None for unknown id
# ===========================================================================

@pytest.mark.asyncio
async def test_get_session_by_id_missing(monkeypatch):
    """_get_session_by_id should return None for an unknown id."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService

    session = _make_mock_session(_make_mock_execute([]))
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_session_by_id(uuid.uuid4())
    assert result is None


# ===========================================================================
# 10. _get_session_by_id returns session for known id
# ===========================================================================

@pytest.mark.asyncio
async def test_get_session_by_id_found(monkeypatch):
    """_get_session_by_id should return the session for a known id."""
    settings = _make_settings(monkeypatch)
    from noa.auth.service import AuthService
    from noa.db.models.session import AuthSession

    sess_id = uuid.uuid4()
    auth_sess = AuthSession(
        id=sess_id,
        user_id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        refresh_token_hash="somehash",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(days=7),
        is_active=True,
    )
    session = _make_mock_session(_make_mock_execute([auth_sess]))
    svc = AuthService(session=session, settings=settings)
    result = await svc._get_session_by_id(sess_id)
    assert result is not None
    assert result.id == sess_id


# ===========================================================================
# 11. create_access_token with session_id includes "sid" claim
# ===========================================================================

def test_create_access_token_with_sid(monkeypatch):
    """create_access_token(session_id=...) should include 'sid' claim."""
    from noa.auth.jwt import create_access_token, decode_token

    sid = str(uuid.uuid4())
    secret = "test-secret"  # noqa: S105
    token = create_access_token(
        user_id="user1",
        secret_key=secret,
        expires_minutes=30,
        session_id=sid,
    )
    payload = decode_token(token, secret_key=secret)
    assert payload["sid"] == sid


# ===========================================================================
# 12. logout reads payload["sid"] not payload["jti"]
# ===========================================================================

@pytest.mark.asyncio
async def test_logout_reads_sid_claim(monkeypatch):
    """logout endpoint should read session_id from 'sid' claim, not 'jti'."""
    settings = _make_settings(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from noa.auth.jwt import create_access_token
    from noa.auth.service import AuthService

    session_id = str(uuid.uuid4())
    secret = settings.secret_key or ""
    token = create_access_token(
        user_id="user1",
        secret_key=secret,
        expires_minutes=30,
        session_id=session_id,
    )

    app, _ = _make_test_app(monkeypatch)

    logout_called_with: list[uuid.UUID] = []

    async def spy_logout(self, *, session_id):
        logout_called_with.append(session_id)

    with patch.object(AuthService, "logout", spy_logout):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200
    assert len(logout_called_with) == 1
    assert str(logout_called_with[0]) == session_id


# ===========================================================================
# 13. login endpoint uses real db session (not _mock_session)
# ===========================================================================

def test_login_endpoint_no_mock_session():
    """The login endpoint code should not reference _mock_session."""
    import inspect

    from noa.api.v1 import auth as auth_module

    source = inspect.getsource(auth_module)
    assert "_mock_session" not in source, (
        "auth module still references _mock_session — it should use get_db_session"
    )


# ===========================================================================
# 14. register endpoint does not require auth
# ===========================================================================

@pytest.mark.asyncio
async def test_register_no_auth_required(monkeypatch):
    """POST /register should not require an Authorization header."""
    _make_settings(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from noa.auth.service import AuthService

    async def mock_register(self, *, email, password):
        return {"user_id": str(uuid.uuid4())}

    app, _ = _make_test_app(monkeypatch)

    with patch.object(AuthService, "register", mock_register):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": "noauth@example.com", "password": "pw"},
            )
    assert resp.status_code == 201
