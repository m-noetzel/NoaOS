"""Tests for MEM3 — Pre-Compaction Memory Flush.

Spec ref: MEM-M1 / MEM3
Verifies:
1. auto_extract is called before compact_messages when compaction is needed
2. auto_extract failure does not prevent compaction from running
3. auto_extract is NOT called when compaction is not needed
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.runner import OrchestratorRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner() -> OrchestratorRunner:
    """Create an OrchestratorRunner with a minimal mock graph."""
    mock_graph = MagicMock()
    return OrchestratorRunner(graph=mock_graph)


def _make_mock_run_service() -> MagicMock:
    svc = MagicMock()
    svc.update_status = AsyncMock()
    svc.append_event = AsyncMock()
    return svc


def _build_big_messages(n: int = 50) -> list[dict[str, Any]]:
    """Build a realistic message list to trigger compaction."""
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    for i in range(n):
        msgs.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}: " + "x" * 200,
        })
    return msgs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mem3_auto_extract_called_before_compaction() -> None:
    """auto_extract is called before compact_messages when context needs compaction."""
    runner = _make_runner()
    run_service = _make_mock_run_service()

    big_messages = _build_big_messages(50)

    call_order: list[str] = []

    mock_memory_tool = MagicMock()

    async def _fake_auto_extract(**kwargs: Any) -> dict[str, Any]:
        call_order.append("auto_extract")
        return {"status": "ok"}

    mock_memory_tool.auto_extract = _fake_auto_extract

    async def _fake_compact(
        messages: list[dict[str, Any]],
        invoke_fn: Any,
        model: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        call_order.append("compact_messages")
        return [{"role": "system", "content": "Summary"}], True

    async def _fake_astream(state: dict[str, Any], **kwargs: Any) -> Any:
        yield {
            "agent": {
                "response": "Done",
                "tool_calls": [],
                "messages": big_messages,
                "llm_usage": [],
                "thoughts": [],
            }
        }

    runner._graph.astream = _fake_astream

    with (
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._persist_event",
            new_callable=AsyncMock,
        ),
        patch("noa.orchestrator.nodes.tools.get_gateway", return_value=None),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._extract_response",
            return_value="Done",
        ),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._build_tool_context",
            return_value="",
        ),
        patch("noa.orchestrator.token_budget.needs_compaction", return_value=True),
        patch("noa.orchestrator.nodes.compactor.compact_messages", _fake_compact),
        patch("noa.orchestrator.nodes.agent.invoke_llm", new_callable=AsyncMock),
        patch.dict(
            "sys.modules",
            {"noa.private_worker.handlers": MagicMock(get_handler=lambda _: None)},
        ),
        patch("noa.tools.memory.MemoryTool", return_value=mock_memory_tool),
    ):
        events = []
        async for event in runner.run(
            message="Hello",
            run_service=run_service,
            run_id="run-mem3-test",
            user_id="user-1",
        ):
            events.append(event)

    # auto_extract must be called before compact_messages
    assert "auto_extract" in call_order, (
        "auto_extract was not called before compaction"
    )
    assert "compact_messages" in call_order, "compact_messages was not called"
    auto_idx = call_order.index("auto_extract")
    compact_idx = call_order.index("compact_messages")
    assert auto_idx < compact_idx, (
        f"auto_extract (pos {auto_idx}) must come before compact_messages (pos {compact_idx})"
    )


@pytest.mark.asyncio
async def test_mem3_auto_extract_failure_does_not_block_compaction() -> None:
    """If auto_extract raises, compaction still completes successfully."""
    runner = _make_runner()
    run_service = _make_mock_run_service()

    big_messages = _build_big_messages(50)
    compaction_ran = [False]

    mock_memory_tool = MagicMock()

    async def _failing_auto_extract(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Memory service unavailable")

    mock_memory_tool.auto_extract = _failing_auto_extract

    async def _fake_compact(
        messages: list[dict[str, Any]],
        invoke_fn: Any,
        model: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        compaction_ran[0] = True
        return [{"role": "system", "content": "Summary"}], True

    async def _fake_astream(state: dict[str, Any], **kwargs: Any) -> Any:
        yield {
            "agent": {
                "response": "Done",
                "tool_calls": [],
                "messages": big_messages,
                "llm_usage": [],
                "thoughts": [],
            }
        }

    runner._graph.astream = _fake_astream

    with (
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._persist_event",
            new_callable=AsyncMock,
        ),
        patch("noa.orchestrator.nodes.tools.get_gateway", return_value=None),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._extract_response",
            return_value="Done",
        ),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._build_tool_context",
            return_value="",
        ),
        patch("noa.orchestrator.token_budget.needs_compaction", return_value=True),
        patch("noa.orchestrator.nodes.compactor.compact_messages", _fake_compact),
        patch("noa.orchestrator.nodes.agent.invoke_llm", new_callable=AsyncMock),
        patch.dict(
            "sys.modules",
            {"noa.private_worker.handlers": MagicMock(get_handler=lambda _: None)},
        ),
        patch("noa.tools.memory.MemoryTool", return_value=mock_memory_tool),
    ):
        events = []
        async for event in runner.run(
            message="Hello",
            run_service=run_service,
            run_id="run-mem3-fail-test",
            user_id="user-1",
        ):
            events.append(event)

    assert compaction_ran[0], (
        "Compaction did not run after auto_extract failure — MEM3 best-effort violated"
    )


@pytest.mark.asyncio
async def test_mem3_no_auto_extract_when_no_compaction_needed() -> None:
    """auto_extract is NOT called when compaction threshold is not reached."""
    runner = _make_runner()
    run_service = _make_mock_run_service()

    auto_extract_called = [False]

    mock_memory_tool = MagicMock()

    async def _spy_auto_extract(**kwargs: Any) -> dict[str, Any]:
        auto_extract_called[0] = True
        return {"status": "ok"}

    mock_memory_tool.auto_extract = _spy_auto_extract

    small_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    async def _fake_astream(state: dict[str, Any], **kwargs: Any) -> Any:
        yield {
            "agent": {
                "response": "Done",
                "tool_calls": [],
                "messages": small_messages,
                "llm_usage": [],
                "thoughts": [],
            }
        }

    runner._graph.astream = _fake_astream

    with (
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._persist_event",
            new_callable=AsyncMock,
        ),
        patch("noa.orchestrator.nodes.tools.get_gateway", return_value=None),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._extract_response",
            return_value="Done",
        ),
        patch(
            "noa.orchestrator.runner.OrchestratorRunner._build_tool_context",
            return_value="",
        ),
        patch("noa.orchestrator.token_budget.needs_compaction", return_value=False),
        patch.dict(
            "sys.modules",
            {"noa.private_worker.handlers": MagicMock(get_handler=lambda _: None)},
        ),
        patch("noa.tools.memory.MemoryTool", return_value=mock_memory_tool),
    ):
        events = []
        async for event in runner.run(
            message="Hi",
            run_service=run_service,
            run_id="run-mem3-no-compact",
            user_id="user-1",
        ):
            events.append(event)

    assert not auto_extract_called[0], (
        "auto_extract should NOT be called when compaction is not needed"
    )
