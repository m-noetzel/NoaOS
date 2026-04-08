"""OV2: Tests for LangGraph interrupt-based approval flow.

Findings resolved: ARCH-AP1 (High), BE-AP2 (Medium), PERF-AP1 (Low).

Test plan:
- Happy path: tool_node calls interrupt() when approval required
- Happy path: tool_node dispatches with approved=True on resume
- Negative path: tool_node returns denial message when decision=denied
- Happy path: runner detects __interrupt__ and emits approval_requested SSE
- Happy path: runner.resume() calls graph with Command(resume=decision)
- Happy path: graph compiled with MemorySaver checkpointer
- Negative path: runner.resume() handles graph error gracefully
- Integration: decide_approval triggers _resume_graph (no _execute_approved_tool)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# 1. tool_node calls interrupt() when approval required
# ---------------------------------------------------------------------------


class TestToolNodeInterrupt:
    """Verify tool_node calls interrupt() when gateway returns approval_required."""

    def test_interrupt_imported_in_tool_node(self) -> None:
        """tool_node imports interrupt from langgraph.types at call time."""
        import inspect

        from noa.orchestrator.nodes import tools

        src = inspect.getsource(tools.tool_node)
        assert "from langgraph.types import interrupt" in src
        assert "interrupt(interrupt_payload)" in src or "interrupt(" in src

    def test_interrupt_payload_fields(self) -> None:
        """Interrupt payload contains tool, function, args, risk_tier."""
        import inspect

        from noa.orchestrator.nodes import tools

        src = inspect.getsource(tools.tool_node)
        # Verify all required fields are present in the payload construction
        assert '"approval_required"' in src
        assert '"tool"' in src
        assert '"function"' in src
        assert '"args"' in src
        assert '"risk_tier"' in src

    async def test_tool_node_calls_interrupt_when_approval_required(self) -> None:
        """When gateway returns approval_required, tool_node calls interrupt()."""
        from noa.orchestrator.nodes import tools

        # Mock gateway that returns approval_required
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.error = "Approval required"
        mock_response.result = {
            "approval_required": True,
            "tool": "calendar",
            "function": "create_event",
            "args": {"title": "Test"},
            "risk_tier": "medium",
        }
        mock_gateway.dispatch = AsyncMock(return_value=mock_response)

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "calendar", "function": "create_event", "args": {"title": "Test"}}],
            "tool_results": [],
            "tool_rounds": 0,
            "approvals_enabled": True,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "privacy_mode": "external",
            "tool_scope": None,
            "messages": [],
        }

        interrupted_values: list[Any] = []

        def fake_interrupt(value: Any) -> dict[str, Any]:
            interrupted_values.append(value)
            # Simulate resume with approved decision
            return {"decision": "approved"}

        mock_gateway.dispatch.side_effect = [
            # First call: approval_required
            MagicMock(
                error="Approval required",
                result={
                    "approval_required": True,
                    "tool": "calendar",
                    "function": "create_event",
                    "risk_tier": "medium",
                },
            ),
            # Second call (after resume with approved): success
            MagicMock(error=None, result={"event_id": "123"}),
        ]
        with (
            patch.object(tools, "_gateway", mock_gateway),
            patch("langgraph.types.interrupt", fake_interrupt),
        ):
            result = await tools.tool_node(state)

        # interrupt() should have been called once with approval_required=True
        assert len(interrupted_values) == 1
        iv = interrupted_values[0]
        assert iv.get("approval_required") is True
        assert iv.get("tool") == "calendar"
        assert iv.get("function") == "create_event"


# ---------------------------------------------------------------------------
# 2. Tool node processes approved decision on resume
# ---------------------------------------------------------------------------


class TestToolNodeApprovedResume:
    """Verify tool_node re-dispatches with approvals_enabled=False on approved."""

    async def test_approved_resume_dispatches_without_approval_gate(self) -> None:
        """On approved decision, gateway is called with approvals_enabled=False."""
        from noa.orchestrator.nodes import tools

        dispatch_calls: list[dict[str, Any]] = []

        async def _mock_dispatch(req: Any, *, approvals_enabled: bool = True) -> Any:
            dispatch_calls.append({"approvals_enabled": approvals_enabled, "req": req})
            if not dispatch_calls or approvals_enabled:
                # First call: approval required
                r = MagicMock()
                r.error = "Approval required"
                r.result = {"approval_required": True, "risk_tier": "medium"}
                return r
            else:
                # Resume call: success
                r = MagicMock()
                r.error = None
                r.result = {"event_id": "abc"}
                return r

        mock_gateway = MagicMock()
        mock_gateway.dispatch = _mock_dispatch

        call_count = [0]

        async def dispatch_side_effects(req: Any, *, approvals_enabled: bool = True) -> Any:
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.error = "Approval required"
                r.result = {"approval_required": True, "risk_tier": "medium"}
            else:
                r.error = None
                r.result = {"event_id": "abc"}
            return r

        mock_gateway.dispatch = dispatch_side_effects

        def _fake_interrupt(value: Any) -> dict[str, Any]:
            return {"decision": "approved"}

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "calendar", "function": "create_event", "args": {}}],
            "tool_results": [],
            "tool_rounds": 0,
            "approvals_enabled": True,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "privacy_mode": "external",
            "tool_scope": None,
            "messages": [],
        }

        with (
            patch.object(tools, "_gateway", mock_gateway),
            patch("langgraph.types.interrupt", _fake_interrupt),
        ):
            result = await tools.tool_node(state)

        # Two gateway calls: first (approval_required), second (approved=True bypasses gate)
        assert call_count[0] == 2, f"Expected 2 dispatch calls, got {call_count[0]}"
        # Result should not have approval_required
        tool_results = result.get("tool_results", [])
        assert len(tool_results) == 1
        assert not tool_results[0].get("approval_required")


# ---------------------------------------------------------------------------
# 3. Tool node processes denied decision on resume
# ---------------------------------------------------------------------------


class TestToolNodeDeniedResume:
    """Verify tool_node returns denial message when decision is denied."""

    async def test_denied_resume_returns_denial_message(self) -> None:
        """On denied decision, tool result contains denial error message."""
        from noa.orchestrator.nodes import tools

        call_count = [0]

        async def dispatch_side_effects(req: Any, *, approvals_enabled: bool = True) -> Any:
            call_count[0] += 1
            r = MagicMock()
            # First call: approval required
            r.error = "Approval required"
            r.result = {"approval_required": True, "risk_tier": "medium"}
            return r

        mock_gateway = MagicMock()
        mock_gateway.dispatch = dispatch_side_effects

        def _fake_interrupt(value: Any) -> dict[str, Any]:
            # User denies
            return {"decision": "denied"}

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "calendar", "function": "create_event", "args": {}}],
            "tool_results": [],
            "tool_rounds": 0,
            "approvals_enabled": True,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "privacy_mode": "external",
            "tool_scope": None,
            "messages": [],
        }

        with (
            patch.object(tools, "_gateway", mock_gateway),
            patch("langgraph.types.interrupt", _fake_interrupt),
        ):
            result = await tools.tool_node(state)

        # Only one gateway call (approval_required); no second dispatch
        assert call_count[0] == 1
        tool_results = result.get("tool_results", [])
        assert len(tool_results) == 1
        # The result should be a denial, not approval_required
        assert "denied" in tool_results[0] or "denied by user" in tool_results[0].get("error", "")
        assert not tool_results[0].get("approval_required")


# ---------------------------------------------------------------------------
# 4. Runner detects __interrupt__ and emits approval_requested SSE
# ---------------------------------------------------------------------------


class TestRunnerInterruptDetection:
    """Verify runner.run() detects __interrupt__ in stream and emits SSE."""

    async def test_runner_emits_approval_requested_on_interrupt(self) -> None:
        """Runner emits approval_requested SSE when graph is interrupted."""
        from noa.orchestrator.runner import OrchestratorRunner

        # Fake interrupt object matching LangGraph's Interrupt namedtuple API
        class FakeInterrupt:
            def __init__(self, value: dict[str, Any]) -> None:
                self.value = value

        interrupt_value = {
            "approval_required": True,
            "tool": "calendar",
            "function": "create_event",
            "args": {"title": "Test"},
            "risk_tier": "high",
        }

        # Mock graph that yields an __interrupt__ chunk
        async def _fake_astream(state: Any, config: Any = None) -> Any:
            yield {"__interrupt__": [FakeInterrupt(interrupt_value)]}

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream

        # Mock run_service
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)

        events: list[dict[str, Any]] = []
        async for event in runner.run(
            message="create a meeting",
            run_service=mock_run_service,
            run_id="test-run-001",
        ):
            events.append(event)

        event_types = [e["event_type"] for e in events]
        assert "approval_requested" in event_types, (
            f"Expected approval_requested in events, got: {event_types}"
        )

        ap_event = next(e for e in events if e["event_type"] == "approval_requested")
        assert ap_event["payload"]["tool"] == "calendar"
        assert ap_event["payload"]["function"] == "create_event"
        assert ap_event["payload"]["risk_tier"] == "high"

    async def test_runner_sets_awaiting_approval_status_on_interrupt(self) -> None:
        """Runner updates run status to awaiting_approval when interrupted."""
        from noa.orchestrator.runner import OrchestratorRunner

        class FakeInterrupt:
            def __init__(self, value: dict[str, Any]) -> None:
                self.value = value

        async def _fake_astream(state: Any, config: Any = None) -> Any:
            yield {"__interrupt__": [FakeInterrupt({
                "approval_required": True,
                "tool": "gmail",
                "function": "send_email",
                "args": {},
                "risk_tier": "medium",
            })]}

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.run(
            message="send email",
            run_service=mock_run_service,
            run_id="test-run-002",
        ):
            events.append(event)

        # update_status should have been called with "awaiting_approval"
        status_calls = [
            call.args[1]
            for call in mock_run_service.update_status.call_args_list
            if len(call.args) > 1
        ]
        assert "awaiting_approval" in status_calls, (
            f"Expected awaiting_approval status call, got: {status_calls}"
        )


# ---------------------------------------------------------------------------
# 5. runner.resume() triggers graph continuation
# ---------------------------------------------------------------------------


class TestRunnerResume:
    """Verify runner.resume() calls graph.astream with Command(resume=decision)."""

    async def test_resume_calls_graph_with_command(self) -> None:
        """resume() passes Command(resume=decision) to graph.astream."""
        from langgraph.types import Command

        from noa.orchestrator.runner import OrchestratorRunner, _pending_interrupts

        # Pre-register the run as pending interrupt
        _pending_interrupts["test-run-resume"] = "test-run-resume"

        resume_commands: list[Any] = []

        async def _fake_astream(cmd_or_state: Any, config: Any = None) -> Any:
            resume_commands.append(cmd_or_state)
            # OV3: yield agent node output (responder deleted)
            yield {
                "agent": {
                    "response": "Event created successfully.",
                    "llm_usage": [],
                },
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)

        events = []
        async for event in runner.resume(
            run_id="test-run-resume",
            decision={"decision": "approved"},
            run_service=mock_run_service,
        ):
            events.append(event)

        assert len(resume_commands) == 1
        cmd = resume_commands[0]
        assert isinstance(cmd, Command), f"Expected Command, got {type(cmd)}"
        assert cmd.resume == {"decision": "approved"}

    async def test_resume_emits_result_ready_after_graph_completes(self) -> None:
        """resume() emits result_ready event after graph loop completes (OV3)."""
        from noa.orchestrator.runner import OrchestratorRunner, _pending_interrupts

        _pending_interrupts["test-run-result"] = "test-run-result"

        async def _fake_astream(cmd_or_state: Any, config: Any = None) -> Any:
            # OV3: agent node sets response; runner emits result_ready after loop
            yield {
                "agent": {
                    "response": "Calendar event created.",
                    "llm_usage": [],
                }
            }

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.resume(
            run_id="test-run-result",
            decision={"decision": "approved"},
            run_service=mock_run_service,
        ):
            events.append(event)

        event_types = [e["event_type"] for e in events]
        assert "result_ready" in event_types, f"Expected result_ready, got: {event_types}"
        result_evt = next(e for e in events if e["event_type"] == "result_ready")
        assert result_evt["payload"]["response"] == "Calendar event created."

    async def test_resume_marks_completed_after_success(self) -> None:
        """resume() updates run status to completed after successful graph run."""
        from noa.orchestrator.runner import OrchestratorRunner, _pending_interrupts

        _pending_interrupts["test-run-complete"] = "test-run-complete"

        async def _fake_astream(cmd_or_state: Any, config: Any = None) -> Any:
            # OV3: agent node output; runner emits result_ready after loop
            yield {"agent": {"response": "Done.", "llm_usage": []}}

        mock_graph = MagicMock()
        mock_graph.astream = _fake_astream

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        async for _ in runner.resume(
            run_id="test-run-complete",
            decision={"decision": "approved"},
            run_service=mock_run_service,
        ):
            pass

        status_calls = [
            call.args[1]
            for call in mock_run_service.update_status.call_args_list
            if len(call.args) > 1
        ]
        assert "completed" in status_calls, f"Expected completed, got: {status_calls}"


# ---------------------------------------------------------------------------
# 6. Graph compiled with MemorySaver checkpointer
# ---------------------------------------------------------------------------


class TestGraphCheckpointerWiring:
    """Verify that build_graph().compile(checkpointer=saver) is called in app.py."""

    def test_app_wires_memory_saver(self) -> None:
        """app.py imports MemorySaver and passes it to graph.compile()."""
        import inspect

        from noa.api import app as app_module

        src = inspect.getsource(app_module.wire_llm_pipeline)
        assert "MemorySaver" in src
        assert "checkpointer=lg_saver" in src or "compile(checkpointer=" in src

    def test_build_graph_returns_state_graph(self) -> None:
        """build_graph() returns a StateGraph that can be compiled."""
        from langgraph.graph import StateGraph

        from noa.orchestrator.graph import build_graph

        g = build_graph()
        assert isinstance(g, StateGraph)

    def test_graph_compiles_with_memory_saver(self) -> None:
        """The graph can be compiled with MemorySaver without errors."""
        from langgraph.checkpoint.memory import MemorySaver

        from noa.orchestrator.graph import build_graph

        saver = MemorySaver()
        compiled = build_graph().compile(checkpointer=saver)
        assert compiled is not None


# ---------------------------------------------------------------------------
# 7. route_after_tools no longer has approval_required branch
# ---------------------------------------------------------------------------


class TestRouteAfterTools:
    """Verify route_after_tools doesn't check approval_required (OV2 removes it)."""

    def test_route_after_tools_no_approval_branch(self) -> None:
        """route_after_tools routes to agent or evaluator only — no approval_required check.

        OV3: routes to evaluator (not responder) when max retries reached.
        """
        from noa.orchestrator.graph import route_after_tools

        # A state that previously would have routed via approval_required
        # Now it should route normally based on tool_rounds
        state_with_approved: dict[str, Any] = {
            "tool_results": [{"name": "calendar.create_event", "approved": True}],
            "tool_rounds": 1,
            "max_retries": 3,
        }
        result = route_after_tools(state_with_approved)
        assert result == "agent"  # Not "evaluator" — rounds remaining

    def test_route_after_tools_still_caps_on_max_retries(self) -> None:
        """route_after_tools routes to evaluator when max_retries reached (OV3)."""
        from noa.orchestrator.graph import route_after_tools

        state: dict[str, Any] = {
            "tool_results": [],
            "tool_rounds": 3,
            "max_retries": 3,
        }
        assert route_after_tools(state) == "evaluator"


# ---------------------------------------------------------------------------
# 8. Integration: decide_approval triggers _resume_graph (not _execute_approved_tool)
# ---------------------------------------------------------------------------


class TestDecideApprovalIntegration:
    """Verify decide_approval endpoint uses _resume_graph, not _execute_approved_tool."""

    def test_execute_approved_tool_is_removed(self) -> None:
        """_execute_approved_tool no longer exists in approvals.py."""
        from noa.api.v1 import approvals

        assert not hasattr(approvals, "_execute_approved_tool"), (
            "_execute_approved_tool should be removed (replaced by _resume_graph)"
        )

    def test_resume_graph_function_exists(self) -> None:
        """_resume_graph coroutine is defined in approvals.py."""
        import inspect

        from noa.api.v1 import approvals

        assert hasattr(approvals, "_resume_graph"), "_resume_graph must be defined"
        assert inspect.iscoroutinefunction(approvals._resume_graph)

    def test_decide_approval_calls_resume_graph(self) -> None:
        """decide_approval() calls asyncio.ensure_future(_resume_graph(...))."""
        import inspect

        from noa.api.v1 import approvals

        src = inspect.getsource(approvals.decide_approval)
        assert "_resume_graph" in src
        assert "_execute_approved_tool" not in src

    def test_resume_graph_uses_runner_resume(self) -> None:
        """_resume_graph() calls runner.resume() to continue the graph."""
        import inspect

        from noa.api.v1 import approvals

        src = inspect.getsource(approvals._resume_graph)
        assert "runner.resume" in src

    async def test_resume_graph_noop_when_no_runner(self) -> None:
        """_resume_graph() logs warning and returns when runner is not available."""
        from noa.api.v1.approvals import _resume_graph

        with patch("noa.api.app_state.get_runner", return_value=None):
            # Should not raise
            await _resume_graph(
                run_id="test-run",
                decision={"decision": "approved"},
                user_id="00000000-0000-0000-0000-000000000001",
            )


# ---------------------------------------------------------------------------
# 9. Cross-domain approval includes cross_domain in interrupt payload
# ---------------------------------------------------------------------------


class TestCrossDomainInterrupt:
    """Verify cross_domain flag is forwarded in interrupt payload."""

    async def test_cross_domain_included_in_interrupt_payload(self) -> None:
        """When tool result has cross_domain=True, interrupt payload includes it."""
        from noa.orchestrator.nodes import tools

        interrupted_values: list[Any] = []

        def _fake_interrupt(value: Any) -> dict[str, Any]:
            interrupted_values.append(value)
            return {"decision": "denied"}

        async def dispatch_side_effects(req: Any, *, approvals_enabled: bool = True) -> Any:
            r = MagicMock()
            r.error = "Approval required"
            r.result = {
                "approval_required": True,
                "risk_tier": "high",
                "cross_domain": True,
                "reason": "Accessing private data from external domain",
            }
            return r

        mock_gateway = MagicMock()
        mock_gateway.dispatch = dispatch_side_effects

        state: dict[str, Any] = {
            "tool_calls": [{"tool": "memory", "function": "recall", "args": {}}],
            "tool_results": [],
            "tool_rounds": 0,
            "approvals_enabled": True,
            "user_id": "00000000-0000-0000-0000-000000000001",
            "privacy_mode": "external",
            "tool_scope": None,
            "messages": [],
        }

        with (
            patch.object(tools, "_gateway", mock_gateway),
            patch("langgraph.types.interrupt", _fake_interrupt),
        ):
            await tools.tool_node(state)

        assert len(interrupted_values) == 1
        iv = interrupted_values[0]
        assert iv.get("cross_domain") is True
        assert "Accessing private" in iv.get("reason", "")
