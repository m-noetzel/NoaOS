"""JWT token creation and verification — SPEC.md SS5.2.

Tokens are JWTs signed with a local secret (HS256).
Two token types: access (short-lived) and refresh (long-lived).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when a token is invalid, expired, or cannot be verified."""


def create_access_token(
    *,
    user_id: str,
    secret_key: str,
    expires_minutes: int,
    session_id: str | None = None,
    token_type: str = "access",  # noqa: S107
) -> str:
    """Create a signed JWT access token.

    Claims: sub (user_id), exp, iat, jti, type.
    If session_id is provided, it is emitted as the 'sid' claim so that
    logout can identify the correct AuthSession row.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "jti": str(uuid.uuid4()),
    }
    if session_id is not None:
        payload["sid"] = session_id
    encoded: str = jwt.encode(payload, secret_key, algorithm=ALGORITHM)
    return encoded


def create_refresh_token(
    *,
    user_id: str,
    secret_key: str,
    expires_days: int,
) -> str:
    """Create a signed JWT refresh token.

    Claims: sub (user_id), exp, iat, jti, type='refresh'.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expires_days),
        "jti": str(uuid.uuid4()),
    }
    encoded: str = jwt.encode(payload, secret_key, algorithm=ALGORITHM)
    return encoded


def decode_token(token: str, *, secret_key: str) -> dict[str, Any]:
    """Decode and verify a JWT token. Raises TokenError on failure."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, secret_key, algorithms=[ALGORITHM]
        )
    except JWTError as exc:
        msg = f"Invalid token: {exc}"
        raise TokenError(msg) from exc
    return payload
