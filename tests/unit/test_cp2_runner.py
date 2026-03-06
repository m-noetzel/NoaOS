"""Tests for CP2: OrchestratorRunner + Event Types.

Verifies that OrchestratorRunner compiles the graph, runs it,
yields SSE events, and records events via RunService.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def _mock_run_service() -> MagicMock:
    """Create a mock RunService."""
    svc = MagicMock()
    svc.create_run = MagicMock(
        return_value=MagicMock(
            id="run-001",
            status="pending",
        )
    )
    svc.update_status = MagicMock()
    svc.append_event = MagicMock()
    return svc


def _collect_events(runner: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """Run the runner and collect all yielded events."""
    async def _run() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        async for event in runner.run(**kwargs):
            result.append(event)
        return result

    return asyncio.get_event_loop().run_until_complete(_run())


class TestRunnerInit:
    """Runner initializes with compiled graph."""

    def test_runner_accepts_graph(self) -> None:
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        runner = OrchestratorRunner(graph=mock_graph)
        assert runner is not None


class TestRunnerEvents:
    """Runner yields correct SSE events during execution."""

    def _make_runner(self) -> Any:
        from noa.orchestrator.runner import OrchestratorRunner

        # Mock the compiled graph's ainvoke to return final state
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
                "privacy_mode": "external",
                "selected_model": "anthropic/claude-haiku",
                "tool_calls": [],
                "tool_results": [],
                "response": "Hi there!",
                "total_cost": 0.001,
            }
        )
        return OrchestratorRunner(graph=mock_graph)

    def test_yields_message_received_first(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        assert len(events) > 0
        assert events[0]["event_type"] == "message_received"

    def test_yields_classification_done(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        types = [e["event_type"] for e in events]
        assert "classification_done" in types

    def test_yields_step_started(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        types = [e["event_type"] for e in events]
        assert "step_started" in types

    def test_yields_result_ready_with_response(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        types = [e["event_type"] for e in events]
        assert "result_ready" in types
        result_event = next(
            e for e in events if e["event_type"] == "result_ready"
        )
        assert "response" in result_event["payload"]

    def test_yields_error_on_exception(self) -> None:
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            side_effect=RuntimeError("LLM failed"),
        )
        runner = OrchestratorRunner(graph=mock_graph)
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        types = [e["event_type"] for e in events]
        assert "error" in types

    def test_events_have_correct_shape(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        for event in events:
            assert "event_type" in event
            assert "payload" in event
            assert "timestamp" in event


class TestRunnerStatusTransitions:
    """Runner updates Run status correctly."""

    def _make_runner(self) -> Any:
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "Hi!"},
                ],
                "privacy_mode": "external",
                "selected_model": "anthropic/claude-haiku",
                "tool_calls": [],
                "tool_results": [],
                "response": "Hi!",
                "total_cost": 0.001,
            }
        )
        return OrchestratorRunner(graph=mock_graph)

    def test_transitions_to_running_then_completed(self) -> None:
        runner = self._make_runner()
        svc = _mock_run_service()

        _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        # Should have called update_status with "running" first
        calls = [c[0] for c in svc.update_status.call_args_list]
        statuses = [c[1] for c in calls]
        assert "running" in statuses
        assert "completed" in statuses

    def test_transitions_to_failed_on_error(self) -> None:
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            side_effect=RuntimeError("boom"),
        )
        runner = OrchestratorRunner(graph=mock_graph)
        svc = _mock_run_service()

        _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        calls = [c[0] for c in svc.update_status.call_args_list]
        statuses = [c[1] for c in calls]
        assert "failed" in statuses


class TestRunnerEventPersistence:
    """Runner appends events via RunService."""

    def test_events_appended_to_run_service(self) -> None:
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "Hi!"},
                ],
                "privacy_mode": "external",
                "selected_model": "anthropic/claude-haiku",
                "tool_calls": [],
                "tool_results": [],
                "response": "Hi!",
                "total_cost": 0.001,
            }
        )
        runner = OrchestratorRunner(graph=mock_graph)
        svc = _mock_run_service()

        events = _collect_events(
            runner,
            message="hello",
            run_service=svc,
            run_id="run-001",
        )

        # RunService.append_event should have been called
        # for each event yielded
        assert svc.append_event.call_count >= len(events)
