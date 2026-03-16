"""Tests for CQ1: Wire Unwired Features.

Spec refs: SPEC.md §2.1 (tool allowlists), §19.2 (dry-run previews),
           §21 (risk tiers), §12 (extensible tools)

Covers:
1. DbCapabilityChecker refactored to accept session_factory
2. Gateway with DbCapabilityChecker wired: grant → allow, no grant → deny
3. load_custom_tools called at startup registers custom tools in gateway
4. ToolScopeRegistry scope filtering in tool_node
5. generate_preview wired into approval flow for medium/high risk
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.cq1


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class _FakeAdapter:
    """Tool adapter that records calls and returns a fixed result."""

    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self._result = result or {"ok": True}
        self.calls: list[Any] = []

    async def execute(self, request: Any) -> Any:
        from noa.tools.gateway import ToolResponse
        self.calls.append(request)
        return ToolResponse(result=self._result, provider="fake")


def _make_gateway() -> Any:
    from noa.tools.gateway import ToolGateway
    return ToolGateway()


# ===========================================================================
# 1. DbCapabilityChecker — session_factory path
# ===========================================================================

class TestDbCapabilityCheckerSessionFactory:
    """DbCapabilityChecker opens its own session per call when given a factory."""

    def test_init_with_session_factory_only(self) -> None:
        """DbCapabilityChecker can be constructed with session_factory kwarg."""
        from noa.tools.capabilities import DbCapabilityChecker
        mock_factory = MagicMock()
        checker = DbCapabilityChecker(session_factory=mock_factory)
        assert checker._session_factory is mock_factory
        assert checker._session is None

    def test_init_with_positional_session_still_works(self) -> None:
        """Positional session argument still works (backward compat for API endpoints)."""
        from noa.tools.capabilities import DbCapabilityChecker
        mock_session = MagicMock()
        checker = DbCapabilityChecker(mock_session)
        assert checker._session is mock_session
        assert checker._session_factory is None

    def test_init_with_neither_raises_runtime_error_on_use(self) -> None:
        """DbCapabilityChecker with no args raises RuntimeError when used."""
        from noa.tools.capabilities import DbCapabilityChecker
        checker = DbCapabilityChecker()

        async def _call() -> None:
            await checker.has_capability(uuid.uuid4(), "web_search")

        with pytest.raises(RuntimeError, match="session|session_factory"):
            asyncio.run(_call())

    def test_has_capability_uses_factory_per_call(self) -> None:
        """has_capability opens a new session via the factory each time."""
        from contextlib import asynccontextmanager

        from noa.tools.capabilities import DbCapabilityChecker

        call_count = 0

        @asynccontextmanager
        async def _factory():
            nonlocal call_count
            call_count += 1
            mock_session = AsyncMock()
            # Return empty result (no capability granted)
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        checker = DbCapabilityChecker(session_factory=_factory)

        async def _run() -> None:
            uid = uuid.uuid4()
            await checker.has_capability(uid, "web_search")
            await checker.has_capability(uid, "web_search")

        asyncio.run(_run())
        # Each has_capability call should open a new session
        assert call_count == 2

    def test_has_capability_returns_false_when_not_granted(self) -> None:
        """has_capability returns False when no DB row exists."""
        from contextlib import asynccontextmanager

        from noa.tools.capabilities import DbCapabilityChecker

        @asynccontextmanager
        async def _factory():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        checker = DbCapabilityChecker(session_factory=_factory)

        result = asyncio.run(
            checker.has_capability(uuid.uuid4(), "web_search")
        )
        assert result is False

    def test_has_capability_returns_true_when_granted(self) -> None:
        """has_capability returns True when a matching DB row exists."""
        from contextlib import asynccontextmanager

        from noa.db.models.tool_capability import ToolCapability
        from noa.tools.capabilities import DbCapabilityChecker

        fake_row = ToolCapability(
            user_id=uuid.uuid4(),
            tool_name="web_search",
            capability="search.read",
        )

        @asynccontextmanager
        async def _factory():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = fake_row
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        checker = DbCapabilityChecker(session_factory=_factory)

        result = asyncio.run(
            checker.has_capability(uuid.uuid4(), "web_search")
        )
        assert result is True

    def test_unknown_tool_returns_false_without_querying_db(self) -> None:
        """has_capability returns False for tools not in TOOL_CAPABILITIES."""
        from contextlib import asynccontextmanager

        from noa.tools.capabilities import DbCapabilityChecker

        execute_called = False

        @asynccontextmanager
        async def _factory():
            mock_session = AsyncMock()

            async def _exec(*args: Any, **kwargs: Any) -> Any:
                nonlocal execute_called
                execute_called = True
                return MagicMock()

            mock_session.execute = _exec
            yield mock_session

        checker = DbCapabilityChecker(session_factory=_factory)
        result = asyncio.run(
            checker.has_capability(uuid.uuid4(), "nonexistent_tool_xyz")
        )
        assert result is False
        # DB should not be queried for unknown tools
        assert not execute_called


# ===========================================================================
# 2. Gateway + DbCapabilityChecker end-to-end
# ===========================================================================

class TestGatewayWithDbCapabilityChecker:
    """Gateway enforces capability checks via DbCapabilityChecker."""

    def _make_checker_granting(self, granted: bool) -> Any:
        """Build a DbCapabilityChecker that always returns the given bool."""
        from contextlib import asynccontextmanager
        from noa.tools.capabilities import DbCapabilityChecker

        @asynccontextmanager
        async def _factory():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            row = MagicMock() if granted else None
            mock_result.scalars.return_value.first.return_value = row
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        return DbCapabilityChecker(session_factory=_factory)

    def test_dispatch_blocked_when_capability_denied(self) -> None:
        """Gateway returns capability_denied error when checker returns False."""
        from noa.tools.gateway import ToolRequest

        gw = _make_gateway()
        adapter = _FakeAdapter()
        gw.register("web_search", adapter)
        gw.capability_checker = self._make_checker_granting(False)

        req = ToolRequest(
            tool="web_search", function="web_search",
            args={"query": "hello"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is not None
        assert "capability" in resp.error.lower() or "denied" in resp.error.lower()
        assert len(adapter.calls) == 0

    def test_dispatch_allowed_when_capability_granted(self) -> None:
        """Gateway passes through when checker returns True."""
        from noa.tools.gateway import ToolRequest

        gw = _make_gateway()
        adapter = _FakeAdapter()
        gw.register("web_search", adapter)
        gw.capability_checker = self._make_checker_granting(True)

        req = ToolRequest(
            tool="web_search", function="web_search",
            args={"query": "hello"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert len(adapter.calls) == 1

    def test_dispatch_skips_capability_check_when_user_id_none(self) -> None:
        """When user_id is None, capability check is skipped (backward compat)."""
        from noa.tools.gateway import ToolRequest

        gw = _make_gateway()
        adapter = _FakeAdapter()
        gw.register("web_search", adapter)
        # Checker that would deny if called
        gw.capability_checker = self._make_checker_granting(False)

        req = ToolRequest(
            tool="web_search", function="web_search",
            args={"query": "hello"},
            # No user_id
        )
        resp = asyncio.run(gw.dispatch(req))
        # Should succeed because user_id is None
        assert resp.error is None
        assert len(adapter.calls) == 1


# ===========================================================================
# 3. load_custom_tools at startup
# ===========================================================================

class TestLoadCustomToolsAtStartup:
    """load_custom_tools loads DB rows and registers them in the gateway."""

    def test_load_custom_tools_registers_adapters(self) -> None:
        """load_custom_tools registers HttpToolAdapters for each DB row."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import load_custom_tools

        gw = ToolGateway()
        initial_tools = set(gw.list_tools())

        # Build fake DB rows
        custom_tool = MagicMock()
        custom_tool.name = "my_custom_api"
        custom_tool.base_url = "https://api.example.com"
        custom_tool.auth_type = "bearer"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [custom_tool]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        asyncio.run(load_custom_tools(gw, mock_session))

        after_tools = set(gw.list_tools())
        assert "my_custom_api" in after_tools
        assert "my_custom_api" not in initial_tools

    def test_load_custom_tools_empty_db(self) -> None:
        """load_custom_tools with empty DB registers nothing."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import load_custom_tools

        gw = ToolGateway()
        initial_tools = set(gw.list_tools())

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        asyncio.run(load_custom_tools(gw, mock_session))

        assert set(gw.list_tools()) == initial_tools

    def test_load_custom_tools_multiple_tools(self) -> None:
        """load_custom_tools handles multiple custom tools from DB."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import load_custom_tools

        gw = ToolGateway()

        tools_data = [
            ("api_one", "https://api1.example.com", "bearer"),
            ("api_two", "https://api2.example.com", "api_key"),
        ]
        custom_tools = []
        for name, url, auth in tools_data:
            t = MagicMock()
            t.name = name
            t.base_url = url
            t.auth_type = auth
            custom_tools.append(t)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = custom_tools
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        asyncio.run(load_custom_tools(gw, mock_session))

        registered = set(gw.list_tools())
        assert "api_one" in registered
        assert "api_two" in registered


# ===========================================================================
# 4. ToolScopeRegistry scope filtering in tool_node
# ===========================================================================

class TestToolNodeScopeFiltering:
    """tool_node enforces scope restrictions when tool_scope is set in state."""

    def _run_tool_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run tool_node synchronously with the given state."""
        from noa.orchestrator.nodes.tools import tool_node
        return asyncio.run(tool_node(state))  # type: ignore[arg-type]

    def test_no_scope_allows_all_tools(self) -> None:
        """When tool_scope is None, all registered tools dispatch normally."""
        from noa.orchestrator.nodes.tools import set_gateway

        gw = _make_gateway()
        adapter = _FakeAdapter({"result": "found"})
        gw.register("web_search", adapter)
        set_gateway(gw)

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "web_search", "function": "web_search",
                            "args": {"query": "test"}}],
            "tool_rounds": 0,
            "messages": [],
            "tool_scope": None,
            "approvals_enabled": False,
            "user_id": None,
        }
        result = self._run_tool_node(state)
        results = result["tool_results"]
        assert len(results) == 1
        assert "error" not in results[0]

    def test_email_draft_scope_blocks_web_search(self) -> None:
        """email_draft scope blocks web_search calls."""
        from noa.orchestrator.nodes.tools import set_gateway

        gw = _make_gateway()
        ws_adapter = _FakeAdapter()
        gw.register("web_search", ws_adapter)
        set_gateway(gw)

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "web_search", "function": "web_search",
                            "args": {"query": "test"}}],
            "tool_rounds": 0,
            "messages": [],
            "tool_scope": "email_draft",
            "approvals_enabled": False,
            "user_id": None,
        }
        result = self._run_tool_node(state)
        results = result["tool_results"]
        assert len(results) == 1
        # web_search is not in email_draft scope
        assert "error" in results[0]
        assert "scope" in results[0]["error"].lower()

    def test_unknown_scope_blocks_all_tools(self) -> None:
        """An unknown scope name blocks all tool calls."""
        from noa.orchestrator.nodes.tools import set_gateway

        gw = _make_gateway()
        adapter = _FakeAdapter()
        gw.register("web_search", adapter)
        set_gateway(gw)

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "web_search", "function": "web_search",
                            "args": {"query": "test"}}],
            "tool_rounds": 0,
            "messages": [],
            "tool_scope": "nonexistent_scope_xyz",
            "approvals_enabled": False,
            "user_id": None,
        }
        result = self._run_tool_node(state)
        results = result["tool_results"]
        assert len(results) == 1
        assert "error" in results[0]

    def test_empty_tool_calls_with_scope_returns_empty(self) -> None:
        """Empty tool_calls returns empty results regardless of scope."""
        from noa.orchestrator.nodes.tools import set_gateway

        gw = _make_gateway()
        set_gateway(gw)

        state: dict[str, Any] = {
            "tool_calls": [],
            "tool_rounds": 0,
            "messages": [],
            "tool_scope": "email_draft",
            "approvals_enabled": False,
            "user_id": None,
        }
        result = self._run_tool_node(state)
        assert result["tool_results"] == []


# ===========================================================================
# 5. AgentState includes tool_scope field
# ===========================================================================

class TestAgentStateTotalScope:
    """AgentState TypedDict includes the tool_scope field."""

    def test_tool_scope_field_in_agent_state(self) -> None:
        """AgentState TypedDict has tool_scope key."""
        from noa.orchestrator.state import AgentState
        annotations = AgentState.__annotations__
        assert "tool_scope" in annotations

    def test_tool_scope_is_optional_str(self) -> None:
        """tool_scope annotation is str | None."""
        from noa.orchestrator.state import AgentState
        ann = AgentState.__annotations__["tool_scope"]
        # repr should contain str and None
        ann_str = str(ann)
        assert "str" in ann_str
        assert "None" in ann_str


# ===========================================================================
# 6. OrchestratorRunner passes tool_scope to initial state
# ===========================================================================

class TestRunnerPassesToolScope:
    """OrchestratorRunner.run() accepts and threads tool_scope into state."""

    def test_runner_run_accepts_tool_scope_kwarg(self) -> None:
        """OrchestratorRunner.run() has a tool_scope parameter."""
        import inspect
        from noa.orchestrator.runner import OrchestratorRunner
        sig = inspect.signature(OrchestratorRunner.run)
        assert "tool_scope" in sig.parameters

    def test_runner_tool_scope_default_is_none(self) -> None:
        """tool_scope defaults to None so existing callers are unaffected."""
        import inspect
        from noa.orchestrator.runner import OrchestratorRunner
        sig = inspect.signature(OrchestratorRunner.run)
        param = sig.parameters["tool_scope"]
        assert param.default is None


# ===========================================================================
# 7. Preview generation wired into approval flow
# ===========================================================================

class TestPreviewInApprovalFlow:
    """gateway.dispatch includes preview text for medium/high risk approvals."""

    def _make_policy_engine(self, risk: str = "medium") -> Any:
        """Build a PolicyEngine that classifies everything as the given tier."""
        engine = MagicMock()
        engine.classify = MagicMock(return_value=risk)
        engine.requires_approval = MagicMock(return_value=risk in ("medium", "high"))
        engine.requires_step_up_auth = MagicMock(return_value=risk == "high")
        engine.requires_preview = MagicMock(return_value=risk in ("medium", "high"))
        return engine

    def test_medium_risk_approval_includes_preview(self) -> None:
        """Medium risk dispatch returns preview text in approval_required result."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _FakeAdapter()
        gw.register("gmail", adapter)
        gw.policy_engine = self._make_policy_engine("medium")

        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={"to": "bob@example.com", "subject": "Hello", "body": "Hi Bob"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req, approvals_enabled=True))

        assert resp.result is not None
        assert resp.result.get("approval_required") is True
        assert "preview" in resp.result, (
            "Expected 'preview' key in approval_required result"
        )
        preview = resp.result["preview"]
        assert preview is not None
        assert "bob@example.com" in preview or "Hello" in preview

    def test_high_risk_approval_includes_preview(self) -> None:
        """High risk dispatch (before step-up) returns preview text."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _FakeAdapter()
        gw.register("gmail", adapter)
        gw.policy_engine = self._make_policy_engine("high")

        req = ToolRequest(
            tool="gmail",
            function="delete_email",
            args={"email_id": "msg-123"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req, approvals_enabled=True))

        assert resp.result is not None
        assert resp.result.get("approval_required") is True
        # High risk also requires preview
        assert "preview" in resp.result

    def test_low_risk_no_approval_no_preview(self) -> None:
        """Low risk dispatch executes without approval or preview."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _FakeAdapter({"results": [{"title": "Found"}]})
        gw.register("web_search", adapter)
        gw.policy_engine = self._make_policy_engine("low")

        req = ToolRequest(
            tool="web_search",
            function="web_search",
            args={"query": "test"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req, approvals_enabled=True))

        # Low risk: no approval, adapter is called, no preview
        assert resp.result is not None
        assert not resp.result.get("approval_required")
        assert len(adapter.calls) == 1

    def test_preview_omitted_when_action_not_previewable(self) -> None:
        """Approval result for non-previewable medium action has no preview key."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _FakeAdapter()
        gw.register("calendar", adapter)

        # Engine that classifies as medium but the action is not in _PREVIEW_ACTIONS
        engine = MagicMock()
        engine.classify = MagicMock(return_value="medium")
        engine.requires_approval = MagicMock(return_value=True)
        engine.requires_step_up_auth = MagicMock(return_value=False)
        engine.requires_preview = MagicMock(return_value=True)
        gw.policy_engine = engine

        req = ToolRequest(
            tool="calendar",
            function="some_unpreviewable_action",
            args={"x": 1},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req, approvals_enabled=True))

        assert resp.result is not None
        assert resp.result.get("approval_required") is True
        # preview key either absent or None (generate_preview returned None for
        # actions not in _PREVIEW_ACTIONS)
        preview = resp.result.get("preview")
        assert preview is None

    def test_approvals_disabled_skips_preview(self) -> None:
        """When approvals_enabled=False, no approval check and no preview."""
        from noa.tools.gateway import ToolGateway, ToolRequest

        gw = ToolGateway()
        adapter = _FakeAdapter({"ok": True})
        gw.register("gmail", adapter)
        gw.policy_engine = self._make_policy_engine("medium")

        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={"to": "a@b.com", "subject": "S", "body": "B"},
            user_id=uuid.uuid4(),
        )
        resp = asyncio.run(gw.dispatch(req, approvals_enabled=False))

        # Approvals disabled: adapter executes, no approval_required
        assert len(adapter.calls) == 1
        assert resp.error is None


# ===========================================================================
# 8. ChatRequest includes tool_scope field
# ===========================================================================

class TestChatRequestToolScope:
    """ChatRequest Pydantic model exposes tool_scope field."""

    def test_chat_request_has_tool_scope_field(self) -> None:
        """ChatRequest model has tool_scope as an optional str field."""
        from noa.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello", tool_scope=None)
        assert req.tool_scope is None

    def test_chat_request_tool_scope_defaults_to_none(self) -> None:
        """tool_scope defaults to None when not provided."""
        from noa.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello")
        assert req.tool_scope is None

    def test_chat_request_tool_scope_accepts_valid_scope(self) -> None:
        """ChatRequest accepts a known scope name."""
        from noa.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello", tool_scope="email_draft")
        assert req.tool_scope == "email_draft"
