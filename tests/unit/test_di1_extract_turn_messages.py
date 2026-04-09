"""Tests for DI1 — _extract_turn_messages() multi-round and missing-id fixes.

W26-M1: Verifies that multiple tool-call rounds per turn are correctly
separated into distinct assistant+tool message pairs, and that providers
omitting tool_call `id` (Ollama, Kimi) get synthetic IDs so results don't
collide.
"""

from __future__ import annotations

from noa.api.v1.chat import _extract_turn_messages


def _tool_called_event(name: str, call_id: str | None = None) -> dict:
    tc: dict = {"name": name, "arguments": {}}
    if call_id is not None:
        tc["id"] = call_id
    return {"event_type": "tool_called", "payload": {"tool_call": tc}}


def _tool_result_event(name: str, result: dict | None = None) -> dict:
    tr = {"name": name, **(result or {"output": "ok"})}
    return {"event_type": "tool_result", "payload": {"tool_name": name, "tool_result": tr}}


class TestSingleRound:
    """Single tool-call round — baseline behaviour."""

    def test_single_call_produces_assistant_and_tool_messages(self) -> None:
        events = [
            _tool_called_event("search", "call_1"),
            _tool_result_event("search"),
        ]
        msgs = _extract_turn_messages(events)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "assistant"
        assert len(msgs[0]["tool_calls"]) == 1
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["name"] == "search"

    def test_empty_events_returns_empty_list(self) -> None:
        assert _extract_turn_messages([]) == []

    def test_non_tool_events_ignored(self) -> None:
        events = [
            {"event_type": "token_stream", "payload": {"token": "hi"}},
            {"event_type": "result_ready", "payload": {"response": "done"}},
        ]
        assert _extract_turn_messages(events) == []


class TestMultipleRounds:
    """DI1 fix: multiple tool-call rounds per agent turn."""

    def test_two_rounds_produce_two_assistant_messages(self) -> None:
        """tool_A → result_A → tool_B → result_B should produce 2 pairs."""
        events = [
            _tool_called_event("search", "call_1"),
            _tool_result_event("search"),
            _tool_called_event("calculator", "call_2"),
            _tool_result_event("calculator"),
        ]
        msgs = _extract_turn_messages(events)
        # Expect: [assistant(search), tool(search), assistant(calculator), tool(calculator)]
        assert len(msgs) == 4

        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["tool_calls"][0]["name"] == "search"

        assert msgs[1]["role"] == "tool"
        assert msgs[1]["name"] == "search"

        assert msgs[2]["role"] == "assistant"
        assert msgs[2]["tool_calls"][0]["name"] == "calculator"

        assert msgs[3]["role"] == "tool"
        assert msgs[3]["name"] == "calculator"

    def test_three_rounds_produce_three_pairs(self) -> None:
        events = [
            _tool_called_event("a", "id1"),
            _tool_result_event("a"),
            _tool_called_event("b", "id2"),
            _tool_result_event("b"),
            _tool_called_event("c", "id3"),
            _tool_result_event("c"),
        ]
        msgs = _extract_turn_messages(events)
        assert len(msgs) == 6
        roles = [m["role"] for m in msgs]
        assert roles == ["assistant", "tool", "assistant", "tool", "assistant", "tool"]

    def test_parallel_calls_in_same_round_stay_together(self) -> None:
        """Two tool_called before any result = single round with two calls."""
        events = [
            _tool_called_event("search", "c1"),
            _tool_called_event("weather", "c2"),
            _tool_result_event("search"),
            _tool_result_event("weather"),
        ]
        msgs = _extract_turn_messages(events)
        # One assistant message with 2 tool_calls + 2 tool messages
        assert len(msgs) == 3
        assert msgs[0]["role"] == "assistant"
        assert len(msgs[0]["tool_calls"]) == 2
        assert msgs[1]["role"] == "tool"
        assert msgs[2]["role"] == "tool"


class TestMissingIdHandling:
    """DI1 fix: providers (Ollama, Kimi) that omit `id` on tool calls."""

    def test_missing_id_gets_synthetic_id(self) -> None:
        """Tool call without `id` should get a synthetic ID like tool_0."""
        events = [
            _tool_called_event("search", call_id=None),  # omit id
            _tool_result_event("search"),
        ]
        msgs = _extract_turn_messages(events)
        assert len(msgs) == 2
        tc = msgs[0]["tool_calls"][0]
        # Synthetic id generated — starts with "tool_"
        assert tc["id"].startswith("tool_")

        # Tool message must reference the same synthetic id
        assert msgs[1]["tool_call_id"] == tc["id"]

    def test_two_missing_ids_get_distinct_synthetic_ids(self) -> None:
        """Two tool calls without id in different rounds get distinct IDs."""
        events = [
            _tool_called_event("a"),  # no id
            _tool_result_event("a"),
            _tool_called_event("b"),  # no id
            _tool_result_event("b"),
        ]
        msgs = _extract_turn_messages(events)
        assert len(msgs) == 4
        id1 = msgs[0]["tool_calls"][0]["id"]
        id2 = msgs[2]["tool_calls"][0]["id"]
        # IDs must be different (no key collision)
        assert id1 != id2

    def test_result_matched_to_synthetic_id(self) -> None:
        """Result's tool_call_id must match the generated synthetic id."""
        events = [
            _tool_called_event("fetch"),  # no id
            _tool_result_event("fetch", {"data": "result"}),
        ]
        msgs = _extract_turn_messages(events)
        call_id = msgs[0]["tool_calls"][0]["id"]
        assert msgs[1]["tool_call_id"] == call_id

    def test_same_tool_called_twice_no_collision(self) -> None:
        """Same tool name called twice in separate rounds without IDs."""
        events = [
            _tool_called_event("search"),  # round 1, no id
            _tool_result_event("search"),
            _tool_called_event("search"),  # round 2, no id
            _tool_result_event("search"),
        ]
        msgs = _extract_turn_messages(events)
        # Should produce 2 complete round pairs
        assert len(msgs) == 4
        id1 = msgs[0]["tool_calls"][0]["id"]
        id2 = msgs[2]["tool_calls"][0]["id"]
        assert id1 != id2
        # Each result linked to its own round's call
        assert msgs[1]["tool_call_id"] == id1
        assert msgs[3]["tool_call_id"] == id2


class TestToolEndEvents:
    """tool_end events (alternative to tool_result) are handled correctly."""

    def test_tool_end_event_produces_tool_message(self) -> None:
        events = [
            _tool_called_event("email", "e1"),
            {"event_type": "tool_end", "payload": {
                "tool_name": "email",
                "result": {"sent": True, "name": "email"},
            }},
        ]
        msgs = _extract_turn_messages(events)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "assistant"
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["name"] == "email"


class TestResultOrdering:
    """Result order is preserved."""

    def test_result_order_matches_call_order(self) -> None:
        events = [
            _tool_called_event("first", "f1"),
            _tool_called_event("second", "f2"),
            _tool_result_event("second"),
            _tool_result_event("first"),
        ]
        msgs = _extract_turn_messages(events)
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        assert tool_msgs[0]["name"] == "second"
        assert tool_msgs[1]["name"] == "first"
