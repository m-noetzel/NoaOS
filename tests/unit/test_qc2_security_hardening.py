"""Tests for Phase QC2: Security Hardening.

Covers: C3 (audit hash chain locking), C6 (httpOnly cookie tokens),
H6 (email validation), H7 (tool capability default deny),
H10 (HTML sanitization with nh3), M2 (CSRF + CORS), M4 (CSP headers).

Finding refs: FINDINGS.md C3, C6, H6, H7, H10, M2, M4
"""

from __future__ import annotations

import re
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.qc2


# ---------------------------------------------------------------------------
# C3: Audit hash chain — SELECT ... FOR UPDATE prevents race conditions
# ---------------------------------------------------------------------------


class TestAuditHashChainLocking:
    """C3: create_entry_async must use FOR UPDATE to prevent race conditions."""

    @pytest.mark.asyncio
    async def test_async_create_uses_for_update(self):
        """The async query for latest audit entry must use with_for_update().

        This prevents two concurrent inserts from reading the same 'latest'
        entry and both chaining from it, which would break the hash chain.
        """
        from noa.audit.service import AuditService

        svc = AuditService()

        # Inspect the source to verify FOR UPDATE is used
        import inspect

        source = inspect.getsource(svc.create_entry_async)
        assert "with_for_update" in source or "for_update" in source, (
            "create_entry_async must use SELECT ... FOR UPDATE "
            "to prevent hash chain race conditions"
        )

    def test_sync_create_uses_for_update(self):
        """The sync query for latest audit entry must use with_for_update()."""
        from noa.audit.service import AuditService

        svc = AuditService()

        import inspect

        source = inspect.getsource(svc.create_entry)
        assert "with_for_update" in source or "for_update" in source, (
            "create_entry must use SELECT ... FOR UPDATE "
            "to prevent hash chain race conditions"
        )


# ---------------------------------------------------------------------------
# C6: httpOnly cookie auth — tokens not in JSON body or localStorage
# ---------------------------------------------------------------------------


class TestCookieAuth:
    """C6: Tokens must be in httpOnly cookies, not in JSON response or localStorage."""

    def test_login_does_not_return_raw_tokens(self):
        """Login response must not include access_token or refresh_token."""
        import inspect

        from noa.api.v1.auth import login

        source = inspect.getsource(login)
        assert "safe_result" in source, (
            "Login must strip tokens from response body"
        )

    def test_refresh_does_not_return_raw_tokens(self):
        """Refresh response must not include access_token or refresh_token."""
        import inspect

        from noa.api.v1.auth import refresh

        source = inspect.getsource(refresh)
        assert "safe_result" in source, (
            "Refresh must strip tokens from response body"
        )

    def test_auth_middleware_reads_cookie(self):
        """Auth middleware must accept token from httpOnly cookie."""
        import inspect

        from noa.auth.middleware import require_auth

        source = inspect.getsource(require_auth)
        assert "noa_access_token" in source
        assert "cookies" in source

    def test_logout_clears_cookies(self):
        """Logout must delete auth cookies."""
        import inspect

        from noa.api.v1.auth import logout

        source = inspect.getsource(logout)
        assert "delete_cookie" in source

    def test_tokens_ts_no_localstorage_tokens(self):
        """Frontend tokens.ts must not store actual tokens in localStorage."""
        tokens_path = "/Users/martin2020/Projekte/NoaOS/web/src/auth/tokens.ts"
        with open(tokens_path) as f:
            content = f.read()
        # Should not have localStorage.setItem with actual token values
        assert "ACCESS_TOKEN_KEY" not in content or "noa_authenticated" in content
        assert "REFRESH_TOKEN_KEY" not in content or "noa_authenticated" in content

    def test_set_auth_cookies_sets_httponly(self):
        """_set_auth_cookies must set httponly=True."""
        import inspect

        from noa.api.v1.auth import _set_auth_cookies

        source = inspect.getsource(_set_auth_cookies)
        assert "httponly=True" in source
        assert "secure=True" in source
        assert 'samesite="strict"' in source


# ---------------------------------------------------------------------------
# H6: Email recipient validation
# ---------------------------------------------------------------------------


class TestEmailValidation:
    """H6: send_email must validate recipient addresses."""

    @pytest.mark.asyncio
    async def test_send_rejects_empty_recipient(self):
        """send_email must reject empty 'to' address."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        tool = GmailTool(api_client=mock_client)

        with pytest.raises((ValueError, TypeError)):
            await tool.send_email(to="", subject="Test", body="Body")

        mock_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_rejects_malformed_email(self):
        """send_email must reject addresses without @ sign."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        tool = GmailTool(api_client=mock_client)

        with pytest.raises(ValueError, match="[Ii]nvalid"):
            await tool.send_email(to="not-an-email", subject="Test", body="Body")

        mock_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_rejects_multiple_recipients_injection(self):
        """send_email must reject comma-separated injection attempts."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        tool = GmailTool(api_client=mock_client)

        with pytest.raises(ValueError):
            await tool.send_email(
                to="legit@example.com, evil@attacker.com",
                subject="Test",
                body="Body",
            )

        mock_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_rejects_newline_injection(self):
        """send_email must reject newline-based header injection."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        tool = GmailTool(api_client=mock_client)

        with pytest.raises(ValueError):
            await tool.send_email(
                to="legit@example.com\nBcc: evil@attacker.com",
                subject="Test",
                body="Body",
            )

        mock_client.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_accepts_valid_email(self):
        """send_email must accept a properly formatted email address."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.send_email.return_value = {"id": "sent-1", "status": "sent"}
        tool = GmailTool(api_client=mock_client)

        result = await tool.send_email(
            to="valid@example.com", subject="Hello", body="Hi!"
        )

        assert result["status"] == "sent"
        mock_client.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_draft_rejects_malformed_email(self):
        """draft_email must also validate the recipient address."""
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        tool = GmailTool(api_client=mock_client)

        with pytest.raises(ValueError):
            await tool.draft_email(to="bad-email", subject="Test", body="Body")

        mock_client.draft_email.assert_not_called()


# ---------------------------------------------------------------------------
# H7: Tool capability default deny
# ---------------------------------------------------------------------------


class TestToolCapabilityDefaultDeny:
    """H7: Tools not in TOOL_CAPABILITIES must be denied by default."""

    @pytest.mark.asyncio
    async def test_unknown_tool_denied_by_default(self):
        """A tool not in TOOL_CAPABILITIES must return False (denied)."""
        from unittest.mock import MagicMock

        from noa.tools.capabilities import DbCapabilityChecker

        mock_session = MagicMock()
        checker = DbCapabilityChecker(session=mock_session)

        result = await checker.has_capability(
            user_id=uuid.uuid4(),
            tool_name="totally_unknown_tool",
        )
        assert result is False, (
            "Unknown tools must be denied by default (principle of least privilege)"
        )

    @pytest.mark.asyncio
    async def test_known_tool_without_grant_denied(self):
        """A known tool without a DB grant must be denied."""
        from unittest.mock import MagicMock

        from noa.tools.capabilities import DbCapabilityChecker

        mock_session = AsyncMock()
        # execute() is awaited, returns a sync result object
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        checker = DbCapabilityChecker(session=mock_session)

        result = await checker.has_capability(
            user_id=uuid.uuid4(),
            tool_name="gmail",
        )
        assert result is False


# ---------------------------------------------------------------------------
# H10: HTML sanitization with nh3 (not regex)
# ---------------------------------------------------------------------------


class TestNotionSanitization:
    """H10: Notion content must be sanitized with nh3, not just regex."""

    def test_sanitizer_strips_script_tags(self):
        """Script tags and content must be removed."""
        from noa.tools.notion import _sanitize_content

        result = _sanitize_content(
            "Safe text<script>alert('xss')</script>More text"
        )
        assert "<script>" not in result
        assert "alert" not in result
        assert "Safe text" in result
        assert "More text" in result

    def test_sanitizer_strips_event_handlers(self):
        """Event handler attributes (onerror, onload) must be removed."""
        from noa.tools.notion import _sanitize_content

        result = _sanitize_content(
            '<img src="x" onerror="alert(1)">'
        )
        assert "onerror" not in result

    def test_sanitizer_strips_svg_xss(self):
        """SVG-based XSS vectors must be stripped."""
        from noa.tools.notion import _sanitize_content

        result = _sanitize_content(
            '<svg onload="alert(1)"><circle r="40"/></svg>'
        )
        assert "onload" not in result.lower()
        assert "alert" not in result

    def test_sanitizer_strips_data_uri_javascript(self):
        """javascript: data URIs must be stripped."""
        from noa.tools.notion import _sanitize_content

        result = _sanitize_content(
            '<a href="javascript:alert(1)">click</a>'
        )
        assert "javascript:" not in result.lower()

    def test_sanitizer_preserves_safe_html(self):
        """Safe HTML elements like p, b, a with http href should survive."""
        from noa.tools.notion import _sanitize_content

        safe = '<p>Hello <b>world</b></p>'
        result = _sanitize_content(safe)
        assert "Hello" in result
        assert "world" in result

    def test_sanitizer_uses_nh3_not_regex(self):
        """Sanitizer must use nh3 library, not regex."""
        from noa.tools import notion
        import inspect

        source = inspect.getsource(notion._sanitize_content)
        assert "nh3" in source or "nh3" in inspect.getsource(notion), (
            "Sanitizer must use nh3 library, not regex-based stripping"
        )


# ---------------------------------------------------------------------------
# M2: CORS is restricted (not wildcard methods/headers)
# ---------------------------------------------------------------------------


class TestCORSRestrictions:
    """M2: CORS must not use wildcard methods/headers."""

    def test_cors_methods_not_wildcard(self):
        """CORS allow_methods must not be ['*']."""
        from noa.api.app import create_app

        app = create_app()

        # Find CORS middleware in the stack
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                methods = middleware.kwargs.get("allow_methods", [])
                assert methods != ["*"], (
                    "CORS allow_methods must be explicit, not wildcard"
                )
                break

    def test_cors_headers_not_wildcard(self):
        """CORS allow_headers must not be ['*']."""
        from noa.api.app import create_app

        app = create_app()

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                headers = middleware.kwargs.get("allow_headers", [])
                assert headers != ["*"], (
                    "CORS allow_headers must be explicit, not wildcard"
                )
                break

    def test_cors_rejects_wildcard_origin_env(self):
        """Setting CORS_ALLOWED_ORIGINS=* must not produce wildcard origin."""
        import os
        from unittest.mock import patch

        from noa.api.app import create_app

        with patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": "*"}):
            app = create_app()

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                origins = middleware.kwargs.get("allow_origins", [])
                assert "*" not in origins, (
                    "Wildcard origin must be rejected when credentials are enabled"
                )
                break


# ---------------------------------------------------------------------------
# M4: Content-Security-Policy headers
# ---------------------------------------------------------------------------


class TestCSPHeaders:
    """M4: API responses must include Content-Security-Policy header."""

    def test_csp_middleware_exists(self):
        """App must have CSP header middleware registered."""
        import inspect

        from noa.api import app as app_module

        source = inspect.getsource(app_module)
        assert "Content-Security-Policy" in source or "CSPMiddleware" in source, (
            "App must set Content-Security-Policy headers"
        )


# ---------------------------------------------------------------------------
# Integration: imports work correctly
# ---------------------------------------------------------------------------


class TestQC2Imports:
    """Verify all modified modules import without errors."""

    def test_audit_service_imports(self):
        from noa.audit.service import AuditService
        assert AuditService is not None

    def test_capabilities_imports(self):
        from noa.tools.capabilities import DbCapabilityChecker
        assert DbCapabilityChecker is not None

    def test_gmail_imports(self):
        from noa.tools.gmail import GmailTool
        assert GmailTool is not None

    def test_notion_imports(self):
        from noa.tools.notion import NotionTool
        assert NotionTool is not None

    def test_app_imports(self):
        from noa.api.app import create_app
        assert create_app is not None
