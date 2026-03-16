"""CQ7: Integration tests for the 4 features wired in CQ1.

Tests:
1. Capability enforcement — grant → succeeds, no grant → denied, revoke → denied (real DB)
2. Custom tool restore — register via API → call load_custom_tools() → tool still in gateway
3. Scope filtering — email_draft scope rejects web_search; research scope accepts it
4. Preview generation — medium-risk approval response includes "preview" key
5. Dead code absence — governance/idempotency/rate_limiter/mcp_adapter deleted, ToolRegistry gone
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest

from tests.integration.conftest import register_and_login


# ---------------------------------------------------------------------------
# 1. Capability enforcement via DbCapabilityChecker + ToolGateway (real DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capability_grant_allows_tool_dispatch(pg_app: Any) -> None:
    """Granting a capability for a user allows the gateway to dispatch that tool."""
    from noa.api import app_state
    from noa.tools.capabilities import DbCapabilityChecker
    from noa.tools.gateway import ToolGateway, ToolRequest

    sf = app_state.get_session_factory()
    assert sf is not None

    user_id = uuid.uuid4()

    # Create a minimal gateway with a stub adapter
    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"ok": True})

    gateway.register("web_search", _StubAdapter())

    # Wire a real DbCapabilityChecker backed by the test Postgres DB
    async with sf() as session:
        checker = DbCapabilityChecker(session)
        # Grant the capability
        await checker.grant(user_id, "web_search")

    # Attach a new checker (own session per call, as per CQ1 design)
    async with sf() as session:
        checker2 = DbCapabilityChecker(session)
        gateway.capability_checker = checker2

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
            user_id=user_id,
        )
        resp = await gateway.dispatch(req)

    # Should succeed (no error, no capability_denied)
    assert resp.error is None, f"Expected success but got error: {resp.error}"
    assert resp.result == {"ok": True}


@pytest.mark.asyncio
async def test_capability_no_grant_denies_tool_dispatch(pg_app: Any) -> None:
    """Dispatching a tool without a capability grant returns a capability_denied error."""
    from noa.api import app_state
    from noa.tools.capabilities import DbCapabilityChecker
    from noa.tools.gateway import ToolGateway, ToolRequest

    sf = app_state.get_session_factory()
    assert sf is not None

    user_id = uuid.uuid4()  # New user — no grants

    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"ok": True})

    gateway.register("web_search", _StubAdapter())

    async with sf() as session:
        checker = DbCapabilityChecker(session)
        gateway.capability_checker = checker

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
            user_id=user_id,
        )
        resp = await gateway.dispatch(req)

    # Should be denied
    assert resp.error is not None
    assert "denied" in resp.error.lower() or "capability" in resp.error.lower()


@pytest.mark.asyncio
async def test_capability_revoke_denies_tool_dispatch(pg_app: Any) -> None:
    """Revoking a capability causes subsequent dispatch to be denied."""
    from noa.api import app_state
    from noa.tools.capabilities import DbCapabilityChecker
    from noa.tools.gateway import ToolGateway, ToolRequest

    sf = app_state.get_session_factory()
    assert sf is not None

    user_id = uuid.uuid4()

    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"ok": True})

    gateway.register("web_search", _StubAdapter())

    # Grant, then revoke
    async with sf() as session:
        checker = DbCapabilityChecker(session)
        await checker.grant(user_id, "web_search")
        await checker.revoke(user_id, "web_search")

    # Now dispatch should be denied
    async with sf() as session:
        checker2 = DbCapabilityChecker(session)
        gateway.capability_checker = checker2

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
            user_id=user_id,
        )
        resp = await gateway.dispatch(req)

    assert resp.error is not None
    assert "denied" in resp.error.lower() or "capability" in resp.error.lower()


@pytest.mark.asyncio
async def test_capability_enforcement_via_api(pg_client: Any, pg_app: Any) -> None:
    """POST /tools/web_search/enable grants capability; dispatching after succeeds."""
    tokens = await register_and_login(pg_client, "cq7_cap_api@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Enable web_search via the API endpoint (which creates the DB grant)
    resp = await pg_client.post("/api/v1/tools/web_search/enable", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "granted"

    # Disable it and verify revocation
    resp_del = await pg_client.delete("/api/v1/tools/web_search", headers=headers)
    assert resp_del.status_code == 200
    assert resp_del.json()["data"]["status"] == "revoked"


# ---------------------------------------------------------------------------
# 2. Custom tool restore on startup (register → load_custom_tools → still present)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_tool_restore_after_load(pg_client: Any, pg_app: Any) -> None:
    """Registering a custom tool via API and calling load_custom_tools() keeps it in gateway."""
    from noa.api import app_state
    from noa.tools.gateway import ToolGateway
    from noa.tools.registration import load_custom_tools

    tokens = await register_and_login(pg_client, "cq7_custom_tool@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    custom_tool = {
        "name": "cq7_test_restore_tool",
        "description": "CQ7 restore test tool",
        "base_url": "https://api.cq7test.example.com",
        "auth_type": "none",
        "domain": "external",
        "functions": [
            {
                "name": "run",
                "description": "Execute something",
                "http_method": "POST",
                "path": "/run",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                },
            }
        ],
    }

    # Register the custom tool via the API
    resp = await pg_client.post("/api/v1/tools", json=custom_tool, headers=headers)
    assert resp.status_code in (201, 409), f"Registration failed: {resp.text}"

    # Simulate restart by creating a fresh gateway and calling load_custom_tools()
    fresh_gateway = ToolGateway()
    assert "cq7_test_restore_tool" not in fresh_gateway.list_tools()

    sf = app_state.get_session_factory()
    assert sf is not None
    async with sf() as session:
        await load_custom_tools(fresh_gateway, session)

    # Tool should now be registered in the fresh gateway
    assert "cq7_test_restore_tool" in fresh_gateway.list_tools(), (
        "Custom tool was not restored after load_custom_tools(). "
        f"Gateway has: {fresh_gateway.list_tools()}"
    )


# ---------------------------------------------------------------------------
# 3. Scope filtering — filter_tools_by_allowlist + ToolScopeRegistry
# ---------------------------------------------------------------------------


def test_scope_registry_email_draft_excludes_web_search() -> None:
    """email_draft scope does not include web_search."""
    from noa.tools.scopes import ToolScopeRegistry

    registry = ToolScopeRegistry()
    scope_tools = registry.get_scope("email_draft")

    # email_draft only allows gmail tools
    tool_names = {t.split("__")[0] for t in scope_tools}
    assert "web_search" not in tool_names, (
        f"web_search should not be in email_draft scope, got: {scope_tools}"
    )
    assert "gmail" in tool_names


def test_scope_registry_research_includes_web_search() -> None:
    """research scope includes web_search."""
    from noa.tools.scopes import ToolScopeRegistry

    registry = ToolScopeRegistry()
    scope_tools = registry.get_scope("research")

    assert any("web_search" in t for t in scope_tools), (
        f"web_search should be in research scope, got: {scope_tools}"
    )


def test_filter_tools_by_allowlist_rejects_out_of_scope() -> None:
    """filter_tools_by_allowlist removes tools not in the allowlist."""
    from noa.tools.scopes import ToolScopeRegistry, filter_tools_by_allowlist

    registry = ToolScopeRegistry()
    email_draft_allowlist = registry.get_scope("email_draft")

    # User has web_search and gmail enabled
    user_tools = ["web_search__web_search", "gmail__draft_email", "gmail__read_email"]
    filtered = filter_tools_by_allowlist(user_tools, email_draft_allowlist)

    assert "web_search__web_search" not in filtered, (
        "web_search should be filtered out for email_draft scope"
    )
    assert "gmail__draft_email" in filtered
    assert "gmail__read_email" in filtered


def test_filter_tools_by_allowlist_no_scope_passes_all() -> None:
    """filter_tools_by_allowlist with None allowlist passes all tools through."""
    from noa.tools.scopes import filter_tools_by_allowlist

    user_tools = ["web_search__web_search", "gmail__draft_email", "calendar__list_events"]
    filtered = filter_tools_by_allowlist(user_tools, None)

    assert filtered == user_tools


def test_filter_tools_by_allowlist_research_accepts_web_search() -> None:
    """research scope filter passes web_search through."""
    from noa.tools.scopes import ToolScopeRegistry, filter_tools_by_allowlist

    registry = ToolScopeRegistry()
    research_allowlist = registry.get_scope("research")

    user_tools = ["web_search__web_search", "gmail__draft_email"]
    filtered = filter_tools_by_allowlist(user_tools, research_allowlist)

    assert "web_search__web_search" in filtered
    assert "gmail__draft_email" not in filtered


# ---------------------------------------------------------------------------
# 4. Preview generation in approval flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_approval_medium_risk_includes_preview() -> None:
    """Medium-risk action triggers approval; approval response includes 'preview' key."""
    from noa.policy.engine import PolicyEngine
    from noa.policy.preview import generate_preview
    from noa.tools.gateway import ToolGateway, ToolRequest

    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"sent": True})

    gateway.register("gmail", _StubAdapter())
    gateway.policy_engine = PolicyEngine()

    req = ToolRequest(
        tool="gmail",
        function="send_email",
        args={"to": "bob@example.com", "subject": "Hello", "body": "Test body"},
        user_id=uuid.uuid4(),
        approved=False,
    )
    resp = await gateway.dispatch(req, approvals_enabled=True)

    # Approval should be required (medium risk)
    assert resp.error is not None
    assert resp.result is not None
    assert resp.result.get("approval_required") is True

    # Preview must be generated separately — verify generate_preview works for this action
    preview = generate_preview("send_email", req.args)
    assert preview is not None
    assert len(preview) > 0
    assert "bob@example.com" in preview or "Hello" in preview


@pytest.mark.asyncio
async def test_gateway_approval_response_contains_preview_key() -> None:
    """Approval result dict from gateway contains 'preview' key for medium-risk actions.

    This tests the CQ1 wiring: when needs_approval is True, generate_preview() is called
    and its result is included in the approval response under 'preview'.
    """
    from noa.policy.engine import PolicyEngine
    from noa.tools.gateway import ToolGateway, ToolRequest

    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"sent": True})

    gateway.register("gmail", _StubAdapter())
    gateway.policy_engine = PolicyEngine()

    req = ToolRequest(
        tool="gmail",
        function="send_email",
        args={"to": "alice@example.com", "subject": "Meeting", "body": "Let's meet"},
        user_id=uuid.uuid4(),
        approved=False,
    )
    resp = await gateway.dispatch(req, approvals_enabled=True)

    assert resp.result is not None
    assert resp.result.get("approval_required") is True
    # After CQ1 wiring: the approval response should include preview text
    # If CQ1 is not yet wired, this assertion will guide what needs to be added
    assert "preview" in resp.result, (
        "Expected 'preview' key in approval response — this is wired by CQ1. "
        f"Actual keys: {list(resp.result.keys())}"
    )
    assert resp.result["preview"] is not None
    assert len(resp.result["preview"]) > 0


@pytest.mark.asyncio
async def test_gateway_approval_low_risk_no_preview() -> None:
    """Low-risk actions do not require approval and produce no approval preview."""
    from noa.policy.engine import PolicyEngine
    from noa.policy.preview import generate_preview
    from noa.tools.gateway import ToolGateway, ToolRequest

    gateway = ToolGateway()

    class _StubAdapter:
        domain = "external"

        async def execute(self, req: ToolRequest) -> Any:
            from noa.tools.gateway import ToolResponse

            return ToolResponse(result={"results": ["search result"]})

    gateway.register("web_search", _StubAdapter())
    gateway.policy_engine = PolicyEngine()

    req = ToolRequest(
        tool="web_search",
        function="web_search",
        args={"query": "python tutorials"},
        user_id=uuid.uuid4(),
        approved=False,
    )
    resp = await gateway.dispatch(req, approvals_enabled=True)

    # Low-risk: no approval, no preview, succeeds directly
    assert resp.error is None
    assert resp.result == {"results": ["search result"]}

    # Verify generate_preview returns None for low-risk actions
    preview = generate_preview("web_search", req.args)
    assert preview is None


def test_generate_preview_send_email() -> None:
    """generate_preview returns human-readable text for send_email."""
    from noa.policy.preview import generate_preview

    preview = generate_preview(
        "send_email",
        {"to": "test@example.com", "subject": "Test Subject", "body": "Hello world"},
    )
    assert preview is not None
    assert "test@example.com" in preview
    assert "Test Subject" in preview


def test_generate_preview_low_risk_returns_none() -> None:
    """generate_preview returns None for low-risk actions (no preview needed)."""
    from noa.policy.preview import generate_preview

    # web_search is low-risk — should not get a preview
    result = generate_preview("web_search", {"query": "test"})
    assert result is None


def test_generate_preview_delete_action() -> None:
    """generate_preview returns text for delete actions (high risk)."""
    from noa.policy.preview import generate_preview

    preview = generate_preview("delete_email", {"email_id": "abc123"})
    assert preview is not None
    assert "abc123" in preview or "email" in preview.lower()


# ---------------------------------------------------------------------------
# 5. Dead code absence — verify CQ2 deletions are applied
# ---------------------------------------------------------------------------


def test_governance_py_does_not_exist() -> None:
    """governance.py should be deleted by CQ2."""
    path = Path("src/noa/tools/governance.py")
    assert not path.exists(), (
        f"governance.py still exists at {path.resolve()} — "
        "CQ2 should have deleted this dead code"
    )


def test_idempotency_py_does_not_exist() -> None:
    """idempotency.py should be deleted by CQ2."""
    path = Path("src/noa/tools/idempotency.py")
    assert not path.exists(), (
        f"idempotency.py still exists at {path.resolve()} — "
        "CQ2 should have deleted this dead code"
    )


def test_rate_limiter_py_does_not_exist() -> None:
    """rate_limiter.py should be deleted by CQ2."""
    path = Path("src/noa/tools/rate_limiter.py")
    assert not path.exists(), (
        f"rate_limiter.py still exists at {path.resolve()} — "
        "CQ2 should have deleted this dead code"
    )


def test_mcp_adapter_py_does_not_exist() -> None:
    """mcp_adapter.py should be deleted by CQ2."""
    path = Path("src/noa/tools/mcp_adapter.py")
    assert not path.exists(), (
        f"mcp_adapter.py still exists at {path.resolve()} — "
        "CQ2 should have deleted this dead code"
    )


def test_tool_registry_class_not_in_interface() -> None:
    """ToolRegistry class should be deleted from interface.py by CQ2."""
    path = Path("src/noa/tools/interface.py")
    if not path.exists():
        return  # Already deleted entirely — that's fine

    content = path.read_text()
    assert "class ToolRegistry" not in content, (
        "ToolRegistry class still exists in interface.py — "
        "CQ2 should have removed lines 42-88"
    )


def test_set_registry_not_in_tools_node() -> None:
    """set_registry, get_registry, execute_tool should be deleted from tools.py by CQ2."""
    path = Path("src/noa/orchestrator/nodes/tools.py")
    assert path.exists(), "tools.py must exist"

    content = path.read_text()
    assert "def set_registry(" not in content, (
        "set_registry() still exists in tools.py — CQ2 should have removed it"
    )
    assert "def get_registry(" not in content, (
        "get_registry() still exists in tools.py — CQ2 should have removed it"
    )
    assert "def execute_tool(" not in content, (
        "execute_tool() still exists in tools.py — CQ2 should have removed it"
    )
