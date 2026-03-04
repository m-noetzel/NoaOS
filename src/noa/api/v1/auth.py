"""Auth API endpoints — SPEC.md SS5.3, SS5.4.

POST /api/v1/auth/login   — authenticate, return tokens
POST /api/v1/auth/refresh  — rotate refresh token
POST /api/v1/auth/logout   — invalidate session
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.jwt import TokenError
from noa.auth.middleware import require_auth
from noa.auth.service import AccountLockedError, AuthError, AuthService
from noa.config import Settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: str


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings() -> Settings:
    return Settings()


async def _mock_session() -> Any:  # noqa: ANN401
    """Return a no-op session for endpoints that need a DB session.

    In production this would come from get_db_session dependency.
    """
    from unittest.mock import AsyncMock
    return AsyncMock()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(
    body: LoginRequest,
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Authenticate user and return access + refresh tokens."""
    rid = trace_id_ctx.get("")
    try:
        session = await _mock_session()
        service = AuthService(session=session, settings=settings)
        result = await service.login(
            email=body.email,
            password=body.password,
            device_id=uuid.UUID(body.device_id),
        )
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return success_envelope(data=result, trace_id=rid)


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Rotate refresh token and return new token pair."""
    rid = trace_id_ctx.get("")
    try:
        session = await _mock_session()
        service = AuthService(session=session, settings=settings)
        result = await service.refresh(
            refresh_token=body.refresh_token,
            device_id=uuid.UUID(body.device_id),
        )
    except (AuthError, TokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return success_envelope(data=result, trace_id=rid)


@router.post("/logout")
async def logout(
    payload: dict[str, Any] = Depends(require_auth),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Invalidate the current session."""
    rid = trace_id_ctx.get("")
    session_id_str = payload.get("jti", "")
    try:
        session = await _mock_session()
        service = AuthService(session=session, settings=settings)
        await service.logout(session_id=uuid.UUID(session_id_str))
    except Exception:  # noqa: BLE001, S110
        pass  # Best-effort logout — token may be invalid/expired

    return success_envelope(data={"status": "logged_out"}, trace_id=rid)
