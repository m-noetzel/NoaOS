"""Authentication service — business logic for login, refresh, logout.

SPEC.md SS5.2-5.4: Session tokens, device binding, token rotation, revocation.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from noa.auth.jwt import create_access_token, create_refresh_token, decode_token
from noa.auth.password import hash_password, verify_password
from noa.config import Settings
from noa.db.models.session import AuthSession
from noa.db.models.user import User


class AuthError(Exception):
    """Raised for authentication failures."""


class AuthService:
    """Handles login, refresh, and logout operations.

    Requires an async SQLAlchemy session and application settings.
    """

    def __init__(self, session: Any, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def login(
        self,
        *,
        email: str,
        password: str,
        device_id: uuid.UUID,
    ) -> dict[str, str]:
        """Authenticate user, create session, return token pair.

        Raises AuthError on invalid credentials.
        """
        user = await self._get_user_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            msg = "Invalid email or password"
            raise AuthError(msg)

        if not user.is_active:
            msg = "Account is disabled"
            raise AuthError(msg)

        # Create session ID upfront so we can embed it in the access token
        session_id = uuid.uuid4()

        # Create tokens
        secret = self._settings.secret_key
        if not secret:
            raise RuntimeError("SECRET_KEY is not set — refusing to issue tokens")
        access_token = create_access_token(
            user_id=str(user.id),
            secret_key=secret,
            expires_minutes=self._settings.access_token_expire_minutes,
            session_id=str(session_id),
        )
        refresh_token = create_refresh_token(
            user_id=str(user.id),
            secret_key=secret,
            expires_days=self._settings.refresh_token_expire_days,
        )

        # Persist session
        auth_session = AuthSession(
            id=session_id,
            user_id=user.id,
            device_id=device_id,
            refresh_token_hash=self._hash_token(refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(days=self._settings.refresh_token_expire_days),
            is_active=True,
        )
        self._session.add(auth_session)
        await self._session.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh(
        self,
        *,
        refresh_token: str,
        device_id: uuid.UUID,
    ) -> dict[str, str]:
        """Rotate refresh token, return new token pair.

        SPEC.md SS5.2 — old refresh token invalidated on use.
        """
        secret = self._settings.secret_key
        if not secret:
            raise RuntimeError("SECRET_KEY is not set — refusing to validate tokens")
        payload = decode_token(refresh_token, secret_key=secret)
        user_id = payload["sub"]

        auth_session = await self._get_session_by_refresh_token(refresh_token)
        if auth_session is None or not auth_session.is_active:
            msg = "Invalid or expired session"
            raise AuthError(msg)

        # Generate new tokens
        new_access = create_access_token(
            user_id=user_id,
            secret_key=secret,
            expires_minutes=self._settings.access_token_expire_minutes,
        )
        new_refresh = create_refresh_token(
            user_id=user_id,
            secret_key=secret,
            expires_days=self._settings.refresh_token_expire_days,
        )

        # Update session with new refresh token hash
        auth_session.refresh_token_hash = self._hash_token(new_refresh)
        auth_session.last_activity_at = datetime.now(UTC)
        auth_session.expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        await self._session.commit()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
        }

    async def logout(self, *, session_id: uuid.UUID) -> None:
        """Invalidate a session — SPEC.md SS5.4."""
        auth_session = await self._get_session_by_id(session_id)
        if auth_session is not None:
            auth_session.is_active = False
            await self._session.commit()

    async def request_password_reset(
        self,
        *,
        email: str,
    ) -> dict[str, str]:
        """Generate a short-lived password reset token.

        For self-hosted systems the token is returned directly
        and also logged to stdout so the admin can retrieve it.
        """
        import logging

        logger = logging.getLogger(__name__)

        user = await self._get_user_by_email(email)
        if user is None:
            # Don't reveal whether email exists
            return {"status": "ok"}

        secret = self._settings.secret_key
        if not secret:
            raise RuntimeError("SECRET_KEY not set")

        # Create a signed reset token (15 min expiry)
        token = create_access_token(
            user_id=str(user.id),
            secret_key=secret,
            expires_minutes=15,
            token_type="reset",  # noqa: S106
        )

        logger.info(
            "Password reset requested for %s — token: %s",
            email,
            token[:20] + "...",
        )

        return {"status": "ok", "reset_token": token}

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> dict[str, str]:
        """Reset password using a valid reset token."""
        secret = self._settings.secret_key
        if not secret:
            raise RuntimeError("SECRET_KEY not set")

        try:
            payload = decode_token(token, secret_key=secret)
        except Exception as exc:
            msg = "Invalid or expired reset token"
            raise AuthError(msg) from exc

        if payload.get("type") != "reset":
            msg = "Invalid token type"
            raise AuthError(msg)

        user_id = payload["sub"]
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            msg = "User not found"
            raise AuthError(msg)

        user.password_hash = hash_password(new_password)
        await self._session.commit()

        return {"status": "password_reset"}

    async def register(
        self,
        *,
        email: str,
        password: str,
    ) -> dict[str, str]:
        """Register a new user.

        Validates no duplicate email, hashes the password, and inserts
        a User row. Returns {"user_id": "<uuid>"}.
        Raises AuthError if the email is already registered.
        """
        existing = await self._get_user_by_email(email)
        if existing is not None:
            msg = "Email already registered"
            raise AuthError(msg)

        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )
        self._session.add(user)
        await self._session.commit()
        return {"user_id": str(user.id)}

    # ------------------------------------------------------------------
    # Internal helpers — real DB queries
    # ------------------------------------------------------------------

    async def _get_user_by_email(self, email: str) -> Any:
        """Look up a user by email. Returns None if not found."""
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_session_by_refresh_token(self, token: str) -> Any:
        """Look up an auth session by refresh token hash."""
        stmt = select(AuthSession).where(
            AuthSession.refresh_token_hash == self._hash_token(token)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_session_by_id(self, session_id: uuid.UUID) -> Any:
        """Look up an auth session by its primary key."""
        stmt = select(AuthSession).where(AuthSession.id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> str:
        """SHA-256 hash of a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

