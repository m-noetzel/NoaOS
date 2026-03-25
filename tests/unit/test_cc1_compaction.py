"""Tests for CC1: Context Window Compaction.

Spec ref: CC1 — automatic context compaction when conversations approach
the LLM context limit.

Test plan:
- Happy path: message list over 80% of model context → compaction runs,
  summary injected, recent messages preserved, SSE event emitted.
- Short conversation: < keep_recent + 1 messages → no compaction.
- Unknown model: falls back to 128 K default.
- Provider-prefixed model: "openai/gpt-4o" → strips prefix, looks up correctly.
- Compaction integration: runner emits "compaction" SSE event when needed and
  the result messages list is shorter.
- Boundary: invoke_fn failure → graceful skip, original messages returned.
- Token estimation: string vs structured content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from noa.orchestrator.nodes.compactor import (
    DEFAULT_KEEP_RECENT,
    compact_messages,
)
from noa.orchestrator.token_budget import (
    COMPACTION_THRESHOLD,
    MODEL_CONTEXT_WINDOWS,
    estimate_message_tokens,
    estimate_total_tokens,
    get_context_limit,
    needs_compaction,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeLLMResponse:
    content: str = "Summary of the conversation."


def _make_msg(role: str = "user", content: str = "hello") -> dict[str, Any]:
    return {"role": role, "content": content}


def _make_many_messages(
    n: int,
    chars_each: int = 100,
) -> list[dict[str, Any]]:
    """Create n alternating user/assistant messages with fixed-length content."""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": "x" * chars_each})
    return msgs


# ---------------------------------------------------------------------------
# token_budget module
# ---------------------------------------------------------------------------

class TestEstimateMessageTokens:
    def test_string_content(self) -> None:
        msg = _make_msg(content="a" * 300)
        est = estimate_message_tokens(msg)
        # 300 chars // 3 + 4 overhead = 104
        assert est == 104

    def test_empty_content(self) -> None:
        msg = _make_msg(content="")
        est = estimate_message_tokens(msg)
        assert est == 4  # just overhead

    def test_structured_content(self) -> None:
        """Structured content (list) is JSON-serialised for estimation."""
        msg = {"role": "user", "content": [{"type": "text", "text": "hello"}]}
        est = estimate_message_tokens(msg)
        assert est > 4  # non-trivial

    def test_missing_content_key(self) -> None:
        msg: dict[str, Any] = {"role": "user"}
        est = estimate_message_tokens(msg)
        assert est == 4

    def test_long_message(self) -> None:
        msg = _make_msg(content="w" * 3000)
        est = estimate_message_tokens(msg)
        assert est == 1004  # 3000 // 3 + 4


class TestEstimateTotalTokens:
    def test_empty_list(self) -> None:
        total = estimate_total_tokens([])
        assert total == 10  # base overhead only

    def test_single_message(self) -> None:
        msgs = [_make_msg(content="a" * 30)]
        total = estimate_total_tokens(msgs)
        # 30 // 3 + 4 + 10 base = 24
        assert total == 24

    def test_multiple_messages(self) -> None:
        msgs = _make_many_messages(4, chars_each=300)
        total = estimate_total_tokens(msgs)
        # each message: 300 // 3 + 4 = 104; 4 × 104 + 10 = 426
        assert total == 426


class TestGetContextLimit:
    def test_known_model(self) -> None:
        assert get_context_limit("gpt-4o-mini") == 128_000

    def test_provider_prefix_stripped(self) -> None:
        assert get_context_limit("openai/gpt-4o-mini") == 128_000

    def test_unknown_model_defaults(self) -> None:
        assert get_context_limit("some-unknown-model-xyz") == 128_000

    def test_small_model(self) -> None:
        assert get_context_limit("llama3.1") == 8_192

    def test_large_model(self) -> None:
        assert get_context_limit("gpt-4.1") == 1_048_576

    def test_all_known_models_present(self) -> None:
        """Every entry in MODEL_CONTEXT_WINDOWS is accessible."""
        for model_name in MODEL_CONTEXT_WINDOWS:
            assert get_context_limit(model_name) > 0


class TestNeedsCompaction:
    def test_short_history_no_compaction(self) -> None:
        msgs = _make_many_messages(3, chars_each=50)
        assert not needs_compaction(msgs, "gpt-4o-mini")

    def test_empty_no_compaction(self) -> None:
        assert not needs_compaction([], "gpt-4o-mini")

    def test_over_threshold_triggers_compaction(self) -> None:
        """Create a tiny-context model and flood it above threshold."""
        # llama3.1 has 8 192 token context; 80% = 6 553 tokens
        # Each message: 3 000 chars → 1 004 tokens
        # 7 messages → 7 × 1 004 + 10 = 7 038 > 6 553  → compaction
        msgs = _make_many_messages(7, chars_each=3000)
        assert needs_compaction(msgs, "llama3.1")

    def test_just_under_threshold_no_compaction(self) -> None:
        # llama3.1: threshold = int(8192 * 0.8) = 6553
        # 3 messages × 3 000 chars = 3 × 1 004 + 10 = 3 022 < 6 553
        msgs = _make_many_messages(3, chars_each=3000)
        assert not needs_compaction(msgs, "llama3.1")

    def test_threshold_is_80_percent(self) -> None:
        assert COMPACTION_THRESHOLD == 0.8


# ---------------------------------------------------------------------------
# compactor module
# ---------------------------------------------------------------------------

class TestCompactMessages:
    def _mock_invoke(self, response: str = "Summary text") -> Any:
        async def _fn(
            model: str,
            messages: list[dict[str, Any]],
            *,
            tools: Any = None,
            **_kwargs: Any,
        ) -> _FakeLLMResponse:
            return _FakeLLMResponse(content=response)
        return _fn

    @pytest.mark.asyncio
    async def test_too_few_messages_skips_compaction(self) -> None:
        msgs = _make_many_messages(DEFAULT_KEEP_RECENT)  # exactly keep_recent
        result, did_compact = await compact_messages(msgs, self._mock_invoke())
        assert not did_compact
        assert result is msgs  # same object returned

    @pytest.mark.asyncio
    async def test_one_over_threshold_compacts(self) -> None:
        msgs = _make_many_messages(DEFAULT_KEEP_RECENT + 2)
        result, did_compact = await compact_messages(
            msgs, self._mock_invoke("A nice summary.")
        )
        assert did_compact
        # summary message + keep_recent recent messages
        assert len(result) == DEFAULT_KEEP_RECENT + 1

    @pytest.mark.asyncio
    async def test_summary_inserted_as_system_message(self) -> None:
        msgs = _make_many_messages(DEFAULT_KEEP_RECENT + 3)
        result, did_compact = await compact_messages(
            msgs, self._mock_invoke("Key facts here.")
        )
        assert did_compact
        first = result[0]
        assert first["role"] == "system"
        assert "Key facts here." in first["content"]
        assert first.get("is_compaction_boundary") is True

    @pytest.mark.asyncio
    async def test_recent_messages_preserved_verbatim(self) -> None:
        keep = 4
        msgs = _make_many_messages(keep + 5, chars_each=50)
        # Mark last `keep` messages with unique content
        sentinel = "UNIQUE_SENTINEL_CONTENT"
        for i in range(-keep, 0):
            msgs[i]["content"] = f"{sentinel}_{i}"
        result, did_compact = await compact_messages(
            msgs, self._mock_invoke(), keep_recent=keep
        )
        assert did_compact
        recent = result[1:]  # skip summary
        assert len(recent) == keep
        for i, msg in enumerate(recent):
            assert sentinel in msg["content"], f"Sentinel missing in message {i}"

    @pytest.mark.asyncio
    async def test_invoke_failure_gracefully_skips(self) -> None:
        """If the LLM call fails, return original messages unchanged."""
        async def _failing_invoke(
            model: str, messages: list[dict], *, tools: Any = None, **_: Any
        ) -> _FakeLLMResponse:
            raise RuntimeError("LLM unavailable")

        msgs = _make_many_messages(DEFAULT_KEEP_RECENT + 3)
        result, did_compact = await compact_messages(msgs, _failing_invoke)
        assert not did_compact
        assert result is msgs

    @pytest.mark.asyncio
    async def test_empty_summary_skips(self) -> None:
        """Empty LLM response → no compaction."""
        msgs = _make_many_messages(DEFAULT_KEEP_RECENT + 3)
        result, did_compact = await compact_messages(
            msgs, self._mock_invoke("   ")  # whitespace only
        )
        assert not did_compact
        assert result is msgs

    @pytest.mark.asyncio
    async def test_custom_keep_recent(self) -> None:
        keep = 2
        msgs = _make_many_messages(keep + 4)
        result, did_compact = await compact_messages(
            msgs, self._mock_invoke("Summary."), keep_recent=keep
        )
        assert did_compact
        assert len(result) == keep + 1  # summary + 2 recent


# ---------------------------------------------------------------------------
# Runner integration: compaction event emitted
# ---------------------------------------------------------------------------

class TestRunnerCompactionIntegration:
    """End-to-end test: OrchestratorRunner emits a 'compaction' SSE event
    when the graph result contains messages that exceed the threshold.

    Uses a minimal fake graph that returns a large message list without
    needing a real LLM.
    """

    @pytest.mark.asyncio
    async def test_compaction_event_emitted_when_threshold_exceeded(
        self,
    ) -> None:
        """Runner emits 'compaction' event when messages exceed 80% of context."""
        pytest.importorskip("langgraph", reason="langgraph not installed")

        from noa.orchestrator.runner import OrchestratorRunner

        # Build a fake graph that returns a flood of messages (llama3.1, tiny ctx)
        # We use the llama3.1 model (8 192 token ctx) so we can trigger compaction
        # with a moderate number of messages.
        large_msgs = [
            {"role": "system", "content": "sys"},
        ] + _make_many_messages(8, chars_each=3000)  # > 80% of 8192 tokens

        class _FakeGraph:
            async def astream(self, state: dict[str, Any]) -> Any:  # type: ignore[override]
                # Yield a single chunk from the "responder" node
                yield {
                    "responder": {
                        "messages": large_msgs,
                        "response": "Final answer.",
                        "tool_calls": [],
                        "tool_results": [],
                        "total_cost": 0.0,
                        "llm_usage": [],
                        "eval_scores": None,
                        "eval_verdict": "pass",
                        "eval_cycle": 0,
                    }
                }

        class _FakeRunService:
            async def update_status(self, run_id: str, status: str) -> None:  # noqa: ARG002
                pass

            async def append_event(self, run_id: str, event: dict) -> None:  # noqa: ARG002
                pass

        runner = OrchestratorRunner(graph=_FakeGraph())

        # Patch invoke_llm for the compaction call so we don't need a real LLM
        compact_response = _FakeLLMResponse(content="Compaction summary.")

        async def _fake_invoke(
            model: str,
            messages: list[dict],
            *,
            privacy_mode: str = "external",
            max_tokens: int = 4096,
            tools: Any = None,
            temperature: Any = None,
        ) -> _FakeLLMResponse:
            return compact_response

        events: list[dict[str, Any]] = []
        with (
            pytest.MonkeyPatch().context() as mp,
        ):
            mp.setattr(
                "noa.orchestrator.nodes.agent.invoke_llm",
                _fake_invoke,
            )
            mp.setattr(
                "noa.orchestrator.nodes.agent._router",
                MagicMock(),
            )

            async for event in runner.run(
                message="hello",
                run_service=_FakeRunService(),
                run_id="test-run-cc1",
                model="llama3.1",
                history=None,
            ):
                events.append(event)

        event_types = [e["event_type"] for e in events]
        assert "compaction" in event_types, (
            f"Expected 'compaction' in events but got: {event_types}"
        )
        compaction_evt = next(e for e in events if e["event_type"] == "compaction")
        payload = compaction_evt["payload"]
        assert payload["messages_before"] > payload["messages_after"]
        assert payload["model"] == "llama3.1"

    @pytest.mark.asyncio
    async def test_no_compaction_event_for_short_conversation(self) -> None:
        """Runner does NOT emit 'compaction' for a short conversation."""
        pytest.importorskip("langgraph", reason="langgraph not installed")

        from noa.orchestrator.runner import OrchestratorRunner

        short_msgs = _make_many_messages(3, chars_each=50)

        class _FakeGraph:
            async def astream(self, state: dict[str, Any]) -> Any:  # type: ignore[override]
                yield {
                    "responder": {
                        "messages": short_msgs,
                        "response": "Done.",
                        "tool_calls": [],
                        "tool_results": [],
                        "total_cost": 0.0,
                        "llm_usage": [],
                        "eval_scores": None,
                        "eval_verdict": "pass",
                        "eval_cycle": 0,
                    }
                }

        class _FakeRunService:
            async def update_status(self, run_id: str, status: str) -> None:
                pass

            async def append_event(self, run_id: str, event: dict) -> None:
                pass

        runner = OrchestratorRunner(graph=_FakeGraph())

        events: list[dict[str, Any]] = []
        async for event in runner.run(
            message="hi",
            run_service=_FakeRunService(),
            run_id="test-run-cc1-short",
            model="gpt-4o-mini",
            history=None,
        ):
            events.append(event)

        event_types = [e["event_type"] for e in events]
        assert "compaction" not in event_types
