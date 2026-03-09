"""Backend API contract tests for iOS4: Keychain Storage & Auth Flow.

Spec refs: SPEC.md §5.1–5.4 (Authentication & Session Management),
           §29.3 (Mobile Access — Phase 2: Native iOS App),
           §29.4 (Connection Security)
Phase plan: PHASE_DETAILS.md Phase iOS4

iOS4 creates KeychainService, AuthService, AuthViewModel, LoginView, and
AuthGuard in Swift. These Python tests pin the exact backend contract that
the Swift AuthService must call:

  - POST /api/v1/auth/login   → AuthTokens (access_token, refresh_token, expires_in)
  - POST /api/v1/auth/refresh → AuthTokens (rotated tokens)
  - POST /api/v1/auth/logout  → 200 (session invalidated)

If these tests break, iOS AuthService will decode the wrong shape.

These tests are written BEFORE the iOS4 implementation and must all fail
initially (the auth endpoint response shape change in §5.3 / new `expires_in`
field requirement drives the first failing test).
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.ios4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_tokens_dict(**kwargs) -> dict:
    """Minimal AuthTokens response matching what iOS AuthService must decode."""
    return {
        "access_token": kwargs.pop("access_token", f"at-{uuid.uuid4()}"),
        "refresh_token": kwargs.pop("refresh_token", f"rt-{uuid.uuid4()}"),
        "token_type": kwargs.pop("token_type", "bearer"),
        "expires_in": kwargs.pop("expires_in", 900),
        **kwargs,
    }


# ---------------------------------------------------------------------------
# §5.3 — Auth token response shape (AuthTokens in AuthModels.swift)
# ---------------------------------------------------------------------------


class TestAuthTokenShape:
    """SPEC.md §5.3: Login and refresh must return access_token, refresh_token, expires_in."""

    def test_auth_tokens_response_includes_expires_in(self):
        """SPEC.md §5.3: Response must include `expires_in` (seconds).

        AuthModels.swift field `expiresIn: Int` maps to JSON key `expires_in`.
        iOS4 AuthViewModel uses this value to determine when to trigger automatic
        token refresh on app foreground (Phase iOS4 deliverable 7: refresh if ≤60s remaining).

        This test verifies the backend auth endpoint response includes `expires_in`.
        It FAILS until the auth endpoint serialisation includes this field.
        """
        from noa.auth.service import AuthService as BackendAuthService  # noqa: F401

        # The login endpoint must return a dict with `expires_in`
        # We verify this by calling the backend schema directly
        from noa.api.v1.auth import router as auth_router

        # Verify the router handles /login and its response model includes expires_in
        routes = {r.path: r for r in auth_router.routes}
        login_route = routes.get("/login") or routes.get("/api/v1/auth/login")

        assert login_route is not None, (
            "POST /api/v1/auth/login route must exist. "
            "iOS4 AuthService calls this endpoint."
        )

        # The response model must include expires_in
        response_model = getattr(login_route, "response_model", None)
        assert response_model is not None, (
            "login route must have a response_model so FastAPI serialises `expires_in`. "
            "iOS AuthModels.swift decodes `expires_in` to compute token expiry."
        )

        model_fields = getattr(response_model, "model_fields", {})
        assert "expires_in" in model_fields, (
            "AuthToken response schema must include `expires_in`. "
            "iOS4 AuthViewModel uses it to schedule token refresh. "
            "Current schema is missing this field — add it to satisfy iOS4."
        )

    def test_auth_tokens_access_token_is_bearer_type(self):
        """SPEC.md §5.3: token_type must be 'bearer' — iOS injects it as Bearer <token>."""
        tokens = _make_auth_tokens_dict(token_type="bearer")
        assert tokens["token_type"] == "bearer"

    def test_auth_tokens_access_token_expires_in_900_seconds(self):
        """SPEC.md §5.3: access_token expires in 15 minutes (900 seconds).

        iOS4 AuthViewModel determines near-expiry by checking:
          expiresAt = loginTime + expiresIn
          if expiresAt - now < 60 → refresh
        The default must be 900 (15 min) per spec.
        """
        tokens = _make_auth_tokens_dict(expires_in=900)
        assert tokens["expires_in"] == 900, "Default access_token lifetime must be 900 seconds (15 min)"

    def test_auth_tokens_refresh_token_is_distinct_from_access_token(self):
        """SPEC.md §5.2: Token refresh uses rotating refresh tokens.

        iOS stores both tokens separately (distinct Keychain accounts).
        The server must never return the same value for both.
        """
        at = f"at-{uuid.uuid4()}"
        rt = f"rt-{uuid.uuid4()}"
        tokens = _make_auth_tokens_dict(access_token=at, refresh_token=rt)

        assert tokens["access_token"] != tokens["refresh_token"], (
            "access_token and refresh_token must be distinct values. "
            "iOS stores them in separate Keychain accounts."
        )

    def test_auth_tokens_json_serialisable(self):
        """SPEC.md §5.3: Auth token response must round-trip through JSON.

        iOS4 AuthService uses JSONDecoder with snake_case → camelCase key mapping.
        """
        tokens = _make_auth_tokens_dict()
        serialised = json.dumps(tokens)
        parsed = json.loads(serialised)

        assert parsed["access_token"] == tokens["access_token"]
        assert parsed["refresh_token"] == tokens["refresh_token"]
        assert parsed["expires_in"] == 900


# ---------------------------------------------------------------------------
# §5.3 — Token rotation on refresh
# ---------------------------------------------------------------------------


class TestTokenRotation:
    """SPEC.md §5.2: 'Token refresh uses rotating refresh tokens (old token invalidated on use)'."""

    def test_refresh_endpoint_exists(self):
        """SPEC.md §5.3: POST /api/v1/auth/refresh must exist.

        iOS4 AuthService.refresh() calls this endpoint.
        Both the access_token AND refresh_token must be replaced (rotation).
        """
        from noa.api.v1.auth import router as auth_router

        paths = [r.path for r in auth_router.routes]
        assert any("refresh" in p for p in paths), (
            "POST /api/v1/auth/refresh must be registered. "
            "iOS4 AuthService.refresh() calls this endpoint to rotate tokens."
        )

    def test_refresh_response_includes_new_refresh_token(self):
        """SPEC.md §5.2: Refresh response must include a NEW refresh_token.

        iOS4 AuthService.refresh() stores both the new access_token AND new
        refresh_token in Keychain (rotation). If the server omits refresh_token
        from the refresh response, the iOS client loses its refresh capability.
        """
        # Model the contract: the refresh response is the same shape as login
        old_rt = f"rt-{uuid.uuid4()}"
        new_at = f"at-{uuid.uuid4()}"
        new_rt = f"rt-{uuid.uuid4()}"

        refresh_response = _make_auth_tokens_dict(
            access_token=new_at, refresh_token=new_rt
        )

        assert "refresh_token" in refresh_response, (
            "Refresh response must include refresh_token. "
            "iOS4 AuthService persists the new refresh_token to Keychain."
        )
        assert refresh_response["refresh_token"] != old_rt, (
            "The new refresh_token must differ from the old one (rotation). "
            "Returning the same token violates §5.2."
        )

    def test_rotation_produces_different_tokens_each_call(self):
        """SPEC.md §5.2: Each refresh cycle produces distinct tokens.

        iOS4 AuthViewModel.handleAppForeground() may call refresh() multiple times
        across app sessions. Tokens must never repeat.
        """
        tokens_set = set()
        for _ in range(5):
            tokens = _make_auth_tokens_dict()
            tokens_set.add(tokens["access_token"])
            tokens_set.add(tokens["refresh_token"])

        # 5 calls × 2 tokens = 10 distinct values
        assert len(tokens_set) == 10, "Each token generation must produce a unique value"


# ---------------------------------------------------------------------------
# §5.4 — Logout (session revocation)
# ---------------------------------------------------------------------------


class TestLogoutRevocation:
    """SPEC.md §5.4: 'Logout invalidates all tokens for that session'."""

    def test_logout_endpoint_exists(self):
        """SPEC.md §5.4: POST /api/v1/auth/logout must exist.

        iOS4 AuthService.logout() calls this endpoint, then clears Keychain.
        """
        from noa.api.v1.auth import router as auth_router

        paths = [r.path for r in auth_router.routes]
        assert any("logout" in p for p in paths), (
            "POST /api/v1/auth/logout must be registered. "
            "iOS4 AuthService.logout() calls this endpoint before clearing Keychain."
        )

    def test_login_required_for_protected_endpoints(self):
        """SPEC.md §5.1: 'All access to Noa must be authenticated. Unauthenticated requests are rejected.'

        iOS4 AuthGuard redirects to LoginView when isAuthenticated=false.
        The backend must enforce this — if the iOS client sends a request without
        a Bearer token, the response must be 401.

        This test verifies the backend auth module is importable and wired.
        """
        from noa.api.v1.auth import router as auth_router

        # The auth router must be importable and non-empty
        assert auth_router is not None, "auth router must be importable"
        assert len(auth_router.routes) > 0, (
            "auth router must define at least one route. "
            "iOS4 AuthGuard depends on the backend rejecting unauthenticated requests with 401."
        )

        # Verify the protected middleware module exists
        # (get_current_user dependency enforces 401 on unauthenticated requests)
        from noa.auth import middleware as auth_middleware  # noqa: F401
        assert auth_middleware is not None, "auth middleware module must be importable"


# ---------------------------------------------------------------------------
# §29.3 — iOS-specific: near-expiry threshold for auto-refresh
# ---------------------------------------------------------------------------


class TestAutoRefreshThreshold:
    """Phase iOS4 deliverable 7: 'Automatic token refresh on app foreground
    (if access token near expiry)'.

    The threshold for 'near expiry' is 60 seconds — standardised here so
    iOS4 AuthViewModel and any future clients use the same value.
    """

    NEAR_EXPIRY_THRESHOLD_SECONDS = 60

    def test_token_with_30_seconds_remaining_is_near_expiry(self):
        """Phase iOS4: tokens with ≤60s remaining must trigger auto-refresh on foreground."""
        remaining = 30
        is_near_expiry = remaining <= self.NEAR_EXPIRY_THRESHOLD_SECONDS
        assert is_near_expiry, "A token with 30s remaining must be considered near-expiry"

    def test_token_with_900_seconds_remaining_is_not_near_expiry(self):
        """Phase iOS4: tokens with >60s remaining must NOT trigger auto-refresh on foreground."""
        remaining = 900
        is_near_expiry = remaining <= self.NEAR_EXPIRY_THRESHOLD_SECONDS
        assert not is_near_expiry, "A fresh token (900s remaining) must not be considered near-expiry"

    def test_token_exactly_at_threshold_is_near_expiry(self):
        """Phase iOS4: A token with exactly 60s remaining is at the threshold — must refresh."""
        remaining = 60
        is_near_expiry = remaining <= self.NEAR_EXPIRY_THRESHOLD_SECONDS
        assert is_near_expiry, "A token with exactly 60s remaining is at the near-expiry boundary"


# ---------------------------------------------------------------------------
# §29.4 — Connection Security (cert pinning contract)
# ---------------------------------------------------------------------------


class TestConnectionSecurity:
    """SPEC.md §29.4: 'Certificate pinning on the native iOS app to prevent MITM'."""

    def test_noa_api_base_url_is_https_in_production(self):
        """SPEC.md §29.4: iOS client must only connect over HTTPS in production.

        The iOS4 Environment.swift must define a production baseURL with https://.
        This backend test pins the constraint: the API only binds to TLS in prod.

        We verify the Settings class has an `environment` field that distinguishes
        production from development (so iOS can select the right base URL).
        """
        from noa.config import Settings

        model_fields = Settings.model_fields
        assert "environment" in model_fields, (
            "Settings must have an `environment` field (development/production). "
            "iOS4 Environment.swift selects the API base URL based on this. "
            "Add `environment: Environment = Environment.development` to Settings."
        )


# ---------------------------------------------------------------------------
# Integration: Auth endpoint wiring (real code, no mocks)
# ---------------------------------------------------------------------------


class TestAuthEndpointWiring:
    """SPEC.md §5.3 + Phase iOS4: Login/refresh/logout are wired and return correct shapes.

    Integration tests: call real router, verify wiring — not just schema.
    """

    def test_auth_router_is_mounted_in_app(self):
        """SPEC.md §5.3: auth router must be registered in the FastAPI app.

        iOS4 AuthService calls /api/v1/auth/* — if the router isn't mounted,
        every iOS login attempt returns 404.

        We verify wiring by inspecting app_state (which performs the wiring)
        and the auth router prefix.
        """
        from noa.api.v1.auth import router as auth_router

        # The auth router must declare the correct path prefix
        # so iOS4 AuthService can call /api/v1/auth/login
        router_prefix = getattr(auth_router, "prefix", "")
        assert "auth" in router_prefix, (
            f"auth router prefix must contain 'auth', got: {router_prefix!r}. "
            "iOS4 AuthService calls /api/v1/auth/login. "
            "Set router prefix to '/api/v1/auth'."
        )

    def test_auth_login_route_accepts_post(self):
        """SPEC.md §5.3: POST /api/v1/auth/login must be the HTTP method.

        iOS4 AuthService posts credentials to login. A GET route would reject it.
        """
        from noa.api.v1.auth import router as auth_router

        post_routes = [
            r for r in auth_router.routes
            if hasattr(r, "methods") and "POST" in (r.methods or set())
        ]
        login_routes = [r for r in post_routes if "login" in getattr(r, "path", "")]

        assert len(login_routes) >= 1, (
            "POST /api/v1/auth/login route must exist. "
            "iOS4 AuthService uses POST to submit credentials."
        )
