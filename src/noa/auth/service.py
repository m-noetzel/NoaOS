"""Authentication service — business logic for login, refresh, logout.

SPEC.md SS5.2-5.4: Session tokens, device binding, token rotation, revocation.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from noa.auth.jwt import create_access_token, create_refresh_token, decode_token
from noa.auth.password import verify_password
from noa.config import Settings
from noa.db.models.session import AuthSession


class AuthError(Exception):
    """Raised for authentication failures."""


class AccountLockedError(AuthError):
    """Raised when an account is locked due to too many failed attempts."""


class AuthService:
    """Handles login, refresh, and logout operations.

    Requires an async SQLAlchemy session and application settings.
    """

    # Rate limiting: track failed attempts per email (in-memory for now)
    _failed_attempts: dict[str, list[datetime]] = {}  # noqa: RUF012
    _MAX_ATTEMPTS = 5
    _LOCKOUT_WINDOW_MINUTES = 10
    _LOCKOUT_DURATION_MINUTES = 30

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
        Raises AccountLockedError after 5 failed attempts within 10 minutes.
        """
        # Check rate limiting BEFORE credential verification
        self._check_rate_limit(email)

        user = await self._get_user_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            self._record_failed_attempt(email)
            msg = "Invalid email or password"
            raise AuthError(msg)

        if not user.is_active:
            msg = "Account is disabled"
            raise AuthError(msg)

        # Clear failed attempts on successful login
        self._failed_attempts.pop(email, None)

        # Create tokens
        secret = self._settings.secret_key or ""
        access_token = create_access_token(
            user_id=str(user.id),
            secret_key=secret,
            expires_minutes=self._settings.access_token_expire_minutes,
        )
        refresh_token = create_refresh_token(
            user_id=str(user.id),
            secret_key=secret,
            expires_days=self._settings.refresh_token_expire_days,
        )

        # Persist session
        auth_session = AuthSession(
            id=uuid.uuid4(),
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
        secret = self._settings.secret_key or ""
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

    # ------------------------------------------------------------------
    # Internal helpers (patched in tests)
    # ------------------------------------------------------------------

    async def _get_user_by_email(self, email: str) -> Any:
        """Look up a user by email. Returns None if not found."""
        return None  # pragma: no cover — overridden in tests / real impl

    async def _get_session_by_refresh_token(self, token: str) -> Any:
        """Look up an auth session by refresh token hash."""
        return None  # pragma: no cover

    async def _get_session_by_id(self, session_id: uuid.UUID) -> Any:
        """Look up an auth session by its primary key."""
        return None  # pragma: no cover

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> str:
        """SHA-256 hash of a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _check_rate_limit(self, email: str) -> None:
        """Raise AccountLockedError if too many recent failed attempts."""
        attempts = self._failed_attempts.get(email, [])
        cutoff = datetime.now(UTC) - timedelta(
            minutes=self._LOCKOUT_WINDOW_MINUTES
        )
        recent = [a for a in attempts if a >= cutoff]
        if len(recent) >= self._MAX_ATTEMPTS:
            msg = (
                "Account locked due to too many failed login attempts."
                " Try again later."
            )
            raise AccountLockedError(msg)

    def _record_failed_attempt(self, email: str) -> None:
        """Record a failed login attempt for rate limiting."""
        now = datetime.now(UTC)
        if email not in self._failed_attempts:
            self._failed_attempts[email] = []
        self._failed_attempts[email].append(now)
