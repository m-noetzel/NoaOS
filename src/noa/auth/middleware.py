"""Authentication middleware — SPEC.md SS5.1.

Extracts and validates Bearer tokens from the Authorization header.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from noa.auth.jwt import ALGORITHM
from noa.config import Settings

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Typed identity extracted from a validated JWT.

    FINDINGS.md M11: replaces raw dict with fragile .get() fallback chains.
    The user_id is always a validated uuid.UUID — never a raw string.
    """

    user_id: uuid.UUID
    session_id: str | None = None


def _get_settings() -> Settings:
    return Settings()


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> AuthUser:
    """FastAPI dependency that enforces authentication.

    Accepts Bearer token from Authorization header or httpOnly cookie (C6).
    Returns an AuthUser on success, raises 401 otherwise.
    """
    token: str | None = None
    if credentials:
        token = credentials.credentials
    else:
        # Fall back to httpOnly cookie (C6)
        token = request.cookies.get("noa_access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY is not set — refusing to validate tokens with an empty key"
        )
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # M11: Extract and validate user_id from 'sub' claim
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user identity (sub claim)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity (sub claim is not a valid UUID)",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    session_id = payload.get("sid")
    return AuthUser(user_id=user_id, session_id=session_id)
