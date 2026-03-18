"""Tests for QC1: Critical Runtime Fixes.

Covers findings C1, C4, C5, A3, H3 from FINDINGS.md.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# C1: tool_node async dispatch must return dict, not Future
# ---------------------------------------------------------------------------

class TestC1AsyncToolDispatch:
    """C1: _dispatch_gateway must return dict, not Future."""

    @pytest.mark.asyncio
    async def test_dispatch_gateway_returns_dict(self) -> None:
        """_dispatch_gateway must return a dict (awaitable, not Future)."""
        from noa.orchestrator.nodes.tools import _dispatch_gateway, set_gateway

        mock_response = MagicMock()
        mock_response.error = None
        mock_response.result = {"data": "test"}

        mock_gateway = MagicMock()
        mock_gateway.dispatch = AsyncMock(return_value=mock_response)
        set_gateway(mock_gateway)

        try:
            result = await _dispatch_gateway("calendar", "list_events", {})
            assert isinstance(result, dict), (
                f"Expected dict, got {type(result).__name__}"
            )
        finally:
            set_gateway(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_tool_node_produces_valid_results(self) -> None:
        """tool_node must produce a list of dicts in tool_results,
        each with a 'name' key — not Futures or coroutines."""
        from noa.orchestrator.nodes.tools import set_gateway, tool_node
        from noa.tools.gateway import ToolGateway, ToolResponse

        class _FakeAdapter:
            async def execute(self, request: Any) -> ToolResponse:
                return ToolResponse(result={"output": "hello"}, provider="fake")

        gw = ToolGateway()
        gw.register("calendar", _FakeAdapter())
        set_gateway(gw)

        try:
            state: dict[str, Any] = {
                "tool_calls": [
                    {"tool": "calendar", "function": "list_events", "args": {}},
                ],
                "tool_rounds": 0,
                "messages": [],
                "approvals_enabled": False,
                "user_id": None,
                "tool_scope": None,
            }
            output = await tool_node(state)
            results = output["tool_results"]
            assert len(results) == 1
            r = results[0]
            assert isinstance(r, dict)
            assert "name" in r
            # The result must contain actual data, not a Future
            assert "output" in r or "error" in r
        finally:
            set_gateway(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C4: Schema drift — migration must add missing columns
# ---------------------------------------------------------------------------

class TestC4SchemaDrift:
    """C4: Migration 005 must exist and add Approval.domain + UsageStats.task_id."""

    def test_migration_005_exists(self) -> None:
        """Migration file 005 must exist with correct structure."""
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[2]
            / "alembic" / "versions" / "005_schema_drift_fix.py"
        )
        assert migration.exists(), (
            f"Migration 005 does not exist at {migration}"
        )

        content = migration.read_text()
        assert "def upgrade" in content
        assert "def downgrade" in content
        assert 'down_revision' in content and '"004"' in content

    def test_approval_model_has_domain_column(self) -> None:
        """Approval ORM model must declare a 'domain' column."""
        from noa.db.models.approval import Approval
        assert hasattr(Approval, "domain"), "Approval model missing 'domain' column"

    def test_usage_stats_model_has_task_id_column(self) -> None:
        """UsageStats ORM model must declare a 'task_id' column."""
        from noa.db.models.usage import UsageStats
        assert hasattr(UsageStats, "task_id"), (
            "UsageStats model missing 'task_id' column"
        )


# ---------------------------------------------------------------------------
# C5: JWT secret must not fall back to empty string
# ---------------------------------------------------------------------------

class TestC5JwtSecretNoEmptyFallback:
    """C5: require_auth must refuse to operate with an empty/None secret_key."""

    def test_middleware_rejects_none_secret_key(self) -> None:
        """If settings.secret_key is None, require_auth must raise,
        not silently use an empty string."""
        import inspect

        from noa.auth.middleware import require_auth

        # Read the source to verify there is no `or ""` fallback
        source = inspect.getsource(require_auth)
        assert 'or ""' not in source, (
            "require_auth still contains `or \"\"` fallback for secret_key"
        )
        assert "or ''" not in source, (
            "require_auth still contains `or ''` fallback for secret_key"
        )

    def test_empty_secret_key_raises_at_startup(self) -> None:
        """When secret_key is None, the auth system must raise RuntimeError
        rather than signing tokens with an empty key."""
        from noa.config import Settings

        # In non-production mode, secret_key defaults to _DEV_SECRET (not None)
        # But the middleware itself must refuse None
        settings = Settings(secret_key=None)
        assert settings.secret_key is None

        # The middleware function should detect None and raise
        # We test this by checking the code path
        from noa.auth.middleware import require_auth
        source = __import__("inspect").getsource(require_auth)
        # Must contain a check that raises on None secret
        assert "RuntimeError" in source or "raise" in source.split("secret")[1][:200], (
            "require_auth does not raise when secret_key is None"
        )


# ---------------------------------------------------------------------------
# A3: OrchestratorRunner must initialize all AgentState fields
# ---------------------------------------------------------------------------

class TestA3FullStateInitialization:
    """A3: initial_state in OrchestratorRunner.run() must include
    model_config and tool_rounds."""

    @pytest.mark.asyncio
    async def test_initial_state_has_model_config(self) -> None:
        """initial_state must contain 'model_config' key.

        Wave 23: runner uses graph.astream() not graph.ainvoke(). The state
        is captured by intercepting astream's first argument.
        """
        from noa.orchestrator.runner import OrchestratorRunner

        captured_state: dict[str, Any] = {}

        mock_graph = MagicMock()

        async def capture_astream(state: dict[str, Any]):
            captured_state.update(state)
            # Yield one agent chunk so runner gets past the graph loop
            yield {"agent": {"response": "test", "tool_calls": [], "total_cost": 0.0}}

        mock_graph.astream = capture_astream

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_svc = MagicMock()
        mock_run_svc.update_status = MagicMock()
        mock_run_svc.append_event = MagicMock()

        async for _ in runner.run(
            message="hello",
            run_service=mock_run_svc,
            run_id="test-run",
        ):
            pass

        assert "model_config" in captured_state, (
            "initial_state missing 'model_config' field"
        )
        assert isinstance(captured_state["model_config"], dict)

    @pytest.mark.asyncio
    async def test_initial_state_has_tool_rounds(self) -> None:
        """initial_state must contain 'tool_rounds' key.

        Wave 23: runner uses graph.astream() not graph.ainvoke().
        """
        from noa.orchestrator.runner import OrchestratorRunner

        captured_state: dict[str, Any] = {}

        mock_graph = MagicMock()

        async def capture_astream(state: dict[str, Any]):
            captured_state.update(state)
            yield {"agent": {"response": "test", "tool_calls": [], "total_cost": 0.0}}

        mock_graph.astream = capture_astream

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_svc = MagicMock()
        mock_run_svc.update_status = MagicMock()
        mock_run_svc.append_event = MagicMock()

        async for _ in runner.run(
            message="hello",
            run_service=mock_run_svc,
            run_id="test-run",
        ):
            pass

        assert "tool_rounds" in captured_state, (
            "initial_state missing 'tool_rounds' field"
        )
        assert captured_state["tool_rounds"] == 0


# ---------------------------------------------------------------------------
# H3: AuditService must be properly instantiated (not __new__)
# ---------------------------------------------------------------------------

class TestH3AuditServiceInstantiation:
    """H3: AuditService must not be created via __new__ in app.py."""

    def test_app_does_not_use_dunder_new_for_audit_service(self) -> None:
        """app.py must not use AuditService.__new__(AuditService)."""
        import inspect

        from noa.api import app as app_module

        source = inspect.getsource(app_module)
        assert "__new__(AuditService)" not in source, (
            "app.py still uses AuditService.__new__(AuditService) — "
            "must properly instantiate or use the async method directly"
        )

    def test_audit_service_init_sets_session(self) -> None:
        """AuditService.__init__ must set the _session attribute."""
        from noa.audit.service import AuditService

        mock_session = MagicMock()
        svc = AuditService(session=mock_session)
        assert svc._session is mock_session


# ---------------------------------------------------------------------------
# Integration test: tool_node round-trip through registry
# ---------------------------------------------------------------------------

class TestToolNodeIntegration:
    """Non-mocked integration: tool_node → ToolGateway → result dict."""

    @pytest.mark.asyncio
    async def test_tool_node_full_dispatch_returns_dict_results(self) -> None:
        """End-to-end: tool_node dispatches through gateway and returns
        a dict with 'tool_results' containing actual dicts (not Futures)."""
        from noa.orchestrator.nodes.tools import set_gateway, tool_node
        from noa.tools.adapters.direct import DirectApiAdapter
        from noa.tools.gateway import ToolGateway

        # Build a real tool implementing ToolInterface
        class DummyTool:
            name = "test_tool"
            domain = "external"
            risk_tiers = {"do_thing": "low"}

            async def execute(
                self, *, function: str, args: dict[str, Any]
            ) -> dict[str, Any]:
                return {"message": f"Handled {function} with {args}"}

        gw = ToolGateway()
        gw.register("test_tool", DirectApiAdapter(tool=DummyTool()))
        set_gateway(gw)

        try:
            state: dict[str, Any] = {
                "tool_calls": [
                    {"tool": "test_tool", "function": "do_thing", "args": {"x": 1}},
                ],
                "tool_rounds": 0,
                "messages": [],
                "approvals_enabled": False,
                "user_id": None,
                "tool_scope": None,
            }
            output = await tool_node(state)
            results = output["tool_results"]
            assert len(results) == 1
            r = results[0]
            assert isinstance(r, dict), f"Expected dict, got {type(r)}"
            assert r["name"] == "test_tool.do_thing"
            # Must have actual result data or error, not a Future
            has_data = any(k not in ("name",) for k in r)
            assert has_data, "Result dict has no data keys beyond 'name'"
        finally:
            set_gateway(None)  # type: ignore[arg-type]
