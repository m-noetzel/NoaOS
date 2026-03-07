"""Auth API endpoints — SPEC.md SS5.3, SS5.4.

POST /api/v1/auth/login    — authenticate, return tokens
POST /api/v1/auth/refresh  — rotate refresh token
POST /api/v1/auth/logout   — invalidate session
POST /api/v1/auth/register — create new user account (public)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
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


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Authenticate user and return access + refresh tokens."""
    rid = trace_id_ctx.get("")
    try:
        service = AuthService(session=session, settings=settings)
        try:
            did = uuid.UUID(body.device_id)
        except (ValueError, AttributeError):
            did = uuid.uuid5(uuid.NAMESPACE_DNS, body.device_id or "unknown")
        result = await service.login(
            email=body.email,
            password=body.password,
            device_id=did,
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
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Rotate refresh token and return new token pair."""
    rid = trace_id_ctx.get("")
    try:
        service = AuthService(session=session, settings=settings)
        try:
            did = uuid.UUID(body.device_id)
        except (ValueError, AttributeError):
            did = uuid.uuid5(uuid.NAMESPACE_DNS, body.device_id or "unknown")
        result = await service.refresh(
            refresh_token=body.refresh_token,
            device_id=did,
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
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Invalidate the current session."""
    rid = trace_id_ctx.get("")
    session_id_str = payload.get("sid", "")
    try:
        service = AuthService(session=session, settings=settings)
        await service.logout(session_id=uuid.UUID(session_id_str))
    except Exception:  # noqa: BLE001, S110
        pass  # Best-effort logout — token may be invalid/expired

    return success_envelope(data={"status": "logged_out"}, trace_id=rid)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Register a new user account. Public — no auth required."""
    rid = trace_id_ctx.get("")
    try:
        service = AuthService(session=session, settings=settings)
        result = await service.register(email=body.email, password=body.password)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return success_envelope(data=result, trace_id=rid)
