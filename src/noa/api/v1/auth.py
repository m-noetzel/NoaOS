"""Auth API endpoints — SPEC.md SS5.3, SS5.4.

POST /api/v1/auth/login           — authenticate, return tokens
POST /api/v1/auth/refresh         — rotate refresh token
POST /api/v1/auth/logout          — invalidate session
POST /api/v1/auth/register        — create new user account (public)
POST /api/v1/auth/forgot-password — request password reset token
POST /api/v1/auth/reset-password  — reset password with token
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.jwt import TokenError
from noa.auth.middleware import require_auth
from noa.auth.service import AccountLockedError, AuthError, AuthService
from noa.config import Environment, Settings

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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class AuthTokenResponse(BaseModel):
    """Auth token response — SPEC.md §5.3.

    For web clients: tokens are set as httpOnly cookies (C6); only metadata
    is returned in the body.
    For native iOS clients: access_token and refresh_token are also included
    in the body so the iOS Keychain can store them securely (SPEC.md §29.3).
    expires_in (seconds) is returned for AuthViewModel auto-refresh scheduling.
    """

    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 1800  # default 30 min; actual value computed from settings
    authenticated: bool = True
    # Native client token delivery — None for web, populated for iOS (SPEC.md §29.3)
    access_token: str | None = None  # noqa: S105
    refresh_token: str | None = None  # noqa: S105


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings() -> Settings:
    return Settings()


def _set_auth_cookies(
    response: Response, tokens: dict[str, Any],
) -> None:
    """Set httpOnly cookies for auth tokens (C6)."""
    settings = _get_settings()
    is_secure = settings.noa_env == Environment.PRODUCTION
    response.set_cookie(
        key="noa_access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=is_secure,
        samesite="lax" if not is_secure else "strict",
        max_age=900,  # 15 minutes
        path="/",
    )
    response.set_cookie(
        key="noa_refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=is_secure,
        samesite="lax" if not is_secure else "strict",
        max_age=7 * 24 * 3600,  # 7 days
        path="/api/v1/auth",  # Only sent to auth endpoints
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AuthTokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> Any:
    """Authenticate user and return access + refresh tokens.

    iOS4: tokens are set as httpOnly cookies (C6); expires_in is returned
    in the body so AuthViewModel can schedule automatic token refresh.
    Response uses the standard success_envelope so both web and iOS clients
    can decode via ApiResponse<AuthTokens>.  Returns JSONResponse directly
    so FastAPI skips response_model serialization while keeping the model
    for OpenAPI docs.
    """
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

    expires_in = settings.access_token_expire_minutes * 60
    envelope = success_envelope(
        data={
            "authenticated": True,
            "token_type": "bearer",  # noqa: S106
            "expires_in": expires_in,
            "access_token": result.get("access_token"),  # noqa: S106
            "refresh_token": result.get("refresh_token"),  # noqa: S106
        },
        trace_id=rid,
    )
    # Return JSONResponse so FastAPI skips response_model serialization,
    # preserving the envelope. JSONResponse subclasses Response so _set_auth_cookies
    # works identically — both expose set_cookie() (C6).
    resp = JSONResponse(content=envelope)
    _set_auth_cookies(resp, result)  # type: ignore[arg-type]
    return resp


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
    # Return tokens in body for native iOS clients (SPEC.md §29.3);
    # httpOnly cookies serve web clients.
    return success_envelope(
        data={
            "authenticated": True,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "access_token": result.get("access_token"),  # noqa: S106
            "refresh_token": result.get("refresh_token"),  # noqa: S106
        },
        trace_id=rid,
    )


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


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Request a password reset token. Always returns 200 to avoid email enumeration."""
    rid = trace_id_ctx.get("")
    service = AuthService(session=session, settings=settings)
    result = await service.request_password_reset(email=body.email)
    return success_envelope(data=result, trace_id=rid)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(_get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Reset password using a valid reset token."""
    rid = trace_id_ctx.get("")
    try:
        service = AuthService(session=session, settings=settings)
        result = await service.reset_password(
            token=body.token, new_password=body.new_password,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return success_envelope(data=result, trace_id=rid)
