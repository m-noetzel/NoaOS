"""LF1 — Langfuse observability tests.

Tests:
- TraceContext records generation/span/score calls to Langfuse SDK
- TraceContext silently no-ops when Langfuse keys not set
- TraceContext silently no-ops when langfuse package not installed
- get_langfuse() singleton behaviour (cached per-process)
- flush() delegates correctly
- Runner integration: TraceContext is created and flushed on run completion
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_langfuse_singleton() -> None:
    """Reset the module-level Langfuse singleton so tests start clean."""
    import noa.observability.langfuse_client as lf_mod

    lf_mod._langfuse_instance = None  # noqa: SLF001
    lf_mod._langfuse_checked = False  # noqa: SLF001


# ---------------------------------------------------------------------------
# get_langfuse() singleton
# ---------------------------------------------------------------------------


@pytest.mark.lf1
def test_get_langfuse_returns_none_when_keys_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_langfuse() returns None when env vars are absent."""
    _reset_langfuse_singleton()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from noa.observability.langfuse_client import get_langfuse

    result = get_langfuse()
    assert result is None


@pytest.mark.lf1
def test_get_langfuse_returns_none_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_langfuse() returns None when the langfuse package is not installed."""
    _reset_langfuse_singleton()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    # Simulate missing package by removing it from sys.modules and blocking import
    sys.modules.pop("langfuse", None)
    with patch.dict(sys.modules, {"langfuse": None}):  # type: ignore[dict-item]
        from noa.observability.langfuse_client import get_langfuse

        result = get_langfuse()

    assert result is None


@pytest.mark.lf1
def test_get_langfuse_returns_client_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_langfuse() returns a Langfuse instance when keys and package exist."""
    _reset_langfuse_singleton()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3001")

    mock_lf = MagicMock()
    mock_lf_class = MagicMock(return_value=mock_lf)
    mock_module = MagicMock()
    mock_module.Langfuse = mock_lf_class

    with patch.dict(sys.modules, {"langfuse": mock_module}):
        import noa.observability.langfuse_client as lf_mod

        # Force re-import to pick up patched sys.modules
        importlib.reload(lf_mod)
        lf_mod._langfuse_checked = False  # noqa: SLF001
        lf_mod._langfuse_instance = None  # noqa: SLF001

        result = lf_mod.get_langfuse()

    assert result is mock_lf
    mock_lf_class.assert_called_once_with(
        public_key="pk-test",
        secret_key="sk-test",
        host="http://localhost:3001",
    )


@pytest.mark.lf1
def test_get_langfuse_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_langfuse() returns the same instance on repeated calls."""
    _reset_langfuse_singleton()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from noa.observability.langfuse_client import get_langfuse

    r1 = get_langfuse()
    r2 = get_langfuse()
    assert r1 is r2  # same None object, but proves no re-initialisation


# ---------------------------------------------------------------------------
# TraceContext — no-op when Langfuse unavailable
# ---------------------------------------------------------------------------


@pytest.mark.lf1
def test_trace_context_noop_when_langfuse_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TraceContext methods all silently no-op when keys are absent."""
    _reset_langfuse_singleton()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from noa.observability.langfuse_client import TraceContext

    ctx = TraceContext(run_id="run-001", user_id="user-1", metadata={"k": "v"})
    # None of these should raise
    ctx.generation("agent", "gpt-4o", [], "hello")
    ctx.span("tool/search", input={"q": "test"}, output={"r": []})
    ctx.score("goal_alignment", 4.0, comment="good")
    ctx.update(output="final")
    ctx.flush()
    assert ctx._trace is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# TraceContext — records to mock Langfuse
# ---------------------------------------------------------------------------


@pytest.mark.lf1
def test_trace_context_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext calls lf.trace() with run_id and user_id."""
    _reset_langfuse_singleton()

    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(
            run_id="run-abc",
            user_id="user-42",
            metadata={"privacy_mode": "external"},
        )

    mock_lf.trace.assert_called_once_with(
        id="run-abc",
        name="run/run-abc",
        user_id="user-42",
        metadata={"privacy_mode": "external"},
    )
    assert ctx._trace is mock_trace  # noqa: SLF001


@pytest.mark.lf1
def test_trace_context_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext.generation() calls trace.generation() with correct args."""
    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-1")
        ctx.generation(
            name="agent",
            model="gpt-4o",
            input_messages=[{"role": "user", "content": "hello"}],
            output="world",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            metadata={"cost": 0.001},
        )

    mock_trace.generation.assert_called_once_with(
        name="agent",
        model="gpt-4o",
        input=[{"role": "user", "content": "hello"}],
        output="world",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        metadata={"cost": 0.001},
    )


@pytest.mark.lf1
def test_trace_context_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext.span() calls trace.span() with correct args."""
    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-2")
        ctx.span(
            name="tool/web_search",
            input={"query": "langfuse docs"},
            output={"results": ["result1"]},
            metadata={"tool_name": "web_search"},
        )

    mock_trace.span.assert_called_once_with(
        name="tool/web_search",
        input={"query": "langfuse docs"},
        output={"results": ["result1"]},
        metadata={"tool_name": "web_search"},
    )


@pytest.mark.lf1
def test_trace_context_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext.score() calls trace.score() with correct args."""
    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-3")
        ctx.score("completeness", 3.5, comment="needs more detail")

    mock_trace.score.assert_called_once_with(
        name="completeness",
        value=3.5,
        comment="needs more detail",
    )


@pytest.mark.lf1
def test_trace_context_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext.update() calls trace.update() with kwargs."""
    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-4")
        ctx.update(output="final response", metadata={"total_cost": 0.002})

    mock_trace.update.assert_called_once_with(
        output="final response",
        metadata={"total_cost": 0.002},
    )


@pytest.mark.lf1
def test_trace_context_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceContext.flush() calls lf.flush()."""
    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-5")
        ctx.flush()

    mock_lf.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Graceful degradation — SDK errors
# ---------------------------------------------------------------------------


@pytest.mark.lf1
def test_trace_context_generation_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If trace.generation() raises, TraceContext silently swallows it."""
    mock_trace = MagicMock()
    mock_trace.generation.side_effect = RuntimeError("network error")
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-err")
        # Should NOT raise despite the RuntimeError in the SDK
        ctx.generation("agent", "gpt-4o", [], "")


@pytest.mark.lf1
def test_trace_context_span_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    """If trace.span() raises, TraceContext silently swallows it."""
    mock_trace = MagicMock()
    mock_trace.span.side_effect = RuntimeError("timeout")
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import TraceContext

        ctx = TraceContext(run_id="run-err2")
        ctx.span("tool/calendar")  # no raise


# ---------------------------------------------------------------------------
# Module-level flush()
# ---------------------------------------------------------------------------


@pytest.mark.lf1
def test_module_flush_noop_when_no_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """module-level flush() silently no-ops when Langfuse is unavailable."""
    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=None,
    ):
        from noa.observability.langfuse_client import flush

        flush()  # must not raise


@pytest.mark.lf1
def test_module_flush_calls_lf_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    """module-level flush() calls lf.flush() when Langfuse is available."""
    mock_lf = MagicMock()

    with patch(
        "noa.observability.langfuse_client.get_langfuse",
        return_value=mock_lf,
    ):
        from noa.observability.langfuse_client import flush

        flush()

    mock_lf.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Runner integration — TraceContext lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.lf1
@pytest.mark.asyncio
async def test_runner_creates_and_flushes_trace() -> None:
    """OrchestratorRunner.run() creates a TraceContext and flushes it on success."""
    from noa.orchestrator.runner import OrchestratorRunner

    # Build a minimal mock graph that returns a complete state
    state_result: dict[str, Any] = {
        "response": "hello world",
        "total_cost": 0.001,
        "llm_usage": [
            {
                "node": "agent",
                "model": "gpt-4o",
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "cost": 0.001,
                "provider": "openai",
            }
        ],
        "tool_calls": [],
        "tool_results": [],
    }

    async def _mock_astream(
        state: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"agent": state_result}

    mock_graph = MagicMock()
    mock_graph.astream = _mock_astream

    mock_run_service = MagicMock()
    mock_run_service.update_status = AsyncMock()
    mock_run_service.append_event = AsyncMock()

    mock_trace = MagicMock()
    mock_trace.flush = MagicMock()

    with patch(
        "noa.orchestrator.runner.TraceContext",
        return_value=mock_trace,
    ) as mock_ctx_cls:
        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for ev in runner.run(
            message="hello",
            run_service=mock_run_service,
            run_id="run-lf1-test",
            user_id="user-1",
        ):
            events.append(ev)

    # TraceContext must have been created with the run_id
    mock_ctx_cls.assert_called_once()
    call_kwargs = mock_ctx_cls.call_args
    assert call_kwargs.kwargs["run_id"] == "run-lf1-test"
    assert call_kwargs.kwargs["user_id"] == "user-1"

    # Trace must have been flushed
    mock_trace.flush.assert_called()

    # Events should include result_ready
    event_types = [e["event_type"] for e in events]
    assert "result_ready" in event_types


@pytest.mark.lf1
@pytest.mark.asyncio
async def test_runner_records_generation_spans() -> None:
    """Runner records one generation span per llm_usage entry."""
    from noa.orchestrator.runner import OrchestratorRunner

    state_result: dict[str, Any] = {
        "response": "done",
        "total_cost": 0.002,
        "llm_usage": [
            {"node": "classifier", "model": "gpt-4o-mini", "cost": 0.0001},
            {"node": "agent", "model": "gpt-4o", "cost": 0.002},
        ],
        "tool_calls": [],
        "tool_results": [],
    }

    async def _mock_astream(
        state: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"agent": state_result}

    mock_graph = MagicMock()
    mock_graph.astream = _mock_astream
    mock_run_service = MagicMock()
    mock_run_service.update_status = AsyncMock()
    mock_run_service.append_event = AsyncMock()

    mock_trace = MagicMock()

    with patch(
        "noa.orchestrator.runner.TraceContext",
        return_value=mock_trace,
    ):
        runner = OrchestratorRunner(graph=mock_graph)
        async for _ in runner.run(
            message="test",
            run_service=mock_run_service,
            run_id="run-gen-test",
        ):
            pass

    # generation() should have been called twice (one per llm_usage entry)
    assert mock_trace.generation.call_count == 2
    call_names = [c.kwargs["name"] for c in mock_trace.generation.call_args_list]
    assert "classifier" in call_names
    assert "agent" in call_names


@pytest.mark.lf1
@pytest.mark.asyncio
async def test_runner_records_tool_spans() -> None:
    """Runner records one span per tool result."""
    from noa.orchestrator.runner import OrchestratorRunner

    tool_result = {
        "name": "web_search",
        "args": {"query": "test"},
        "result": "some results",
    }
    state_result: dict[str, Any] = {
        "response": "done",
        "total_cost": 0.0,
        "llm_usage": [],
        "tool_calls": [],
        "tool_results": [tool_result],
    }

    async def _mock_astream(
        state: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"tools": state_result}

    mock_graph = MagicMock()
    mock_graph.astream = _mock_astream
    mock_run_service = MagicMock()
    mock_run_service.update_status = AsyncMock()
    mock_run_service.append_event = AsyncMock()

    mock_trace = MagicMock()

    with patch(
        "noa.orchestrator.runner.TraceContext",
        return_value=mock_trace,
    ):
        runner = OrchestratorRunner(graph=mock_graph)
        async for _ in runner.run(
            message="search something",
            run_service=mock_run_service,
            run_id="run-tool-test",
        ):
            pass

    # span() should have been called for the tool result
    assert mock_trace.span.call_count >= 1
    call_names = [c.kwargs["name"] for c in mock_trace.span.call_args_list]
    assert "tool/web_search" in call_names


@pytest.mark.lf1
@pytest.mark.asyncio
async def test_runner_flushes_trace_on_error() -> None:
    """Runner flushes the Langfuse trace even when the graph raises."""
    from noa.orchestrator.runner import OrchestratorRunner

    async def _failing_astream(
        state: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise RuntimeError("graph exploded")
        yield  # make this an async generator

    mock_graph = MagicMock()
    mock_graph.astream = _failing_astream
    mock_run_service = MagicMock()
    mock_run_service.update_status = AsyncMock()
    mock_run_service.append_event = AsyncMock()

    mock_trace = MagicMock()

    with patch(
        "noa.orchestrator.runner.TraceContext",
        return_value=mock_trace,
    ):
        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for ev in runner.run(
            message="crash",
            run_service=mock_run_service,
            run_id="run-error-test",
        ):
            events.append(ev)

    # flush must still be called on error
    mock_trace.flush.assert_called()

    # Error event must be yielded to client
    event_types = [e["event_type"] for e in events]
    assert "error" in event_types
