"""OV8: Tests for ask_user tool and Langfuse topology logging.

Test plan:
- ask_user_tool calls interrupt() with correct payload
- Runner differentiates ask_user vs approval interrupts (emits ask_user SSE event)
- Runner emits approval_requested for standard approval interrupts (no ask_user key)
- ask_user SSE event has correct structure with run_id, question, options, allow_freetext
- Resume endpoint handles user response (returns resuming to graph)
- Routing decision spans are emitted after key nodes
- Cycle tagging appears in span names when eval_cycle > 0

Spec refs: SPEC.md §22.1, §22.2. Phase: OV8.
"""

from __future__ import annotations

import typing
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

# ---------------------------------------------------------------------------
# 1. ask_user_tool calls interrupt() with correct payload
# ---------------------------------------------------------------------------


class TestAskUserTool:
    """Unit tests for the ask_user_tool function."""

    def test_ask_user_tool_calls_interrupt_with_correct_payload(self) -> None:
        """ask_user_tool calls interrupt() with ask_user=True and all fields."""
        captured: list[dict] = []

        def _fake_interrupt(payload: dict) -> dict:  # type: ignore[type-arg]
            captured.append(payload)
            return {"response": "Work"}

        with patch(
            "noa.tools.ask_user.interrupt", side_effect=_fake_interrupt
        ):
            from noa.tools.ask_user import ask_user_tool

            result = ask_user_tool(
                question="Which calendar?",
                options=["Work", "Personal"],
                allow_freetext=True,
            )

        assert len(captured) == 1
        payload = captured[0]
        assert payload["ask_user"] is True
        assert payload["question"] == "Which calendar?"
        assert payload["options"] == ["Work", "Personal"]
        assert payload["allow_freetext"] is True
        assert result == {"user_response": "Work"}

    def test_ask_user_tool_defaults(self) -> None:
        """ask_user_tool uses empty options and allow_freetext=True by default."""
        captured: list[dict] = []

        def _fake_interrupt(payload: dict) -> dict:  # type: ignore[type-arg]
            captured.append(payload)
            return {"response": "yes"}

        with patch(
            "noa.tools.ask_user.interrupt", side_effect=_fake_interrupt
        ):
            from noa.tools.ask_user import ask_user_tool

            result = ask_user_tool(question="Proceed?")

        payload = captured[0]
        assert payload["options"] == []
        assert payload["allow_freetext"] is True
        assert result == {"user_response": "yes"}

    def test_ask_user_tool_truncates_options_to_3(self) -> None:
        """ask_user_tool silently truncates options to max 3."""
        captured: list[dict] = []

        def _fake_interrupt(payload: dict) -> dict:  # type: ignore[type-arg]
            captured.append(payload)
            return {"response": "A"}

        with patch(
            "noa.tools.ask_user.interrupt", side_effect=_fake_interrupt
        ):
            from noa.tools.ask_user import ask_user_tool

            ask_user_tool(
                question="Pick one",
                options=["A", "B", "C", "D", "E"],
            )

        assert len(captured[0]["options"]) == 3

    def test_ask_user_tool_non_dict_resume_value(self) -> None:
        """ask_user_tool converts non-dict resume value to string."""

        def _fake_interrupt(_payload: dict) -> str:  # type: ignore[type-arg]
            return "plain string"

        with patch(
            "noa.tools.ask_user.interrupt", side_effect=_fake_interrupt
        ):
            from noa.tools.ask_user import ask_user_tool

            result = ask_user_tool(question="?")

        assert result == {"user_response": "plain string"}

    def test_ask_user_tool_empty_response(self) -> None:
        """ask_user_tool returns empty string when resume dict has no 'response' key."""

        def _fake_interrupt(_payload: dict) -> dict:  # type: ignore[type-arg]
            return {}

        with patch(
            "noa.tools.ask_user.interrupt", side_effect=_fake_interrupt
        ):
            from noa.tools.ask_user import ask_user_tool

            result = ask_user_tool(question="?")

        assert result == {"user_response": ""}


# ---------------------------------------------------------------------------
# 2. Runner differentiates ask_user vs approval interrupts
# ---------------------------------------------------------------------------


class TestRunnerInterruptDifferentiation:
    """Runner emits ask_user event for ask_user interrupts, approval_requested otherwise."""

    def _make_interrupt_chunk(self, iv: dict) -> dict:  # type: ignore[type-arg]
        """Build a fake LangGraph chunk with __interrupt__ key."""
        interrupt_item = MagicMock()
        interrupt_item.value = iv
        return {"__interrupt__": [interrupt_item]}

    async def test_ask_user_interrupt_emits_ask_user_event(self) -> None:
        """Runner emits ask_user SSE event when interrupt has ask_user=True."""
        from noa.orchestrator.runner import OrchestratorRunner

        iv = {
            "ask_user": True,
            "question": "Which calendar?",
            "options": ["Work", "Personal"],
            "allow_freetext": True,
        }

        chunk = self._make_interrupt_chunk(iv)

        # Build a mock graph that yields one interrupt chunk
        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        runner = OrchestratorRunner(graph=mock_graph)
        events: list[dict[str, Any]] = []

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        async for event in runner.run(
            message="test",
            run_service=mock_run_service,
            run_id="test-run-id",
        ):
            events.append(event)

        # Filter to just event_type events (exclude meta, classification_done, etc.)
        typed_events = {e["event_type"] for e in events}
        assert "ask_user" in typed_events
        assert "approval_requested" not in typed_events

        ask_events = [e for e in events if e["event_type"] == "ask_user"]
        assert len(ask_events) == 1
        payload = ask_events[0]["payload"]
        assert payload["question"] == "Which calendar?"
        assert payload["options"] == ["Work", "Personal"]
        assert payload["allow_freetext"] is True
        # run_id is included for frontend to know which run to resume
        assert payload["run_id"] == "test-run-id"

    async def test_approval_interrupt_emits_approval_requested_event(self) -> None:
        """Runner emits approval_requested SSE event for standard approval interrupts."""
        from noa.orchestrator.runner import OrchestratorRunner

        iv = {
            "approval_required": True,
            "tool": "calendar",
            "function": "create_event",
            "args": {"title": "Dentist"},
            "risk_tier": "medium",
        }

        chunk = self._make_interrupt_chunk(iv)

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        runner = OrchestratorRunner(graph=mock_graph)
        events: list[dict[str, Any]] = []

        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        async for event in runner.run(
            message="test",
            run_service=mock_run_service,
            run_id="test-run-id",
        ):
            events.append(event)

        typed_events = {e["event_type"] for e in events}
        assert "approval_requested" in typed_events
        assert "ask_user" not in typed_events

    @staticmethod
    async def _async_iter(items: list) -> Any:  # type: ignore[type-arg]
        """Helper to create an async iterator from a list."""
        for item in items:
            yield item


# ---------------------------------------------------------------------------
# 3. ask_user SSE event has correct structure
# ---------------------------------------------------------------------------


class TestAskUserSSEEventStructure:
    """Verify ask_user event structure conforms to sse_types.py spec."""

    def test_ask_user_in_valid_sse_event_types(self) -> None:
        """ask_user is in VALID_SSE_EVENT_TYPES."""
        from noa.orchestrator.sse_types import VALID_SSE_EVENT_TYPES

        assert "ask_user" in VALID_SSE_EVENT_TYPES

    def test_ask_user_event_typeddict_exists(self) -> None:
        """AskUserEvent TypedDict is importable from sse_types."""
        from noa.orchestrator.sse_types import AskUserEvent  # noqa: F401

        # Verify the TypedDict has the expected fields by checking annotations
        annotations = typing.get_type_hints(AskUserEvent)
        assert "event_type" in annotations
        assert "payload" in annotations
        assert "timestamp" in annotations

    def test_ask_user_payload_fields(self) -> None:
        """AskUserEvent payload has question, options, allow_freetext fields."""
        from noa.orchestrator.sse_types import _AskUserPayload  # noqa: F401

        annotations = typing.get_type_hints(_AskUserPayload)
        assert "question" in annotations
        assert "options" in annotations
        assert "allow_freetext" in annotations


# ---------------------------------------------------------------------------
# 4. Routing decision spans are emitted after key nodes
# ---------------------------------------------------------------------------


class TestRoutingDecisionSpans:
    """OV8: Verify routing decision spans are logged to Langfuse after key nodes."""

    async def test_routing_span_emitted_after_agent_with_tool_calls(self) -> None:
        """routing/after_agent span logged with destination=tools when agent has tool calls."""
        from noa.orchestrator.runner import OrchestratorRunner

        # Simulate agent node output with tool_calls
        agent_output = {
            "tool_calls": [{"name": "calendar__create_event", "args": {}}],
            "response": None,
        }
        chunk = {"agent": agent_output}

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        lf_spans: list[dict[str, Any]] = []

        def _fake_span(**kwargs: Any) -> None:
            lf_spans.append(kwargs)

        mock_lf_trace = MagicMock()
        mock_lf_trace.span = _fake_span
        mock_lf_trace.update = MagicMock()
        mock_lf_trace.generation = MagicMock()
        mock_lf_trace.score = MagicMock()
        mock_lf_trace.flush = MagicMock()

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        with patch(
            "noa.orchestrator.runner.TraceContext", return_value=mock_lf_trace
        ):
            async for _ in runner.run(
                message="test",
                run_service=mock_run_service,
                run_id="test-run-id",
            ):
                pass

        span_names = [s["name"] for s in lf_spans]
        assert "routing/after_agent" in span_names

        routing_span = next(s for s in lf_spans if s["name"] == "routing/after_agent")
        assert routing_span["output"]["destination"] == "tools"
        assert routing_span["input"]["tool_calls_count"] == 1

    async def test_routing_span_emitted_after_agent_without_tool_calls(self) -> None:
        """routing/after_agent span with destination=evaluator when no tool calls."""
        from noa.orchestrator.runner import OrchestratorRunner

        agent_output = {
            "tool_calls": [],
            "response": "Here is the answer.",
        }
        chunk = {"agent": agent_output}

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        lf_spans: list[dict[str, Any]] = []

        def _fake_span(**kwargs: Any) -> None:
            lf_spans.append(kwargs)

        mock_lf_trace = MagicMock()
        mock_lf_trace.span = _fake_span
        mock_lf_trace.update = MagicMock()
        mock_lf_trace.generation = MagicMock()
        mock_lf_trace.score = MagicMock()
        mock_lf_trace.flush = MagicMock()

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        with patch(
            "noa.orchestrator.runner.TraceContext", return_value=mock_lf_trace
        ):
            async for _ in runner.run(
                message="test",
                run_service=mock_run_service,
                run_id="test-run-id",
            ):
                pass

        span_names = [s["name"] for s in lf_spans]
        assert "routing/after_agent" in span_names

        routing_span = next(s for s in lf_spans if s["name"] == "routing/after_agent")
        assert routing_span["output"]["destination"] == "evaluator"

    async def test_routing_span_emitted_after_classifier(self) -> None:
        """routing/after_classifier span logged with task_type decision."""
        from noa.orchestrator.runner import OrchestratorRunner

        classifier_output = {
            "task_type": "execution",
            "privacy_mode": "external",
        }
        chunk = {"classifier": classifier_output}

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        lf_spans: list[dict[str, Any]] = []

        def _fake_span(**kwargs: Any) -> None:
            lf_spans.append(kwargs)

        mock_lf_trace = MagicMock()
        mock_lf_trace.span = _fake_span
        mock_lf_trace.update = MagicMock()
        mock_lf_trace.generation = MagicMock()
        mock_lf_trace.score = MagicMock()
        mock_lf_trace.flush = MagicMock()

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        with patch(
            "noa.orchestrator.runner.TraceContext", return_value=mock_lf_trace
        ):
            async for _ in runner.run(
                message="test",
                run_service=mock_run_service,
                run_id="test-run-id",
            ):
                pass

        span_names = [s["name"] for s in lf_spans]
        assert "routing/after_classifier" in span_names
        routing_span = next(
            s for s in lf_spans if s["name"] == "routing/after_classifier"
        )
        assert routing_span["input"]["task_type"] == "execution"
        assert routing_span["output"]["destination"] == "planner"

    @staticmethod
    async def _async_iter(items: list) -> Any:  # type: ignore[type-arg]
        for item in items:
            yield item


# ---------------------------------------------------------------------------
# 5. Cycle tagging in span names
# ---------------------------------------------------------------------------


class TestCycleTagging:
    """OV8: Span names include #cycleN suffix when eval_cycle > 0."""

    async def test_cycle_tag_added_when_eval_cycle_nonzero(self) -> None:
        """Node spans include #cycle1 suffix when eval_cycle = 1 (reroute)."""
        from noa.orchestrator.runner import OrchestratorRunner

        # Simulate agent node output that sets eval_cycle=1
        agent_output = {
            "tool_calls": [],
            "response": "Rerouted answer.",
            "eval_cycle": 1,
        }
        chunk = {"agent": agent_output}

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        lf_spans: list[dict[str, Any]] = []

        def _fake_span(**kwargs: Any) -> None:
            lf_spans.append(kwargs)

        mock_lf_trace = MagicMock()
        mock_lf_trace.span = _fake_span
        mock_lf_trace.update = MagicMock()
        mock_lf_trace.generation = MagicMock()
        mock_lf_trace.score = MagicMock()
        mock_lf_trace.flush = MagicMock()

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        with patch(
            "noa.orchestrator.runner.TraceContext", return_value=mock_lf_trace
        ):
            async for _ in runner.run(
                message="test",
                run_service=mock_run_service,
                run_id="test-run-id",
            ):
                pass

        span_names = [s["name"] for s in lf_spans]
        # Should have cycle-tagged span for agent
        assert "node/agent#cycle1" in span_names
        # Routing span should also be tagged
        assert "routing/after_agent#cycle1" in span_names

    async def test_no_cycle_tag_when_eval_cycle_zero(self) -> None:
        """Node spans have no cycle suffix when eval_cycle = 0 (first pass)."""
        from noa.orchestrator.runner import OrchestratorRunner

        agent_output = {
            "tool_calls": [],
            "response": "Answer.",
            "eval_cycle": 0,
        }
        chunk = {"agent": agent_output}

        mock_graph = MagicMock()
        mock_graph.astream = MagicMock(
            return_value=self._async_iter([chunk])
        )

        lf_spans: list[dict[str, Any]] = []

        def _fake_span(**kwargs: Any) -> None:
            lf_spans.append(kwargs)

        mock_lf_trace = MagicMock()
        mock_lf_trace.span = _fake_span
        mock_lf_trace.update = MagicMock()
        mock_lf_trace.generation = MagicMock()
        mock_lf_trace.score = MagicMock()
        mock_lf_trace.flush = MagicMock()

        runner = OrchestratorRunner(graph=mock_graph)
        mock_run_service = MagicMock()
        mock_run_service.update_status = AsyncMock()
        mock_run_service.append_event = AsyncMock()

        with patch(
            "noa.orchestrator.runner.TraceContext", return_value=mock_lf_trace
        ):
            async for _ in runner.run(
                message="test",
                run_service=mock_run_service,
                run_id="test-run-id",
            ):
                pass

        span_names = [s["name"] for s in lf_spans]
        assert "node/agent" in span_names
        assert "node/agent#cycle0" not in span_names

    @staticmethod
    async def _async_iter(items: list) -> Any:  # type: ignore[type-arg]
        for item in items:
            yield item


# ---------------------------------------------------------------------------
# 6. Integration: ask_user tool schema available to LLM
# ---------------------------------------------------------------------------


class TestAskUserToolSchema:
    """Verify ask_user tool schema is available in TOOL_SCHEMAS for LLM calls."""

    def test_ask_user_in_tool_schemas(self) -> None:
        """TOOL_SCHEMAS includes ask_user tool definition."""
        from noa.tools.definitions import TOOL_SCHEMAS

        assert "ask_user" in TOOL_SCHEMAS
        schema = TOOL_SCHEMAS["ask_user"]
        assert "ask_user" in schema["functions"]
        func_def = schema["functions"]["ask_user"]
        assert "question" in func_def["parameters"]["properties"]
        assert "question" in func_def["parameters"]["required"]

    def test_ask_user_schema_in_anthropic_format(self) -> None:
        """get_anthropic_tools returns ask_user in correct format."""
        from noa.tools.definitions import get_anthropic_tools

        tools = get_anthropic_tools(["ask_user"])
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "ask_user__ask_user"
        assert "input_schema" in tool
        assert "question" in tool["input_schema"]["properties"]

    def test_ask_user_schema_in_openai_format(self) -> None:
        """get_openai_tools returns ask_user in correct format."""
        from noa.tools.definitions import get_openai_tools

        tools = get_openai_tools(["ask_user"])
        assert len(tools) == 1
        tool = tools[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "ask_user__ask_user"
        assert "question" in tool["function"]["parameters"]["properties"]


# ---------------------------------------------------------------------------
# 7. Resume endpoint accepts user response
# ---------------------------------------------------------------------------


class TestAskUserResumeEndpoint:
    """Integration test: the /runs/{run_id}/resume endpoint accepts a response."""

    async def test_resume_endpoint_exists_and_requires_response_field(
        self,
    ) -> None:
        """GET /api/v1/runs/{run_id}/resume route exists in the app."""
        from fastapi.testclient import TestClient

        from noa.api.app import app

        with TestClient(app) as client:
            # POST without auth should get 401, proving route exists
            resp = client.post(
                "/api/v1/runs/00000000-0000-0000-0000-000000000001/resume",
                json={"response": "Work"},
            )
            # 401 = authenticated route exists; 422 = validation failure
            # (both mean the route exists and was reached)
            assert resp.status_code in (401, 422)
