"""Authentication middleware — SPEC.md SS5.1.

Extracts and validates Bearer tokens from the Authorization header.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from noa.auth.jwt import TokenError, decode_token
from noa.config import Settings

_bearer_scheme = HTTPBearer(auto_error=True)


def _get_settings() -> Settings:
    return Settings()


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """FastAPI dependency that enforces authentication.

    Returns the decoded JWT payload on success, raises 401 otherwise.
    """
    token = credentials.credentials
    secret = settings.secret_key or ""
    try:
        payload: dict[str, Any] = decode_token(token, secret_key=secret)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
