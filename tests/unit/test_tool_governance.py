"""Tests for TI6: Tool Governance (Idempotency, Rate Limits, Previews).

Covers: idempotency key dedup, per-tool rate limiting, dry-run preview
generation, Idempotency-Key header support, GovernanceWrapper.

Spec refs: SPEC.md §19.1, §19.2, §19.3, §25.4
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti6


# ---------------------------------------------------------------------------
# Idempotency per §19.1
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Tests for idempotency key enforcement per §19.1."""

    def test_store_and_retrieve_result(self):
        """Idempotency store must cache results by key.

        SPEC.md §19.1 — De-duplicate by idempotency_key.
        """
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore()
        store.set("key-1", {"status": "sent", "id": "msg-1"})

        result = store.get("key-1")
        assert result == {"status": "sent", "id": "msg-1"}

    def test_duplicate_key_returns_cached(self):
        """Duplicate idempotency key must return previous result.

        SPEC.md §19.1 — Return previous result without re-executing.
        """
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore()
        store.set("key-1", {"status": "sent"})

        # Second set with same key should not overwrite
        assert store.get("key-1") == {"status": "sent"}

    def test_unknown_key_returns_none(self):
        """Unknown idempotency key must return None.

        SPEC.md §19.1 — Only cached keys return results.
        """
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore()
        assert store.get("unknown") is None

    def test_expiry_after_ttl(self):
        """Idempotency keys must expire after TTL.

        SPEC.md §25.4 — De-duplicate within 24 hours.
        """
        from noa.tools.idempotency import IdempotencyStore

        store = IdempotencyStore(ttl_seconds=1)
        store.set("key-1", {"status": "sent"})
        assert store.get("key-1") is not None

        # Simulate time passing
        store._entries["key-1"]["expires_at"] = time.monotonic() - 1
        assert store.get("key-1") is None


# ---------------------------------------------------------------------------
# Rate Limiting per §19.3
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Tests for per-tool rate limiting per §19.3."""

    def test_send_email_limit_10_per_hour(self):
        """send_email must be blocked after 10/hour.

        SPEC.md §19.3 — send_email: 10/hour.
        """
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(10):
            assert limiter.check("send_email") is True

        assert limiter.check("send_email") is False

    def test_create_event_limit_20_per_hour(self):
        """create_event must be blocked after 20/hour.

        SPEC.md §19.3 — create_event: 20/hour.
        """
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(20):
            assert limiter.check("create_event") is True

        assert limiter.check("create_event") is False

    def test_create_page_limit_20_per_hour(self):
        """create_page must be blocked after 20/hour.

        SPEC.md §19.3 — create_page: 20/hour.
        """
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(20):
            assert limiter.check("create_page") is True

        assert limiter.check("create_page") is False

    def test_web_search_limit_30_per_hour(self):
        """web_search must be blocked after 30/hour.

        SPEC.md §19.3 — web_search: 30/hour.
        """
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(30):
            assert limiter.check("web_search") is True

        assert limiter.check("web_search") is False

    def test_unlimited_action_always_allowed(self):
        """Actions without rate limits must always be allowed.

        SPEC.md §19.3 — Only listed actions are rate-limited.
        """
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(100):
            assert limiter.check("list_events") is True

    def test_rate_limit_resets_after_window(self):
        """Rate limits must reset after the window expires."""
        from noa.tools.rate_limiter import RateLimiter

        limiter = RateLimiter()

        for _ in range(10):
            limiter.check("send_email")

        assert limiter.check("send_email") is False

        # Simulate window expiry by shifting all timestamps back
        from collections import deque as _deque
        old_ts = time.monotonic() - 3601
        limiter._timestamps["send_email"] = _deque([old_ts] * 10)
        assert limiter.check("send_email") is True


# ---------------------------------------------------------------------------
# Dry-Run Previews per §19.2
# ---------------------------------------------------------------------------


class TestDryRunPreviews:
    """Tests for dry-run preview generation per §19.2."""

    def test_preview_generated_for_send_email(self):
        """send_email must generate a preview before execution.

        SPEC.md §19.2 — All send actions show a preview.
        """
        from noa.tools.governance import generate_preview

        preview = generate_preview(
            tool_name="gmail",
            function="send_email",
            args={
                "to": "bob@example.com",
                "subject": "Hello",
                "body": "Hi Bob!",
            },
        )

        assert preview["action"] == "send_email"
        assert "bob@example.com" in preview["summary"]
        assert preview["requires_confirmation"] is True

    def test_preview_generated_for_create_event(self):
        """create_event must generate a preview before execution.

        SPEC.md §19.2 — All create actions show a preview.
        """
        from noa.tools.governance import generate_preview

        preview = generate_preview(
            tool_name="calendar",
            function="create_event",
            args={
                "title": "Team standup",
                "start": "2026-03-06T10:00:00Z",
                "end": "2026-03-06T11:00:00Z",
            },
        )

        assert preview["action"] == "create_event"
        assert "Team standup" in preview["summary"]
        assert preview["requires_confirmation"] is True

    def test_preview_not_required_for_low_risk(self):
        """Low-risk actions must not require preview.

        SPEC.md §19.2 — Only Medium-risk actions require preview.
        """
        from noa.tools.governance import generate_preview

        preview = generate_preview(
            tool_name="calendar",
            function="list_events",
            args={"start_date": "2026-03-05"},
        )

        assert preview["requires_confirmation"] is False

    def test_preview_includes_diff_summary(self):
        """Preview must include a diff-like summary.

        SPEC.md §19.2 — Preview includes diff-like summary.
        """
        from noa.tools.governance import generate_preview

        preview = generate_preview(
            tool_name="notion",
            function="create_page",
            args={
                "parent_id": "parent-123",
                "title": "New Page",
                "content": "# Hello World",
            },
        )

        assert "summary" in preview
        assert len(preview["summary"]) > 0


# ---------------------------------------------------------------------------
# GovernanceWrapper
# ---------------------------------------------------------------------------


class TestGovernanceWrapper:
    """Tests for the GovernanceWrapper that wraps ToolInterface."""

    @pytest.mark.asyncio
    async def test_governance_wraps_tool_transparently(self):
        """GovernanceWrapper must wrap ToolInterface transparently.

        MASTER_PLAN TI6 — GovernanceWrapper wraps ToolInterface.
        """
        from noa.tools.governance import GovernanceWrapper

        mock_tool = AsyncMock()
        mock_tool.name = "calendar"
        mock_tool.domain = "external"
        mock_tool.risk_tiers = {"list_events": "low"}
        mock_tool.execute.return_value = {"events": []}

        wrapper = GovernanceWrapper(tool=mock_tool)
        result = await wrapper.execute(
            function="list_events", args={"start": "2026-03-05"},
        )

        mock_tool.execute.assert_called_once()
        assert result == {"events": []}

    @pytest.mark.asyncio
    async def test_governance_blocks_rate_limited(self):
        """GovernanceWrapper must block rate-limited actions.

        SPEC.md §19.3 — Block + notify on exceed.
        """
        from noa.tools.governance import GovernanceWrapper, RateLimitError

        mock_tool = AsyncMock()
        mock_tool.name = "gmail"
        mock_tool.domain = "external"
        mock_tool.risk_tiers = {"send_email": "medium"}
        mock_tool.execute.return_value = {"status": "sent"}

        wrapper = GovernanceWrapper(tool=mock_tool)

        # Exhaust rate limit
        for _ in range(10):
            await wrapper.execute(
                function="send_email",
                args={"to": "x@x.com", "subject": "Hi", "body": "Hi"},
            )

        with pytest.raises(RateLimitError, match="send_email"):
            await wrapper.execute(
                function="send_email",
                args={"to": "x@x.com", "subject": "Hi", "body": "Hi"},
            )

    @pytest.mark.asyncio
    async def test_governance_deduplicates_by_idempotency_key(self):
        """GovernanceWrapper must deduplicate by idempotency_key.

        SPEC.md §19.1 — Return previous result without re-executing.
        """
        from noa.tools.governance import GovernanceWrapper

        mock_tool = AsyncMock()
        mock_tool.name = "gmail"
        mock_tool.domain = "external"
        mock_tool.risk_tiers = {"send_email": "medium"}
        mock_tool.execute.return_value = {"status": "sent", "id": "msg-1"}

        wrapper = GovernanceWrapper(tool=mock_tool)

        # First call
        result1 = await wrapper.execute(
            function="send_email",
            args={"to": "x@x.com", "subject": "Hi", "body": "Hi"},
            idempotency_key="key-1",
        )

        # Second call with same key — should NOT re-execute
        result2 = await wrapper.execute(
            function="send_email",
            args={"to": "x@x.com", "subject": "Hi", "body": "Hi"},
            idempotency_key="key-1",
        )

        assert mock_tool.execute.call_count == 1
        assert result1 == result2


# ---------------------------------------------------------------------------
# Idempotency-Key header per §25.4
# ---------------------------------------------------------------------------


class TestIdempotencyKeyHeader:
    """Tests for Idempotency-Key header support per §25.4."""

    def test_idempotency_middleware_extracts_key(self):
        """Middleware must extract Idempotency-Key from request headers.

        SPEC.md §25.4 — Write endpoints accept Idempotency-Key header.
        """
        from noa.api.middleware import extract_idempotency_key

        key = extract_idempotency_key({"Idempotency-Key": "abc-123"})
        assert key == "abc-123"

    def test_idempotency_middleware_returns_none_without_header(self):
        """Missing Idempotency-Key header must return None."""
        from noa.api.middleware import extract_idempotency_key

        key = extract_idempotency_key({})
        assert key is None

    def test_idempotency_middleware_extracts_lowercase_key(self):
        """Starlette normalises headers to lowercase — must still find the key.

        RFC 7230: HTTP headers are case-insensitive.
        """
        from noa.api.middleware import extract_idempotency_key

        key = extract_idempotency_key({"idempotency-key": "low-123"})
        assert key == "low-123"

    def test_idempotency_middleware_extracts_mixed_case_key(self):
        """Arbitrary casing must still work per RFC 7230."""
        from noa.api.middleware import extract_idempotency_key

        key = extract_idempotency_key({"IDEMPOTENCY-KEY": "upper-456"})
        assert key == "upper-456"
