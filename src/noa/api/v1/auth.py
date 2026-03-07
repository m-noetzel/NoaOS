"""Auth API endpoints — SPEC.md SS5.3, SS5.4.

POST /api/v1/auth/login    — authenticate, return tokens
POST /api/v1/auth/refresh  — rotate refresh token
POST /api/v1/auth/logout   — invalidate session
POST /api/v1/auth/register — create new user account (public)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


def _set_auth_cookies(
    response: Response, tokens: dict[str, Any],
) -> None:
    """Set httpOnly cookies for auth tokens (C6)."""
    response.set_cookie(
        key="noa_access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=900,  # 15 minutes
        path="/",
    )
    response.set_cookie(
        key="noa_refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,  # 7 days
        path="/api/v1/auth",  # Only sent to auth endpoints
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
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

    _set_auth_cookies(response, result)
    # C6: Don't expose raw tokens in JSON body — they're in httpOnly cookies
    safe_result = {
        k: v for k, v in result.items()
        if k not in ("access_token", "refresh_token")
    }
    safe_result["authenticated"] = True
    return success_envelope(data=safe_result, trace_id=rid)


@router.post("/refresh")
async def refresh(
    request: Request,
    body: RefreshRequest,
    response: Response,
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
        # C6: Prefer refresh token from httpOnly cookie, fall back to body
        refresh_token = (
            request.cookies.get("noa_refresh_token")
            or body.refresh_token
        )
        result = await service.refresh(
            refresh_token=refresh_token,
            device_id=did,
        )
    except (AuthError, TokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _set_auth_cookies(response, result)
    safe_result = {
        k: v for k, v in result.items()
        if k not in ("access_token", "refresh_token")
    }
    safe_result["authenticated"] = True
    return success_envelope(data=safe_result, trace_id=rid)


@router.post("/logout")
async def logout(
    response: Response,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Invalidate the current session."""
    rid = trace_id_ctx.get("")
    if payload.session_id:
        try:
            service = AuthService(session=session, settings=settings)
            await service.logout(session_id=uuid.UUID(payload.session_id))
        except Exception:  # noqa: BLE001, S110
            pass  # Best-effort logout — token may be invalid/expired

    # C6: Clear httpOnly cookies on logout
    response.delete_cookie("noa_access_token", path="/")
    response.delete_cookie("noa_refresh_token", path="/api/v1/auth")
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
