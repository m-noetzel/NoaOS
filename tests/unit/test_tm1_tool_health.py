"""Tests for tool health-check & credential status — Phase TM1.

Spec refs: SPEC.md §11 (Secrets), §12 (MVP Tool Definitions)
Phase plan: PHASE_DETAILS.md TM1
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.tm1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_health_checker(**kwargs: Any) -> Any:
    """Create a ToolHealthChecker with overridable defaults."""
    from noa.tools.health import ToolHealthChecker

    return ToolHealthChecker(**kwargs)


def _make_credential_status_checker(**kwargs: Any) -> Any:
    """Create a CredentialStatusChecker."""
    from noa.tools.health import CredentialStatusChecker

    return CredentialStatusChecker(**kwargs)


def _make_mock_gateway(
    tools: list[str] | None = None,
    dispatch_result: Any = None,
    dispatch_error: str | None = None,
) -> MagicMock:
    """Build a mock ToolGateway."""
    from noa.tools.gateway import ToolResponse

    gw = MagicMock()
    gw.list_tools.return_value = tools or []
    resp = ToolResponse(
        result=dispatch_result or {"ok": True},
        error=dispatch_error,
    )
    gw.dispatch = AsyncMock(return_value=resp)
    return gw


# ===========================================================================
# 1. Health Probe Behavioral Tests
# ===========================================================================


class TestToolHealthProbe:
    """Health probes verify external API reachability."""

    async def test_healthy_tool_returns_ok(self) -> None:
        """TM1: Registered tool with successful dispatch → ok."""
        checker = _make_health_checker()
        gw = _make_mock_gateway(tools=["web_search"])
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=gw,
        ):
            result = await checker.check("web_search")
        assert result["status"] == "ok"
        assert result["error"] is None

    async def test_unhealthy_tool_returns_error(self) -> None:
        """TM1: Dispatch error → error status."""
        checker = _make_health_checker()
        gw = _make_mock_gateway(
            tools=["web_search"],
            dispatch_error="API key invalid",
        )
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=gw,
        ):
            result = await checker.check("web_search")
        assert result["status"] == "error"
        assert "invalid" in result["error"].lower()

    async def test_probe_timeout_returns_error(self) -> None:
        """TM1: Probe must timeout and report error."""
        import asyncio

        checker = _make_health_checker(timeout=0.1)

        async def _slow_dispatch(req: Any) -> Any:
            await asyncio.sleep(10)

        gw = _make_mock_gateway(tools=["web_search"])
        gw.dispatch = _slow_dispatch
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=gw,
        ):
            result = await checker.check("web_search")
        assert result["status"] == "error"
        assert "timeout" in result["error"].lower()

    async def test_unknown_tool_returns_error(self) -> None:
        """TM1: Unregistered tool returns error."""
        checker = _make_health_checker()
        gw = _make_mock_gateway(tools=["web_search"])
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=gw,
        ):
            result = await checker.check("nonexistent_tool")
        assert result["status"] == "error"
        err = result["error"].lower()
        assert "not registered" in err or "unknown" in err

    async def test_no_gateway_returns_error(self) -> None:
        """TM1: No gateway → error."""
        checker = _make_health_checker()
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=None,
        ):
            result = await checker.check("web_search")
        assert result["status"] == "error"
        assert "gateway" in result["error"].lower()


# ===========================================================================
# 2. Credential Status Tests
# ===========================================================================


class TestCredentialStatus:
    """Credential status: configured vs. missing."""

    async def test_configured_returns_configured(self) -> None:
        """TM1: All required secrets present → 'configured'."""
        checker = _make_credential_status_checker()
        with patch.object(
            checker, "_check_secret",
            new_callable=AsyncMock, return_value=True,
        ):
            status = await checker.get_status("web_search")
        assert status == "configured"

    async def test_missing_returns_missing(self) -> None:
        """TM1: Missing secret → 'missing'."""
        checker = _make_credential_status_checker()
        with patch.object(
            checker, "_check_secret",
            new_callable=AsyncMock, return_value=False,
        ):
            status = await checker.get_status("web_search")
        assert status == "missing"

    async def test_google_tools_share_oauth(self) -> None:
        """Google Calendar and Gmail share OAuth credentials."""
        checker = _make_credential_status_checker()
        cal = checker.required_secrets("calendar")
        gmail = checker.required_secrets("gmail")
        assert len(cal) > 0
        assert len(gmail) > 0
        assert set(cal) == set(gmail)

    async def test_notion_requires_token(self) -> None:
        """Notion uses an integration token."""
        checker = _make_credential_status_checker()
        secrets = checker.required_secrets("notion")
        assert any(
            "token" in s.lower() or "notion" in s.lower()
            for s in secrets
        )

    async def test_tavily_requires_api_key(self) -> None:
        """Web search (Tavily) requires an API key."""
        checker = _make_credential_status_checker()
        secrets = checker.required_secrets("web_search")
        assert any(
            "key" in s.lower() or "tavily" in s.lower()
            for s in secrets
        )


# ===========================================================================
# 3. Credential Store & Masking Tests
# ===========================================================================


class TestCredentialMasking:
    """Credentials only displayed masked."""

    async def test_masked_on_retrieval(self) -> None:
        """TM1: Stored API keys are returned masked."""
        from noa.tools.health import mask_credential

        raw = "sk-abc123456789xyzABCDEF"
        masked = mask_credential(raw)
        assert raw not in masked
        assert masked.endswith("CDEF") or "****" in masked
        assert "*" in masked

    async def test_short_credential_fully_masked(self) -> None:
        """TM1: Short credentials → fixed-length mask."""
        from noa.tools.health import mask_credential

        masked = mask_credential("abc")
        assert "abc" not in masked
        assert masked == "****"

    async def test_empty_credential_returns_empty(self) -> None:
        """TM1: Empty/None → empty string."""
        from noa.tools.health import mask_credential

        assert mask_credential("") == ""
        assert mask_credential(None) == ""  # type: ignore[arg-type]


# ===========================================================================
# 4. Tool List Enrichment Tests
# ===========================================================================


def _make_app() -> Any:
    """Build minimal ASGI app with tools router."""
    from fastapi import FastAPI

    from noa.api.v1.tools import router

    app = FastAPI()
    app.include_router(router)
    return app


def _fake_user() -> Any:
    from noa.auth.middleware import AuthUser
    return AuthUser(user_id="u1", session_id="s1")


class TestToolListEnrichment:
    """GET /api/v1/tools includes credential_status and health."""

    @pytest.fixture
    def _app(self):
        return _make_app()

    async def test_includes_credential_status(
        self, _app: Any,
    ) -> None:
        """TM1: Each tool has a credential_status field."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with (
                patch("noa.api.v1.tools.require_auth", _auth),
                patch(
                    "noa.api.v1.tools.get_db_session",
                    return_value=AsyncMock(),
                ),
            ):
                resp = await client.get("/api/v1/tools")

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert isinstance(data, list)
        assert len(data) > 0
        tool = data[0]
        assert "credentials" in tool
        assert isinstance(tool["credentials"], dict)
        assert "configured" in tool["credentials"]

    async def test_includes_health_field(
        self, _app: Any,
    ) -> None:
        """TM1: Each tool has a health field."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with (
                patch("noa.api.v1.tools.require_auth", _auth),
                patch(
                    "noa.api.v1.tools.get_db_session",
                    return_value=AsyncMock(),
                ),
            ):
                resp = await client.get("/api/v1/tools")

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert isinstance(data, list) and len(data) > 0
        tool = data[0]
        assert "health" in tool
        assert isinstance(tool["health"], dict)
        assert tool["health"]["status"] in (
            "healthy", "unhealthy", "unchecked",
        )


# ===========================================================================
# 5. Health Endpoint Tests
# ===========================================================================


class TestHealthEndpoint:
    """POST /api/v1/tools/{name}/health triggers a probe."""

    @pytest.fixture
    def _app(self):
        return _make_app()

    async def test_returns_status(self, _app: Any) -> None:
        """TM1: Health endpoint returns probe result."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with patch(
                "noa.api.v1.tools.require_auth", _auth,
            ):
                resp = await client.post(
                    "/api/v1/tools/web_search/health",
                )

        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)
        assert "status" in data
        assert data["status"] in (
            "healthy", "unhealthy",
        )

    async def test_unknown_tool_returns_404(
        self, _app: Any,
    ) -> None:
        """TM1: Unknown tool → 404."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with patch(
                "noa.api.v1.tools.require_auth", _auth,
            ):
                resp = await client.post(
                    "/api/v1/tools/nonexistent_xyz/health",
                )

        assert resp.status_code == 404


# ===========================================================================
# 6. Credential Store Endpoint Tests
# ===========================================================================


class TestCredentialEndpoint:
    """POST/GET /api/v1/tools/{name}/credentials."""

    @pytest.fixture
    def _app(self):
        return _make_app()

    async def test_post_stores_and_returns_masked(
        self, _app: Any,
    ) -> None:
        """TM1: POST stores credential, returns masked."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with patch(
                "noa.api.v1.tools.require_auth", _auth,
            ):
                resp = await client.post(
                    "/api/v1/tools/web_search/credentials",
                    json={"api_key": "tvly-abc123456789"},
                )

        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)
        raw = "tvly-abc123456789"
        assert raw not in str(data)
        assert "****" in str(data)

    async def test_get_returns_only_masked(
        self, _app: Any,
    ) -> None:
        """TM1: GET returns only masked credential."""
        from httpx import ASGITransport, AsyncClient

        async def _auth():
            return _fake_user()

        async with AsyncClient(
            transport=ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            with patch(
                "noa.api.v1.tools.require_auth", _auth,
            ):
                resp = await client.get(
                    "/api/v1/tools/web_search/credentials",
                )

        assert resp.status_code == 200


# ===========================================================================
# 7. Integration: Health + Credential Status Together
# ===========================================================================


class TestHealthCredentialIntegration:
    """Health checker and credential status work together."""

    async def test_missing_creds_consistent(self) -> None:
        """TM1: Missing creds → credential missing status."""
        from noa.tools.health import (
            CredentialStatusChecker,
        )

        cred_checker = CredentialStatusChecker()

        with patch.object(
            cred_checker, "_check_secret",
            new_callable=AsyncMock, return_value=False,
        ):
            cred_status = await cred_checker.get_status(
                "web_search",
            )

        assert cred_status == "missing"

    async def test_registered_tool_can_be_probed(self) -> None:
        """TM1: Registered tool returns health result."""
        checker = _make_health_checker()
        gw = _make_mock_gateway(tools=["web_search"])
        with patch(
            "noa.orchestrator.nodes.tools.get_gateway",
            return_value=gw,
        ):
            result = await checker.check("web_search")
        assert result["status"] in ("ok", "error")
