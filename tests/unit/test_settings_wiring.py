"""Tests for W22-H1 (agent limit settings wiring) and W22-H2 (approvals toggle).

Verifies that:
- agent_node uses max_tool_calls from AgentState (W22-H1)
- route_after_tools uses max_retries from AgentState (W22-H1)
- ToolGateway skips approval check when approvals_enabled=False (W22-H2)
- ToolGateway enforces approval check when approvals_enabled=True (W22-H2)
- UpdateSettingsRequest Pydantic validation rejects out-of-range values (W22-M2)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# W22-H1: agent_node uses max_tool_calls from state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_node_respects_max_tool_calls_from_state() -> None:
    """agent_node must cap tool calls using max_tool_calls from state, not the constant."""
    from noa.orchestrator.nodes.agent import agent_node

    # LLM returns 5 tool calls; state allows only 2
    mock_response = MagicMock()
    mock_response.tool_calls = [
        {"name": f"tool_{i}", "arguments": {}} for i in range(5)
    ]
    mock_response.content = ""
    mock_response.usage = {}
    mock_response.provider = "test"
    mock_response.model = "test-model"

    state: dict = {
        "messages": [{"role": "user", "content": "hi"}],
        "selected_model": "openai/gpt-4.1-mini",
        "privacy_mode": "external",
        "available_tools": [],
        "max_tokens": 4096,
        "max_tool_calls": 2,  # user-configured limit
        "max_retries": 3,
        "timeout_seconds": 120,
        "approvals_enabled": True,
        "model_config": {},
        "tool_rounds": 0,
        "llm_usage": [],
        "total_cost": 0.0,
    }

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        return_value=mock_response,
    ):
        result = await agent_node(state)  # type: ignore[arg-type]

    # Only 2 calls should pass through (max_tool_calls=2)
    assert len(result["tool_calls"]) == 2


@pytest.mark.asyncio
async def test_agent_node_fallback_to_constant_when_no_state_value() -> None:
    """agent_node falls back to MAX_TOOL_CALLS constant when max_tool_calls not in state."""
    from noa.orchestrator.nodes.agent import MAX_TOOL_CALLS, agent_node

    # Create exactly MAX_TOOL_CALLS + 2 tool calls to verify the constant cap
    mock_response = MagicMock()
    mock_response.tool_calls = [
        {"name": f"tool_{i}", "arguments": {}} for i in range(MAX_TOOL_CALLS + 2)
    ]
    mock_response.content = ""
    mock_response.usage = {}
    mock_response.provider = "test"
    mock_response.model = "test-model"

    state: dict = {
        "messages": [{"role": "user", "content": "hi"}],
        "selected_model": "openai/gpt-4.1-mini",
        "privacy_mode": "external",
        "available_tools": [],
        "max_tokens": 4096,
        # max_tool_calls intentionally absent — should fall back to MAX_TOOL_CALLS
        "model_config": {},
        "tool_rounds": 0,
        "llm_usage": [],
        "total_cost": 0.0,
    }

    with patch(
        "noa.orchestrator.nodes.agent.invoke_llm",
        return_value=mock_response,
    ):
        result = await agent_node(state)  # type: ignore[arg-type]

    assert len(result["tool_calls"]) == MAX_TOOL_CALLS


# ---------------------------------------------------------------------------
# W22-H1: route_after_tools uses max_retries from state
# ---------------------------------------------------------------------------


def test_route_after_tools_uses_max_retries_from_state() -> None:
    """route_after_tools must use max_retries from state, not the hardcoded constant."""
    from noa.orchestrator.graph import route_after_tools

    # State with max_retries=1 and tool_rounds=1 → should route to responder
    state_at_limit = {
        "tool_rounds": 1,
        "max_retries": 1,
    }
    assert route_after_tools(state_at_limit) == "responder"

    # State with max_retries=5 and tool_rounds=1 → should still route to agent
    state_under_limit = {
        "tool_rounds": 1,
        "max_retries": 5,
    }
    assert route_after_tools(state_under_limit) == "agent"


def test_route_after_tools_fallback_to_constant() -> None:
    """route_after_tools falls back to MAX_TOOL_ROUNDS when max_retries not in state."""
    from noa.orchestrator.graph import MAX_TOOL_ROUNDS, route_after_tools

    # At the constant cap, should route to responder
    state = {"tool_rounds": MAX_TOOL_ROUNDS}
    assert route_after_tools(state) == "responder"

    # One below, should route to agent
    state_under = {"tool_rounds": MAX_TOOL_ROUNDS - 1}
    assert route_after_tools(state_under) == "agent"


# ---------------------------------------------------------------------------
# W22-H2: Gateway skips approval when approvals_enabled=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_skips_approval_when_disabled() -> None:
    """When approvals_enabled=False, gateway must not check policy engine approval."""
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    # Set up gateway with a policy engine that would normally require approval
    mock_policy = MagicMock()
    mock_policy.classify.return_value = "medium"
    mock_policy.requires_approval.return_value = True
    mock_policy.requires_step_up_auth.return_value = False

    # Adapter that returns success
    mock_adapter = AsyncMock()
    mock_adapter.execute.return_value = ToolResponse(result={"ok": True})

    gw = ToolGateway()
    gw.policy_engine = mock_policy
    gw.register("test_tool", mock_adapter)

    req = ToolRequest(tool="test_tool", function="do_action", args={})

    # With approvals_enabled=False, the policy check is skipped → tool executes
    resp = await gw.dispatch(req, approvals_enabled=False)

    assert resp.error is None
    assert resp.result == {"ok": True}
    # Policy engine must NOT have been consulted
    mock_policy.requires_approval.assert_not_called()
    mock_adapter.execute.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_requires_approval_when_enabled() -> None:
    """When approvals_enabled=True (default), gateway must enforce policy approval."""
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    mock_policy = MagicMock()
    mock_policy.classify.return_value = "medium"
    mock_policy.requires_approval.return_value = True
    mock_policy.requires_step_up_auth.return_value = False

    mock_adapter = AsyncMock()
    mock_adapter.execute.return_value = ToolResponse(result={"ok": True})

    gw = ToolGateway()
    gw.policy_engine = mock_policy
    gw.register("test_tool", mock_adapter)

    req = ToolRequest(tool="test_tool", function="do_action", args={})

    # With approvals_enabled=True (default), policy check runs → approval_required
    resp = await gw.dispatch(req, approvals_enabled=True)

    assert resp.error == "Approval required before executing this action"
    assert resp.result is not None
    assert resp.result.get("approval_required") is True
    # Adapter must NOT have been called (blocked at approval check)
    mock_adapter.execute.assert_not_called()


@pytest.mark.asyncio
async def test_gateway_default_approvals_enabled_enforces_approval() -> None:
    """Gateway.dispatch() default (no approvals_enabled arg) must enforce approvals."""
    from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse

    mock_policy = MagicMock()
    mock_policy.classify.return_value = "high"
    mock_policy.requires_approval.return_value = True
    mock_policy.requires_step_up_auth.return_value = False

    mock_adapter = AsyncMock()
    mock_adapter.execute.return_value = ToolResponse(result={"ok": True})

    gw = ToolGateway()
    gw.policy_engine = mock_policy
    gw.register("test_tool", mock_adapter)

    req = ToolRequest(tool="test_tool", function="risky_action", args={})

    # Default call (no approvals_enabled kwarg) → approval enforced
    resp = await gw.dispatch(req)

    assert resp.error is not None
    assert "Approval required" in resp.error


# ---------------------------------------------------------------------------
# W22-M2: Pydantic validation on agent limit fields
# ---------------------------------------------------------------------------


def test_update_settings_rejects_max_tool_calls_zero() -> None:
    """max_tool_calls=0 must fail validation (ge=1)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(max_tool_calls=0)
    assert "max_tool_calls" in str(exc_info.value)


def test_update_settings_rejects_max_tool_calls_above_limit() -> None:
    """max_tool_calls=51 must fail validation (le=50)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(max_tool_calls=51)
    assert "max_tool_calls" in str(exc_info.value)


def test_update_settings_accepts_valid_max_tool_calls() -> None:
    """max_tool_calls within [1, 50] must pass validation."""
    from noa.api.v1.settings import UpdateSettingsRequest

    req = UpdateSettingsRequest(max_tool_calls=1)
    assert req.max_tool_calls == 1

    req2 = UpdateSettingsRequest(max_tool_calls=50)
    assert req2.max_tool_calls == 50


def test_update_settings_rejects_max_retries_zero() -> None:
    """max_retries=0 must fail validation (ge=1)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(max_retries=0)
    assert "max_retries" in str(exc_info.value)


def test_update_settings_rejects_max_retries_above_limit() -> None:
    """max_retries=11 must fail validation (le=10)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(max_retries=11)
    assert "max_retries" in str(exc_info.value)


def test_update_settings_rejects_timeout_below_minimum() -> None:
    """timeout_seconds=5 must fail validation (ge=10)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(timeout_seconds=5)
    assert "timeout_seconds" in str(exc_info.value)


def test_update_settings_rejects_timeout_above_maximum() -> None:
    """timeout_seconds=601 must fail validation (le=600)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    with pytest.raises(ValidationError) as exc_info:
        UpdateSettingsRequest(timeout_seconds=601)
    assert "timeout_seconds" in str(exc_info.value)


def test_update_settings_accepts_valid_timeout() -> None:
    """timeout_seconds within [10, 600] must pass validation."""
    from noa.api.v1.settings import UpdateSettingsRequest

    req = UpdateSettingsRequest(timeout_seconds=10)
    assert req.timeout_seconds == 10

    req2 = UpdateSettingsRequest(timeout_seconds=600)
    assert req2.timeout_seconds == 600


def test_update_settings_all_fields_none_is_valid() -> None:
    """All optional fields set to None must be valid (no-op partial update)."""
    from noa.api.v1.settings import UpdateSettingsRequest

    req = UpdateSettingsRequest()
    assert req.max_tool_calls is None
    assert req.max_retries is None
    assert req.timeout_seconds is None
    assert req.approvals_enabled is None
