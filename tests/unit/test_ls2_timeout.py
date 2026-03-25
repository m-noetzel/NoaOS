"""Tests for LS2: Orchestrator Timeout Watchdog.

Spec refs: SPEC.md §22
Phase plan: PHASE_DETAILS.md LS2

Tests verify that long-running graph execution is terminated after
timeout_seconds, a TIMEOUT error event is yielded, and the run is
marked as failed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.runner import OrchestratorRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_service(*, fail_update: bool = False) -> MagicMock:
    """Create a mock RunService."""
    svc = MagicMock()
    svc.update_status = AsyncMock(
        side_effect=Exception("update failed") if fail_update else None
    )
    svc.append_event = AsyncMock()
    return svc


def _make_graph(chunks: list[dict[str, Any]]) -> MagicMock:
    """Create a mock graph whose astream yields the given chunks."""

    async def _astream(state: dict[str, Any]):  # type: ignore[misc]
        for chunk in chunks:
            yield chunk

    graph = MagicMock()
    graph.astream = _astream
    return graph


def _make_slow_graph(
    *,
    chunks: list[dict[str, Any]],
    delay_per_chunk: float,
) -> MagicMock:
    """Create a mock graph that sleeps between chunks to simulate slow execution."""

    async def _astream(state: dict[str, Any]):  # type: ignore[misc]
        for chunk in chunks:
            await asyncio.sleep(delay_per_chunk)
            yield chunk

    graph = MagicMock()
    graph.astream = _astream
    return graph


async def _collect(runner: OrchestratorRunner, **kwargs: Any) -> list[dict[str, Any]]:
    """Collect all events from runner.run() into a list."""
    events: list[dict[str, Any]] = []
    async for event in runner.run(**kwargs):
        events.append(event)
    return events


_BASE_KWARGS: dict[str, Any] = {
    "message": "hello",
    "run_id": "run-test-1",
    "privacy_mode": "external",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_timeout_within_budget() -> None:
    """Graph completing within timeout_seconds yields no TIMEOUT event."""
    chunk = {"agent": {"response": "done", "tool_calls": [], "tool_results": []}}
    graph = _make_graph([chunk])
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    events = await _collect(
        runner,
        run_service=svc,
        timeout_seconds=60,
        **_BASE_KWARGS,
    )

    event_types = [e["event_type"] for e in events]
    # Must not contain any TIMEOUT error
    timeout_events = [
        e for e in events
        if e["event_type"] == "error"
        and e["payload"].get("code") == "TIMEOUT"
    ]
    assert len(timeout_events) == 0, "Unexpected timeout event in fast execution"
    # Must still complete with result_ready
    assert "result_ready" in event_types


@pytest.mark.asyncio
async def test_timeout_fires_after_elapsed_time() -> None:
    """When graph takes longer than timeout_seconds, TIMEOUT error event is yielded."""
    # Two chunks: the first arrives after 0.05s (within budget),
    # the second after another 0.05s (over budget for a 0.06s total timeout).
    chunks = [
        {"agent": {"response": None, "tool_calls": [], "tool_results": []}},
        {"responder": {"response": "done", "tool_calls": [], "tool_results": []}},
    ]
    graph = _make_slow_graph(chunks=chunks, delay_per_chunk=0.04)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    events = await _collect(
        runner,
        run_service=svc,
        timeout_seconds=0.05,  # budget exhausted after first chunk's 0.04s delay
        **_BASE_KWARGS,
    )

    timeout_events = [
        e for e in events
        if e["event_type"] == "error"
        and e["payload"].get("code") == "TIMEOUT"
    ]
    assert len(timeout_events) == 1, (
        f"Expected exactly 1 TIMEOUT event, got {len(timeout_events)}. "
        f"Event types: {[e['event_type'] for e in events]}"
    )


@pytest.mark.asyncio
async def test_timeout_event_payload() -> None:
    """TIMEOUT event carries the correct message and code fields."""
    chunk = {"agent": {"response": None, "tool_calls": [], "tool_results": []}}
    graph = _make_slow_graph(chunks=[chunk], delay_per_chunk=0.05)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    events = await _collect(
        runner,
        run_service=svc,
        timeout_seconds=0.01,
        **_BASE_KWARGS,
    )

    timeout_events = [
        e for e in events
        if e["event_type"] == "error"
        and e["payload"].get("code") == "TIMEOUT"
    ]
    assert len(timeout_events) == 1
    payload = timeout_events[0]["payload"]
    assert payload["code"] == "TIMEOUT"
    assert "timeout" in payload["message"].lower()
    assert "0" in payload["message"]  # timeout_seconds value appears in message


@pytest.mark.asyncio
async def test_run_marked_failed_on_timeout() -> None:
    """When timeout fires, run_service.update_status is called with 'failed'."""
    chunk = {"agent": {"response": None, "tool_calls": [], "tool_results": []}}
    graph = _make_slow_graph(chunks=[chunk], delay_per_chunk=0.05)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    await _collect(
        runner,
        run_service=svc,
        timeout_seconds=0.01,
        **_BASE_KWARGS,
    )

    # update_status called with 'failed' for the timeout
    status_calls = [
        call.args[1]
        for call in svc.update_status.call_args_list
        if len(call.args) >= 2
    ]
    assert "failed" in status_calls, (
        f"Expected 'failed' status update, got: {status_calls}"
    )


@pytest.mark.asyncio
async def test_no_result_ready_after_timeout() -> None:
    """After a timeout, the graph execution is aborted — no result_ready event."""
    chunks = [
        {"agent": {"response": None, "tool_calls": [], "tool_results": []}},
        {"responder": {"response": "should not arrive", "tool_calls": [], "tool_results": []}},
    ]
    graph = _make_slow_graph(chunks=chunks, delay_per_chunk=0.04)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    events = await _collect(
        runner,
        run_service=svc,
        timeout_seconds=0.05,
        **_BASE_KWARGS,
    )

    event_types = [e["event_type"] for e in events]
    assert "result_ready" not in event_types, (
        "result_ready should not be emitted after timeout"
    )


@pytest.mark.asyncio
async def test_timeout_update_status_failure_is_handled_gracefully() -> None:
    """If run_service.update_status raises on timeout, runner still completes cleanly."""
    chunk = {"agent": {"response": None, "tool_calls": [], "tool_results": []}}
    graph = _make_slow_graph(chunks=[chunk], delay_per_chunk=0.05)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service(fail_update=True)

    # Should not raise even when update_status throws
    events = await _collect(
        runner,
        run_service=svc,
        timeout_seconds=0.01,
        **_BASE_KWARGS,
    )

    timeout_events = [
        e for e in events
        if e["event_type"] == "error" and e["payload"].get("code") == "TIMEOUT"
    ]
    assert len(timeout_events) == 1


@pytest.mark.asyncio
async def test_stream_callback_cleared_after_timeout() -> None:
    """Stream callback is cleared (set to None) when timeout fires."""
    chunk = {"agent": {"response": None, "tool_calls": [], "tool_results": []}}
    graph = _make_slow_graph(chunks=[chunk], delay_per_chunk=0.05)
    runner = OrchestratorRunner(graph=graph)
    svc = _make_run_service()

    cleared_to_none: list[Any] = []

    def _fake_set_stream_callback(cb: Any) -> None:
        cleared_to_none.append(cb)

    with patch(
        "noa.orchestrator.nodes.agent.set_stream_callback",
        side_effect=_fake_set_stream_callback,
    ):
        await _collect(
            runner,
            run_service=svc,
            timeout_seconds=0.01,
            **_BASE_KWARGS,
        )

    # The last call to set_stream_callback should have been None (cleanup)
    assert None in cleared_to_none, (
        f"Expected set_stream_callback(None) call, got calls with: {cleared_to_none}"
    )
