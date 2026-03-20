"""CX1: Doom loop detection tests.

Tests that tool_node raises/returns an error when the same tool+args
combination appears >= DOOM_LOOP_THRESHOLD times in the last DOOM_LOOP_WINDOW
tool results.

Happy path:
- Tool called < threshold times → dispatches normally
- Same tool with *different* args → no doom loop

Negative path:
- Same tool + same args >= threshold times → DoomLoopError / error result
- Works for both registry-format and legacy-format tool calls
- Error is returned as a tool result, not raised (state machine stays live)

Window boundary:
- Signature appearing threshold times but spread beyond window → not triggered
"""

from __future__ import annotations

import pytest

from noa.orchestrator.nodes.tools import (
    _DOOM_LOOP_THRESHOLD,
    _DOOM_LOOP_WINDOW,
    DoomLoopError,
    _check_doom_loop,
    _tool_signature,
)

# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_tool_signature_stable():
    """Same tool + same args always produce the same signature."""
    sig1 = _tool_signature("calendar.list_events", {"start": "2024-01-01", "limit": 10})
    sig2 = _tool_signature("calendar.list_events", {"limit": 10, "start": "2024-01-01"})
    assert sig1 == sig2


def test_tool_signature_different_args_different_sig():
    """Different args produce different signatures."""
    sig1 = _tool_signature("search", {"q": "hello"})
    sig2 = _tool_signature("search", {"q": "world"})
    assert sig1 != sig2


def test_tool_signature_different_tool_different_sig():
    """Different tool names produce different signatures."""
    sig1 = _tool_signature("search", {"q": "test"})
    sig2 = _tool_signature("email", {"q": "test"})
    assert sig1 != sig2


def _make_prior_results(tool: str, args: dict, count: int) -> list[dict]:
    """Build a list of fake tool results with the given signature tag."""
    sig = _tool_signature(tool, args)
    return [{"name": tool, "_signature": sig, "result": {}} for _ in range(count)]


def test_check_doom_loop_below_threshold_ok():
    """No error raised when call count is below threshold."""
    prior = _make_prior_results("t", {"x": 1}, _DOOM_LOOP_THRESHOLD - 1)
    # Should not raise
    _check_doom_loop("t", {"x": 1}, prior)


def test_check_doom_loop_at_threshold_raises():
    """DoomLoopError raised when count reaches the threshold."""
    prior = _make_prior_results("t", {"x": 1}, _DOOM_LOOP_THRESHOLD)
    with pytest.raises(DoomLoopError, match="Doom loop detected"):
        _check_doom_loop("t", {"x": 1}, prior)


def test_check_doom_loop_different_args_no_trigger():
    """Different args don't trigger the loop even if same tool."""
    prior = _make_prior_results("t", {"x": 1}, _DOOM_LOOP_THRESHOLD)
    # Different args — should NOT raise
    _check_doom_loop("t", {"x": 2}, prior)


def test_check_doom_loop_window_boundary():
    """Signatures beyond the window are not counted."""
    args = {"q": "test"}
    tool = "search"
    sig = _tool_signature(tool, args)

    # Build exactly _DOOM_LOOP_THRESHOLD entries, but place them BEFORE the window
    old_entries = [{"name": tool, "_signature": sig}] * _DOOM_LOOP_THRESHOLD
    # Fill the window with unrelated results so the old entries are out of range
    filler = [{"name": "other", "_signature": _tool_signature("other", {})}] * _DOOM_LOOP_WINDOW
    prior = old_entries + filler

    # The old entries are outside the window — no doom loop
    _check_doom_loop(tool, args, prior)


def test_check_doom_loop_empty_prior():
    """No error when there are no prior results."""
    _check_doom_loop("tool", {"arg": "val"}, [])


def test_check_doom_loop_error_message_contains_tool_name():
    """Error message mentions the tool name."""
    prior = _make_prior_results("calendar.list_events", {"start": "x"}, _DOOM_LOOP_THRESHOLD)
    with pytest.raises(DoomLoopError, match="calendar.list_events"):
        _check_doom_loop("calendar.list_events", {"start": "x"}, prior)


# ---------------------------------------------------------------------------
# Integration: tool_node returns error result (no raise propagates)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_node_returns_doom_loop_error_result():
    """tool_node returns an error dict (not raises) when doom loop is detected."""
    from noa.orchestrator.nodes.tools import set_gateway, tool_node
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    gw = ToolGateway()

    class FakeAdapter:
        async def execute(self, req: ToolRequest) -> ToolResponse:
            return ToolResponse(result={"ok": True}, provider="fake")

    gw.register("search", FakeAdapter())

    # Set the gateway
    set_gateway(gw)

    tool = "search"
    func = "web_search"
    args = {"q": "repeated query"}
    qualified = f"{tool}.{func}"
    sig = _tool_signature(qualified, args)

    # Build prior_results already at threshold - 1 (so this call would be #threshold)
    prior = _make_prior_results(qualified, args, _DOOM_LOOP_THRESHOLD)

    state = {
        "tool_calls": [{"tool": tool, "function": func, "args": args}],
        "tool_results": prior,
        "tool_rounds": 0,
        "messages": [],
        "approvals_enabled": False,  # Skip policy checks
        "user_id": None,
        "tool_scope": None,
    }

    result = await tool_node(state)

    tool_results = result["tool_results"]
    assert len(tool_results) == 1
    err_result = tool_results[0]
    assert "error" in err_result
    assert "Doom loop" in err_result["error"]
    assert "search.web_search" in err_result["error"]

    # Clean up
    set_gateway(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_tool_node_no_doom_loop_below_threshold():
    """tool_node dispatches normally when count is below threshold."""
    from noa.orchestrator.nodes.tools import set_gateway, tool_node
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    gw = ToolGateway()
    call_count = 0

    class CountAdapter:
        async def execute(self, req: ToolRequest) -> ToolResponse:
            nonlocal call_count
            call_count += 1
            return ToolResponse(result={"executed": True}, provider="ok")

    gw.register("svc", CountAdapter())
    set_gateway(gw)

    tool = "svc"
    func = "do"
    args = {"x": 1}
    qualified = f"{tool}.{func}"

    # Only _DOOM_LOOP_THRESHOLD - 1 prior results — should NOT trigger
    prior = _make_prior_results(qualified, args, _DOOM_LOOP_THRESHOLD - 1)

    state = {
        "tool_calls": [{"tool": tool, "function": func, "args": args}],
        "tool_results": prior,
        "tool_rounds": 0,
        "messages": [],
        "approvals_enabled": False,
        "user_id": None,
        "tool_scope": None,
    }

    result = await tool_node(state)

    tool_results = result["tool_results"]
    assert len(tool_results) == 1
    assert "error" not in tool_results[0] or "Doom loop" not in tool_results[0].get("error", "")
    assert call_count == 1

    set_gateway(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_tool_node_different_args_no_doom_loop():
    """Different args for the same tool do not trigger doom loop detection."""
    from noa.orchestrator.nodes.tools import set_gateway, tool_node
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    gw = ToolGateway()
    executed = []

    class TrackAdapter:
        async def execute(self, req: ToolRequest) -> ToolResponse:
            executed.append(req.args)
            return ToolResponse(result={"args": req.args}, provider="ok")

    gw.register("svc", TrackAdapter())
    set_gateway(gw)

    tool = "svc"
    func = "do"
    qualified = f"{tool}.{func}"

    # Prior results are all with args {"x": 1}
    prior = _make_prior_results(qualified, {"x": 1}, _DOOM_LOOP_THRESHOLD)

    # Dispatching with different args {"x": 2} — no doom loop
    state = {
        "tool_calls": [{"tool": tool, "function": func, "args": {"x": 2}}],
        "tool_results": prior,
        "tool_rounds": 0,
        "messages": [],
        "approvals_enabled": False,
        "user_id": None,
        "tool_scope": None,
    }

    result = await tool_node(state)
    tool_results = result["tool_results"]

    assert len(tool_results) == 1
    assert "Doom loop" not in tool_results[0].get("error", "")
    assert len(executed) == 1
    assert executed[0] == {"x": 2}

    set_gateway(None)  # type: ignore[arg-type]
