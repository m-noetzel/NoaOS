"""Tests for SEC1: JWT Token Revocation.

Verifies that:
- logout() inserts the access token's jti into the blacklist
- require_auth() rejects tokens whose jti is in the blacklist
- cleanup_expired_blacklist() removes only expired entries
- Non-revoked tokens still pass require_auth()
- revoke_all_user_tokens() deactivates all sessions for a user

Integration scenario: login → logout → use old access token → 401 "Token has been revoked"
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.sec1


# ---------------------------------------------------------------------------
# DB fixtures (real SQLite in-memory, not mocked)
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    """In-memory SQLite engine with all models registered."""
    from noa.db.models import Base  # noqa: F401 — registers all models
    from noa.db.models.token_blacklist import TokenBlacklist  # noqa: F401

    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(monkeypatch) -> Any:
    for k, v in {
        "SECRET_KEY": "test-secret-key-for-jwt-sec1-32bytes!",
        "DATABASE_URL": "sqlite+aiosqlite:///test_sec1.db",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    }.items():
        monkeypatch.setenv(k, v)
    from noa.config import Settings

    return Settings()


async def _seed_user(session: AsyncSession) -> Any:
    """Insert a test user and commit. Returns the User row."""
    from noa.auth.password import hash_password
    from noa.db.models.user import User

    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Password123!"),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _seed_session(session: AsyncSession, user_id: uuid.UUID) -> Any:
    """Insert an active AuthSession for user_id. Returns the AuthSession."""
    from noa.db.models.session import AuthSession

    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user_id,
        device_id=uuid.uuid4(),
        refresh_token_hash="fakehash",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        is_active=True,
    )
    session.add(auth_session)
    await session.commit()
    return auth_session


# ---------------------------------------------------------------------------
# Test: TokenBlacklist model
# ---------------------------------------------------------------------------


class TestTokenBlacklistModel:
    """Verify the ORM model persists and retrieves correctly."""

    async def test_blacklist_entry_persists(self, db_session):
        """Inserting a TokenBlacklist entry and querying it back works."""
        from noa.db.models.token_blacklist import TokenBlacklist

        jti = str(uuid.uuid4())
        user_id = uuid.uuid4()
        entry = TokenBlacklist(
            id=uuid.uuid4(),
            jti=jti,
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
            reason="logout",
        )
        db_session.add(entry)
        await db_session.commit()

        result = await db_session.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.jti == jti
        assert row.reason == "logout"

    async def test_duplicate_jti_raises(self, db_session):
        """Inserting the same jti twice should raise IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        from noa.db.models.token_blacklist import TokenBlacklist

        jti = str(uuid.uuid4())
        user_id = uuid.uuid4()
        for _ in range(2):
            entry = TokenBlacklist(
                id=uuid.uuid4(),
                jti=jti,
                user_id=user_id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                revoked_at=datetime.now(UTC),
            )
            db_session.add(entry)

        with pytest.raises(IntegrityError):
            await db_session.commit()


# ---------------------------------------------------------------------------
# Test: AuthService.revoke_token
# ---------------------------------------------------------------------------


class TestRevokeToken:
    """Unit tests for AuthService.revoke_token()."""

    async def test_revoke_token_inserts_blacklist_row(
        self, db_session, session_factory, monkeypatch
    ):
        """revoke_token() inserts a row into token_blacklist."""
        from noa.auth.service import AuthService
        from noa.db.models.token_blacklist import TokenBlacklist

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)

        jti = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.revoke_token(
                jti=jti,
                user_id=user.id,
                expires_at=expires_at,
                reason="logout",
            )
            await session.commit()

        result = await db_session.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.user_id == user.id
        assert row.reason == "logout"

    async def test_revoke_token_idempotent(
        self, db_session, session_factory, monkeypatch
    ):
        """Revoking the same jti twice should not raise."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)

        jti = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        for _ in range(2):
            async with session_factory() as session:
                svc = AuthService(session=session, settings=settings)
                # Should not raise on second call (idempotent)
                await svc.revoke_token(
                    jti=jti,
                    user_id=user.id,
                    expires_at=expires_at,
                    reason="logout",
                )
                await session.commit()


# ---------------------------------------------------------------------------
# Test: AuthService.is_token_revoked
# ---------------------------------------------------------------------------


class TestIsTokenRevoked:
    """Unit tests for AuthService.is_token_revoked()."""

    async def test_revoked_jti_returns_true(
        self, db_session, session_factory, monkeypatch
    ):
        """is_token_revoked() returns True after revoke_token()."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)

        jti = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.revoke_token(
                jti=jti, user_id=user.id, expires_at=expires_at, reason="logout"
            )
            await session.commit()
            revoked = await svc.is_token_revoked(jti)
        assert revoked is True

    async def test_unknown_jti_returns_false(
        self, db_session, session_factory, monkeypatch
    ):
        """is_token_revoked() returns False for a jti not in the blacklist."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            revoked = await svc.is_token_revoked(str(uuid.uuid4()))
        assert revoked is False


# ---------------------------------------------------------------------------
# Test: AuthService.logout with token revocation
# ---------------------------------------------------------------------------


class TestLogoutRevokesToken:
    """Verify that revoke_token() + logout() together blacklist the access token.

    The endpoint (not service.logout) handles token extraction and revocation.
    These tests verify the lower-level service methods that the endpoint calls.
    """

    async def test_revoke_token_and_logout_together(
        self, db_session, session_factory, monkeypatch
    ):
        """Calling revoke_token() + logout() simulates the full endpoint flow.

        After revoke_token(), the jti appears in the blacklist.
        After logout(), the session is deactivated.
        """
        from noa.auth.jwt import create_access_token, decode_token
        from noa.auth.service import AuthService
        from noa.db.models.token_blacklist import TokenBlacklist

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)
        auth_session = await _seed_session(db_session, user.id)

        # Create a real access token (simulates what the endpoint holds)
        token = create_access_token(
            user_id=str(user.id),
            secret_key=settings.secret_key,
            expires_minutes=30,
            session_id=str(auth_session.id),
        )
        payload = decode_token(token, secret_key=settings.secret_key)
        jti = payload["jti"]
        exp = payload["exp"]
        expires_at = datetime.fromtimestamp(exp, tz=UTC)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            # Endpoint calls these two operations
            await svc.logout(session_id=auth_session.id)
            await svc.revoke_token(
                jti=jti,
                user_id=user.id,
                expires_at=expires_at,
                reason="logout",
            )
            await session.commit()

        # Verify blacklist entry exists
        result = await db_session.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.reason == "logout"

        # Verify session is deactivated
        await db_session.refresh(auth_session)
        assert auth_session.is_active is False

    async def test_logout_deactivates_session(
        self, db_session, session_factory, monkeypatch
    ):
        """logout() deactivates the session row."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)
        auth_session = await _seed_session(db_session, user.id)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.logout(session_id=auth_session.id)

        # Verify session is deactivated
        await db_session.refresh(auth_session)
        assert auth_session.is_active is False


# ---------------------------------------------------------------------------
# Test: cleanup_expired_blacklist
# ---------------------------------------------------------------------------


class TestCleanupExpiredBlacklist:
    """Verify cleanup removes only expired rows."""

    async def test_cleanup_removes_expired_entries(
        self, db_session, session_factory, monkeypatch
    ):
        """Rows with expires_at in the past are deleted; future rows remain."""
        from noa.auth.service import AuthService
        from noa.db.models.token_blacklist import TokenBlacklist

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)

        expired_jti = str(uuid.uuid4())
        active_jti = str(uuid.uuid4())

        # Insert an expired entry
        expired = TokenBlacklist(
            id=uuid.uuid4(),
            jti=expired_jti,
            user_id=user.id,
            expires_at=datetime.now(UTC) - timedelta(hours=2),  # past
            revoked_at=datetime.now(UTC) - timedelta(hours=3),
            reason="logout",
        )
        # Insert an active (non-expired) entry
        active = TokenBlacklist(
            id=uuid.uuid4(),
            jti=active_jti,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),  # future
            revoked_at=datetime.now(UTC),
            reason="logout",
        )
        db_session.add_all([expired, active])
        await db_session.commit()

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            deleted = await svc.cleanup_expired_blacklist()

        assert deleted == 1

        # Expired row gone, active row remains
        result_expired = await db_session.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == expired_jti)
        )
        assert result_expired.scalar_one_or_none() is None

        result_active = await db_session.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == active_jti)
        )
        assert result_active.scalar_one_or_none() is not None

    async def test_cleanup_with_no_expired_returns_zero(
        self, db_session, session_factory, monkeypatch
    ):
        """cleanup_expired_blacklist() returns 0 when nothing to clean."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            deleted = await svc.cleanup_expired_blacklist()

        assert deleted == 0


# ---------------------------------------------------------------------------
# Test: revoke_all_user_tokens
# ---------------------------------------------------------------------------


class TestRevokeAllUserTokens:
    """Verify revoke_all_user_tokens deactivates all sessions for a user."""

    async def test_revoke_all_deactivates_sessions(
        self, db_session, session_factory, monkeypatch
    ):
        """All active sessions for user_id become inactive."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)
        user = await _seed_user(db_session)

        # Create 3 active sessions
        sessions = []
        for _ in range(3):
            s = await _seed_session(db_session, user.id)
            sessions.append(s)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.revoke_all_user_tokens(
                user_id=user.id, reason="password_change"
            )

        # All sessions should be inactive
        for s in sessions:
            await db_session.refresh(s)
            assert s.is_active is False

    async def test_revoke_all_does_not_affect_other_users(
        self, db_session, session_factory, monkeypatch
    ):
        """revoke_all_user_tokens() does not touch sessions belonging to other users."""
        from noa.auth.service import AuthService

        settings = _make_settings(monkeypatch)
        user_a = await _seed_user(db_session)
        user_b = await _seed_user(db_session)

        session_a = await _seed_session(db_session, user_a.id)
        session_b = await _seed_session(db_session, user_b.id)

        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.revoke_all_user_tokens(user_id=user_a.id, reason="test")

        await db_session.refresh(session_a)
        await db_session.refresh(session_b)
        assert session_a.is_active is False
        assert session_b.is_active is True  # unaffected


# ---------------------------------------------------------------------------
# Test: require_auth rejects revoked tokens (integration)
# ---------------------------------------------------------------------------


class TestRequireAuthRejectsRevokedToken:
    """Integration test: middleware rejects a token after it is blacklisted."""

    async def test_revoked_token_raises_401(self, session_factory, monkeypatch):
        """Tokens in the blacklist are rejected by require_auth with 401."""
        from noa.auth.jwt import create_access_token, decode_token
        from noa.auth.middleware import _check_blacklist
        from noa.auth.service import AuthService

        monkeypatch.setenv(
            "SECRET_KEY", "test-secret-key-for-jwt-sec1-32bytes!"
        )
        from noa.config import Settings

        settings = Settings()

        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_minutes=30,
        )
        payload = decode_token(token, secret_key=settings.secret_key)
        jti = payload["jti"]
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        # Blacklist the token
        async with session_factory() as session:
            svc = AuthService(session=session, settings=settings)
            await svc.revoke_token(
                jti=jti, user_id=user_id, expires_at=expires_at, reason="logout"
            )
            await session.commit()

        # _check_blacklist should return True
        async with session_factory() as session:
            revoked = await _check_blacklist(session, jti)
        assert revoked is True

    async def test_non_revoked_token_passes_blacklist_check(
        self, session_factory, monkeypatch
    ):
        """Tokens not in the blacklist pass the _check_blacklist check."""
        from noa.auth.middleware import _check_blacklist

        async with session_factory() as session:
            not_revoked = await _check_blacklist(session, str(uuid.uuid4()))
        assert not_revoked is False

    async def test_full_flow_require_auth_rejects_after_logout(
        self, session_factory, monkeypatch
    ):
        """Full integration: after logout, require_auth() raises 401 for old token.

        Flow: issue token → add to blacklist → simulate require_auth with mocked
        factory → 401 "Token has been revoked"
        """
        from noa.auth.jwt import create_access_token

        monkeypatch.setenv(
            "SECRET_KEY", "test-secret-key-for-jwt-sec1-32bytes!"
        )
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test_sec1.db")
        from noa.config import Settings

        settings = Settings()

        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_minutes=30,
        )

        from noa.auth.jwt import decode_token

        payload_data = decode_token(token, secret_key=settings.secret_key)
        jti = payload_data["jti"]
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        # Blacklist via service
        async with session_factory() as session:
            from noa.auth.service import AuthService

            svc = AuthService(session=session, settings=settings)
            await svc.revoke_token(
                jti=jti, user_id=user_id, expires_at=expires_at, reason="logout"
            )
            await session.commit()

        # Patch _get_optional_db_session to return our real factory
        with patch(
            "noa.auth.middleware._get_optional_db_session",
            return_value=session_factory,
        ):
            from fastapi import Request
            from fastapi.security import HTTPAuthorizationCredentials

            from noa.auth.middleware import require_auth

            mock_request = MagicMock(spec=Request)
            mock_request.cookies = {}
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=token
            )

            with pytest.raises(HTTPException) as exc_info:
                await require_auth(
                    request=mock_request,
                    credentials=credentials,
                    settings=settings,
                )

            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()

    async def test_non_revoked_token_passes_require_auth(
        self, session_factory, monkeypatch
    ):
        """A valid, non-revoked token is accepted by require_auth()."""
        from noa.auth.jwt import create_access_token

        monkeypatch.setenv(
            "SECRET_KEY", "test-secret-key-for-jwt-sec1-32bytes!"
        )
        from noa.config import Settings

        settings = Settings()

        user_id = uuid.uuid4()
        token = create_access_token(
            user_id=str(user_id),
            secret_key=settings.secret_key,
            expires_minutes=30,
        )

        # Do NOT revoke — token should pass
        with patch(
            "noa.auth.middleware._get_optional_db_session",
            return_value=session_factory,
        ):
            from fastapi import Request
            from fastapi.security import HTTPAuthorizationCredentials

            from noa.auth.middleware import require_auth

            mock_request = MagicMock(spec=Request)
            mock_request.cookies = {}
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=token
            )

            auth_user = await require_auth(
                request=mock_request,
                credentials=credentials,
                settings=settings,
            )

        assert auth_user.user_id == user_id
