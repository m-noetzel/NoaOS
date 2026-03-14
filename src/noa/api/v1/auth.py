"""Auth API endpoints — SPEC.md SS5.3, SS5.4.

POST /api/v1/auth/login           — authenticate, return tokens
POST /api/v1/auth/refresh         — rotate refresh token
POST /api/v1/auth/logout          — invalidate session
POST /api/v1/auth/register        — create new user account (public)
POST /api/v1/auth/forgot-password — request password reset token
POST /api/v1/auth/reset-password  — reset password with token
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.jwt import TokenError
from noa.auth.middleware import AuthUser, require_auth
from noa.auth.service import AccountLockedError, AuthError, AuthService
from noa.config import Environment, Settings

logger = logging.getLogger(__name__)

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
        # Extract minutes from message for Retry-After header
        import re

        match = re.search(r"(\d+) minute", str(exc))
        retry_after = int(match.group(1)) * 60 if match else 1800
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(retry_after)},
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
    _set_auth_cookies(resp, result)
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
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    except AuthError as exc:
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
    """Invalidate the current session.

    BE-H12: Ensure cookies are deleted with the same attributes they were set
    with (secure, samesite, httponly, path).  Browsers only honour a cookie
    deletion when the Set-Cookie header precisely matches the original —
    mismatched attributes cause the browser to ignore the deletion and the
    session cookie remains, making it appear the user is still logged in.
    """
    rid = trace_id_ctx.get("")
    if payload.session_id:
        try:
            service = AuthService(session=session, settings=settings)
            await service.logout(session_id=uuid.UUID(payload.session_id))
        except Exception:  # noqa: BLE001
            logger.warning("Best-effort logout failed — token may be invalid/expired")

    # C6: Clear httpOnly cookies on logout.
    # Attributes must match _set_auth_cookies() exactly for browsers to honour
    # the deletion (RFC 6265: path + domain must match; secure/samesite should match).
    is_secure = settings.noa_env == Environment.PRODUCTION
    samesite: Literal["strict", "lax"] = "strict" if is_secure else "lax"

    response.delete_cookie(
        "noa_access_token",
        path="/",
        httponly=True,
        secure=is_secure,
        samesite=samesite,
    )
    response.delete_cookie(
        "noa_refresh_token",
        path="/api/v1/auth",
        httponly=True,
        secure=is_secure,
        samesite=samesite,
    )
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


# ---------------------------------------------------------------------------
# Google OAuth2 Routes — SPEC.md §12.1, §12.2, §11.1, §5.3
# ---------------------------------------------------------------------------

# In-memory CSRF state store: {state_token: {"user_id", "platform", "expires"}}
# Single-user system — short-lived, never persisted.
# TTL: 600 seconds (10 minutes); expired entries pruned on each authorize call.
_oauth_states: dict[str, dict[str, Any]] = {}
_OAUTH_STATE_TTL = 600.0  # seconds


def _prune_expired_oauth_states() -> None:
    """Remove expired OAuth state entries to prevent unbounded growth."""
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if v.get("expires", 0) < now]
    for k in expired:
        _oauth_states.pop(k, None)


def _get_google_scopes() -> list[str]:
    """Combined Calendar + Gmail scopes per §12.1 and §12.2."""
    from noa.tools.google_auth import CALENDAR_SCOPES, GMAIL_SCOPES

    return CALENDAR_SCOPES + GMAIL_SCOPES


def _get_live_google_client() -> Any:
    """Get the live GoogleAuthClient from app state.

    Tries the direct accessor first (set by google_auth module at startup).
    Falls back to gateway adapter traversal for backwards compatibility.
    """
    from noa.api.app_state import get_app

    # Try direct accessor first — set by _set_live_google_client() below
    app = get_app()
    if app is not None:
        client = getattr(app.state, "google_auth_client", None)
        if client is not None:
            return client

    # Fallback: traverse gateway adapters (fragile, kept for compatibility)
    from noa.api.app_state import get_gateway

    gateway = get_gateway()
    if gateway is not None and hasattr(gateway, "_adapters"):
        for name in ("calendar", "gmail"):
            adapter = gateway._adapters.get(name)
            if adapter is not None and hasattr(adapter, "_tool"):
                tool = adapter._tool
                if hasattr(tool, "_api_client") and hasattr(
                    tool._api_client, "_auth_client"
                ):
                    client = tool._api_client._auth_client
                    # Cache for next call
                    if app is not None:
                        app.state.google_auth_client = client
                    return client
    return None


@router.get("/google/authorize")
async def google_authorize(
    auth_user: AuthUser = Depends(require_auth),  # noqa: B008
    platform: str | None = Query(default=None),
) -> dict[str, Any]:
    """Generate Google OAuth2 authorization URL with CSRF state.

    Args:
        platform: Optional client platform. Pass "ios" from iOS clients so the
                  callback redirects to noaapp:// instead of the web settings page.

    Returns:
        JSON: {"auth_url": "https://accounts.google.com/..."}

    Requires JWT authentication. The state parameter is stored server-side
    and verified on callback to prevent CSRF (§5.3).
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.environ.get(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/callback",
    )

    if not (client_id and client_secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google OAuth2 not configured — "
                "set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
            ),
        )

    from noa.tools.google_auth import GoogleAuthClient

    client = GoogleAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    scopes = _get_google_scopes()

    # Prune expired states and generate a new CSRF state token
    _prune_expired_oauth_states()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "user_id": str(auth_user.user_id),
        "platform": platform or "web",
        "expires": time.time() + _OAUTH_STATE_TTL,
    }

    # Append state to auth URL
    from urllib.parse import urlencode

    base_url = client.get_auth_url(scopes)
    auth_url = base_url + "&" + urlencode({"state": state})

    rid = trace_id_ctx.get("")
    return success_envelope(data={"auth_url": auth_url}, trace_id=rid)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Any:
    """Handle Google OAuth2 callback: exchange code, persist tokens, redirect.

    On success: redirects to {NOA_DOMAIN}/settings?google=connected
    On error: returns 400.

    CSRF state is verified before code exchange (§5.3).
    Tokens are encrypted before DB storage (§11.1).
    """
    # Handle OAuth2 error response
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth2 error: {error}",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    # Verify CSRF state (peek before consuming — consume only after service check)
    # Also reject expired states (TTL enforcement)
    state_entry = _oauth_states.get(state) if state else None
    if state_entry is None or state_entry.get("expires", 0) < time.time():
        if state and state in _oauth_states:
            _oauth_states.pop(state, None)  # Clean up expired entry
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth2 state parameter",
        )

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.environ.get(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/callback",
    )

    if not (client_id and client_secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth2 not configured",
        )

    # Consume state only after confirming service is available
    # state is non-None: state_entry not None only when state is truthy
    assert state is not None  # noqa: S101
    state_data = _oauth_states.pop(state)
    user_id_str = state_data["user_id"]
    client_platform = state_data.get("platform", "web")
    user_id = uuid.UUID(user_id_str)

    from noa.tools.google_auth import GoogleAuthClient, GoogleAuthError

    client = GoogleAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    try:
        tokens = await client.exchange_code(code)
    except (GoogleAuthError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {exc}",
        ) from exc

    # Persist encrypted tokens to DB (§11.1)
    from sqlalchemy import select as sa_select

    from noa.db.models.google_credential import GoogleCredential
    from noa.tools._token_crypto import encrypt_token

    enc_access = encrypt_token(tokens["access_token"])
    enc_refresh = encrypt_token(tokens["refresh_token"])

    stmt = sa_select(GoogleCredential).where(GoogleCredential.user_id == user_id)
    db_result = await session.execute(stmt)
    cred = db_result.scalar_one_or_none()

    if cred is not None:
        cred.access_token_enc = enc_access
        cred.refresh_token_enc = enc_refresh
    else:
        cred = GoogleCredential(
            user_id=user_id,
            access_token_enc=enc_access,
            refresh_token_enc=enc_refresh,
        )
        session.add(cred)

    await session.commit()

    # Update live client if available
    live_client = _get_live_google_client()
    if live_client is not None:
        live_client.set_tokens(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )

    logger.info("Google OAuth2 tokens persisted for user %s", user_id)

    # Redirect based on client platform
    if client_platform == "ios":
        # iOS ASWebAuthenticationSession intercepts this custom-scheme URL
        redirect_url = "noaapp://oauth/callback?google=connected"
    else:
        noa_domain = os.environ.get("NOA_DOMAIN", "localhost:8000")
        frontend_url = os.environ.get("FRONTEND_URL", "")
        if frontend_url:
            redirect_url = f"{frontend_url}/settings?google=connected"
        else:
            local_hosts = ("localhost:8000", "localhost")
            scheme = "https" if noa_domain not in local_hosts else "http"
            redirect_url = f"{scheme}://{noa_domain}/settings?google=connected"

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/google/status")
async def google_status(
    auth_user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Return Google OAuth2 connection status for the authenticated user.

    Returns:
        JSON: {"connected": bool, "scopes": [...]}
    """
    from sqlalchemy import select as sa_select

    from noa.db.models.google_credential import GoogleCredential

    stmt = sa_select(GoogleCredential).where(
        GoogleCredential.user_id == auth_user.user_id
    )
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    connected = cred is not None
    scopes = _get_google_scopes() if connected else []

    rid = trace_id_ctx.get("")
    return success_envelope(
        data={"connected": connected, "scopes": scopes},
        trace_id=rid,
    )


@router.delete("/google/disconnect", status_code=status.HTTP_200_OK)
async def google_disconnect(
    auth_user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Delete Google OAuth2 credentials for the authenticated user.

    Removes the DB row and clears tokens from the live client.
    Returns 404 if no credentials exist.
    """
    from sqlalchemy import select as sa_select

    from noa.db.models.google_credential import GoogleCredential

    stmt = sa_select(GoogleCredential).where(
        GoogleCredential.user_id == auth_user.user_id
    )
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Google credentials found",
        )

    await session.delete(cred)
    await session.commit()

    # Clear tokens from live client
    live_client = _get_live_google_client()
    if live_client is not None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(live_client.clear_tokens())
        except RuntimeError:
            pass

    logger.info("Google OAuth2 credentials disconnected for user %s", auth_user.user_id)

    rid = trace_id_ctx.get("")
    return success_envelope(data={"disconnected": True}, trace_id=rid)
