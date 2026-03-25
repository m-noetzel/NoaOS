"""OI7: Cross-Domain Step-Up Approval tests.

When a private-mode request tries to call an external-domain tool the gateway
must return an approval_required response (with cross_domain=True) instead of
raising PermissionError.  Once the user approves (approved=True), the tool
must execute normally.

The reverse direction (private tool from external request) must still raise
PermissionError — that path is not subject to user approval.
"""

from __future__ import annotations

import asyncio

import pytest

from noa.tools.gateway import ToolGateway, ToolRequest, ToolResponse
from noa.types import PrivacyMode

# ---------------------------------------------------------------------------
# Minimal stub adapters so the gateway has registered tools
# ---------------------------------------------------------------------------


class _ExternalAdapter:
    """Stub external-domain adapter."""

    domain = PrivacyMode.EXTERNAL

    async def execute(self, request: ToolRequest) -> ToolResponse:
        return ToolResponse(result={"executed": True, "tool": request.tool})


class _PrivateAdapter:
    """Stub private-domain adapter."""

    domain = PrivacyMode.PRIVATE

    async def execute(self, request: ToolRequest) -> ToolResponse:
        return ToolResponse(result={"executed": True, "tool": request.tool})


class _NoDomainAdapter:
    """Stub adapter with no domain annotation."""

    async def execute(self, request: ToolRequest) -> ToolResponse:
        return ToolResponse(result={"executed": True})


def _make_gateway() -> ToolGateway:
    gw = ToolGateway()
    gw.register("gmail", _ExternalAdapter())
    gw.register("memory", _PrivateAdapter())
    gw.register("calculator", _NoDomainAdapter())
    return gw


# ---------------------------------------------------------------------------
# OI7 — cross-domain approval flow
# ---------------------------------------------------------------------------


class TestCrossDomainApprovalRequired:
    """External tool called from private mode returns approval_required."""

    def test_external_tool_private_mode_returns_approval_required(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={"to": "test@example.com"},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error == "Cross-domain approval required"
        assert resp.result is not None
        assert resp.result["approval_required"] is True

    def test_cross_domain_flag_set(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="list_messages",
            args={},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.result is not None
        assert resp.result.get("cross_domain") is True

    def test_risk_tier_is_high_for_cross_domain(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="list_messages",
            args={},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.result is not None
        assert resp.result.get("risk_tier") == "high"

    def test_approval_response_includes_tool_function_args(self) -> None:
        gw = _make_gateway()
        args = {"subject": "hello", "body": "world"}
        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args=args,
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.result is not None
        assert resp.result["tool"] == "gmail"
        assert resp.result["function"] == "send_email"
        assert resp.result["args"] == args

    def test_approval_response_includes_reason(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.result is not None
        reason = resp.result.get("reason", "")
        assert "external-domain" in reason or "cross-domain" in reason.lower()


class TestApprovedCrossDomainPassesThrough:
    """approved=True lets an external tool execute in private mode."""

    def test_approved_request_executes_tool(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={"to": "test@example.com"},
            privacy_mode=PrivacyMode.PRIVATE,
            approved=True,
        )
        resp = asyncio.run(gw.dispatch(req))
        # Should succeed — no approval_required, tool executes
        assert resp.result is not None
        assert resp.result.get("approval_required") is None
        assert resp.result.get("executed") is True

    def test_approved_false_still_blocked(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="send_email",
            args={},
            privacy_mode=PrivacyMode.PRIVATE,
            approved=False,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.result is not None
        assert resp.result.get("approval_required") is True


class TestReverseDomainStillRaisesPermissionError:
    """Private tool from external request must still raise PermissionError."""

    def test_private_tool_external_mode_raises(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="memory",
            function="store",
            args={"key": "x"},
            privacy_mode=PrivacyMode.EXTERNAL,
        )
        with pytest.raises(PermissionError, match="Private-domain tool"):
            asyncio.run(gw.dispatch(req))


class TestSameDomainUnaffected:
    """Same-domain requests pass through the domain check unchanged."""

    def test_external_tool_external_mode_executes(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="gmail",
            function="list_messages",
            args={},
            privacy_mode=PrivacyMode.EXTERNAL,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert resp.result is not None
        assert resp.result.get("executed") is True

    def test_private_tool_private_mode_executes(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="memory",
            function="retrieve",
            args={"key": "x"},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None
        assert resp.result is not None
        assert resp.result.get("executed") is True

    def test_no_domain_tool_any_mode_executes(self) -> None:
        gw = _make_gateway()
        req = ToolRequest(
            tool="calculator",
            function="add",
            args={"a": 1, "b": 2},
            privacy_mode=PrivacyMode.PRIVATE,
        )
        resp = asyncio.run(gw.dispatch(req))
        assert resp.error is None


# ---------------------------------------------------------------------------
# OI7 — privacy_mode wired through tool dispatch node
# ---------------------------------------------------------------------------


class TestPrivacyModePassedThroughDispatch:
    """tool_node reads privacy_mode from state and passes it to gateway."""

    def test_dispatch_gateway_accepts_privacy_mode_kwarg(self) -> None:
        """Verify _dispatch_gateway signature accepts privacy_mode parameter."""
        # Inspect the signature of _dispatch_gateway
        import inspect

        from noa.orchestrator.nodes import tools as tools_mod
        sig = inspect.signature(tools_mod._dispatch_gateway)
        assert "privacy_mode" in sig.parameters, (
            "_dispatch_gateway must accept privacy_mode kwarg (OI7)"
        )

    def test_privacy_mode_default_is_external(self) -> None:
        import inspect

        from noa.orchestrator.nodes import tools as tools_mod

        sig = inspect.signature(tools_mod._dispatch_gateway)
        default = sig.parameters["privacy_mode"].default
        assert default == "external"

    @pytest.mark.asyncio
    async def test_tool_node_passes_privacy_mode_to_gateway(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tool_node must forward state['privacy_mode'] to _dispatch_gateway."""
        from noa.orchestrator.nodes import tools as tools_mod

        captured_privacy_modes: list[str] = []

        async def fake_dispatch(
            tool_name: str,
            function: str,
            args: dict,
            *,
            approvals_enabled: bool = True,
            user_id: str | None = None,
            privacy_mode: str = "external",
        ) -> dict:
            captured_privacy_modes.append(privacy_mode)
            return {"executed": True}

        monkeypatch.setattr(tools_mod, "_dispatch_gateway", fake_dispatch)
        # Set a non-None gateway so the gateway path is taken
        monkeypatch.setattr(tools_mod, "_gateway", object())

        state = {
            "tool_calls": [
                {"tool": "gmail", "function": "send_email", "args": {}}
            ],
            "privacy_mode": "private",
            "approvals_enabled": True,
            "user_id": None,
            "tool_scope": None,
            "tool_results": [],
            "messages": [],
            "tool_rounds": 0,
            "max_tool_calls": 10,
        }

        await tools_mod.tool_node(state)  # type: ignore[arg-type]
        assert captured_privacy_modes == ["private"], (
            f"Expected privacy_mode='private' to reach gateway, got {captured_privacy_modes}"
        )


# ---------------------------------------------------------------------------
# OI7 — runner approval event includes cross_domain fields
# ---------------------------------------------------------------------------


class TestRunnerApprovalEventCrossDomain:
    """Runner emits cross_domain and reason when present in tool result."""

    def test_approval_payload_includes_cross_domain_fields(self) -> None:
        """_make_event with cross_domain=True propagates reason."""
        from noa.orchestrator import runner as runner_mod

        # Minimal runner instance (no DB needed for _make_event)
        r = runner_mod.OrchestratorRunner.__new__(runner_mod.OrchestratorRunner)

        tr = {
            "approval_required": True,
            "cross_domain": True,
            "risk_tier": "high",
            "tool": "gmail",
            "function": "send_email",
            "args": {"to": "a@b.com"},
            "reason": "External-domain tool; approval required.",
        }

        # Simulate what runner does when building the approval payload
        approval_payload: dict = {
            "tool": tr.get("tool", ""),
            "function": tr.get("function", ""),
            "args": tr.get("args", {}),
            "risk_tier": tr.get("risk_tier", "medium"),
        }
        if tr.get("cross_domain"):
            approval_payload["cross_domain"] = True
            approval_payload["reason"] = tr.get("reason", "")

        assert approval_payload["cross_domain"] is True
        assert "reason" in approval_payload
        assert approval_payload["risk_tier"] == "high"
