"""Tests for CQ4: PrivacyMode/RiskTier enums and centralized model config.

Spec refs: SPEC.md §4 (privacy domains), §14 (routing), §21 (risk tiers).
Phase: CQ4 — Enums, Config Centralization, Magic Strings.
"""

from __future__ import annotations


class TestPrivacyModeEnum:
    """PrivacyMode StrEnum — backward-compatible string comparisons."""

    def test_private_equals_string(self) -> None:
        """PrivacyMode.PRIVATE must compare equal to the plain string 'private'."""
        from noa.types import PrivacyMode

        assert PrivacyMode.PRIVATE == "private"

    def test_external_equals_string(self) -> None:
        """PrivacyMode.EXTERNAL must compare equal to the plain string 'external'."""
        from noa.types import PrivacyMode

        assert PrivacyMode.EXTERNAL == "external"

    def test_is_str_subtype(self) -> None:
        """PrivacyMode values must be str instances for JSON/DB compatibility."""
        from noa.types import PrivacyMode

        assert isinstance(PrivacyMode.PRIVATE, str)
        assert isinstance(PrivacyMode.EXTERNAL, str)

    def test_usable_in_format_strings(self) -> None:
        """PrivacyMode enum values must work transparently in format strings."""
        from noa.types import PrivacyMode

        assert f"mode={PrivacyMode.PRIVATE}" == "mode=private"
        assert f"mode={PrivacyMode.EXTERNAL}" == "mode=external"

    def test_in_operator_with_plain_strings(self) -> None:
        """PrivacyMode values must work in 'in' membership tests with strings."""
        from noa.types import PrivacyMode

        assert PrivacyMode.PRIVATE in ("private", "external")
        assert "private" in (PrivacyMode.PRIVATE, PrivacyMode.EXTERNAL)


class TestRiskTierEnum:
    """RiskTier StrEnum — backward-compatible string comparisons."""

    def test_values_match_strings(self) -> None:
        """All RiskTier values must equal their corresponding plain strings."""
        from noa.types import RiskTier

        assert RiskTier.LOW == "low"
        assert RiskTier.MEDIUM == "medium"
        assert RiskTier.HIGH == "high"
        assert RiskTier.CRITICAL == "critical"

    def test_is_str_subtype(self) -> None:
        """RiskTier values must be str instances for JSON/DB compatibility."""
        from noa.types import RiskTier

        for tier in RiskTier:
            assert isinstance(tier, str)

    def test_usable_in_membership_check(self) -> None:
        """RiskTier must work in set/tuple membership with plain strings."""
        from noa.types import RiskTier

        approval_tiers = ("medium", "high")
        assert RiskTier.MEDIUM in approval_tiers
        assert RiskTier.HIGH in approval_tiers
        assert RiskTier.LOW not in approval_tiers


class TestPolicyEngineUsesRiskTierEnum:
    """PolicyEngine.classify() must return RiskTier enum values."""

    def test_low_action_returns_risk_tier(self) -> None:
        """web_search (low) → RiskTier.LOW."""
        from noa.policy.engine import PolicyEngine
        from noa.types import RiskTier

        engine = PolicyEngine()
        result = engine.classify("web_search", {})
        assert result == RiskTier.LOW
        assert result == "low"  # backward-compat: StrEnum == plain string

    def test_medium_action_returns_risk_tier(self) -> None:
        """send_email (medium) → RiskTier.MEDIUM."""
        from noa.policy.engine import PolicyEngine
        from noa.types import RiskTier

        engine = PolicyEngine()
        result = engine.classify("send_email", {})
        assert result == RiskTier.MEDIUM
        assert result == "medium"

    def test_high_action_returns_risk_tier(self) -> None:
        """delete_email (high) → RiskTier.HIGH."""
        from noa.policy.engine import PolicyEngine
        from noa.types import RiskTier

        engine = PolicyEngine()
        result = engine.classify("delete_email", {})
        assert result == RiskTier.HIGH
        assert result == "high"

    def test_unknown_action_defaults_to_high(self) -> None:
        """Unknown actions must default to RiskTier.HIGH (fail-safe)."""
        from noa.policy.engine import PolicyEngine
        from noa.types import RiskTier

        engine = PolicyEngine()
        result = engine.classify("__totally_unknown_action__", {})
        assert result == RiskTier.HIGH

    def test_requires_approval_with_enum_values(self) -> None:
        """requires_approval must accept RiskTier enum values."""
        from noa.policy.engine import PolicyEngine
        from noa.types import RiskTier

        engine = PolicyEngine()
        assert engine.requires_approval(RiskTier.MEDIUM) is True
        assert engine.requires_approval(RiskTier.HIGH) is True
        assert engine.requires_approval(RiskTier.LOW) is False


class TestConfigModelDefaults:
    """DEFAULT_EXTERNAL_MODEL and DEFAULT_PRIVATE_MODEL must be exported from config."""

    def test_external_model_is_string(self) -> None:
        """DEFAULT_EXTERNAL_MODEL must be a non-empty string."""
        from noa.config import DEFAULT_EXTERNAL_MODEL

        assert isinstance(DEFAULT_EXTERNAL_MODEL, str)
        assert len(DEFAULT_EXTERNAL_MODEL) > 0

    def test_private_model_is_string(self) -> None:
        """DEFAULT_PRIVATE_MODEL must be a non-empty string."""
        from noa.config import DEFAULT_PRIVATE_MODEL

        assert isinstance(DEFAULT_PRIVATE_MODEL, str)
        assert len(DEFAULT_PRIVATE_MODEL) > 0

    def test_external_model_used_by_model_config(self) -> None:
        """ModelConfig default agent must equal DEFAULT_EXTERNAL_MODEL."""
        from noa.config import DEFAULT_EXTERNAL_MODEL
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig()
        assert cfg.agent == DEFAULT_EXTERNAL_MODEL

    def test_private_model_used_by_model_config(self) -> None:
        """ModelConfig.for_privacy_mode('private') agent must equal DEFAULT_PRIVATE_MODEL."""
        from noa.config import DEFAULT_PRIVATE_MODEL
        from noa.orchestrator.model_config import ModelConfig

        cfg = ModelConfig.for_privacy_mode("private")
        assert cfg.agent == DEFAULT_PRIVATE_MODEL


class TestGatewayDomainIsolation:
    """ToolGateway domain checks must work with PrivacyMode enum values."""

    def test_private_tool_blocked_in_external_mode(self) -> None:
        """Private-domain tool raises PermissionError when request is external."""
        import asyncio

        from noa.tools.gateway import ToolGateway, ToolRequest

        class _PrivateAdapter:
            domain = "private"

            async def call(self, function: str, args: dict) -> str:
                return "ok"

        gw = ToolGateway()
        gw.register("private_tool", _PrivateAdapter())

        req = ToolRequest(
            tool="private_tool", function="call", args={},
            privacy_mode="external",
        )
        with __import__("pytest").raises(PermissionError):
            # Use asyncio.run() instead of get_event_loop() to avoid
            # "no current event loop" errors after async tests close the loop.
            asyncio.run(gw.dispatch(req))

    def test_external_tool_blocked_in_private_mode(self) -> None:
        """External-domain tool raises PermissionError when request is private."""
        import asyncio

        from noa.tools.gateway import ToolGateway, ToolRequest

        class _ExternalAdapter:
            domain = "external"

            async def call(self, function: str, args: dict) -> str:
                return "ok"

        gw = ToolGateway()
        gw.register("external_tool", _ExternalAdapter())

        req = ToolRequest(
            tool="external_tool", function="call", args={},
            privacy_mode="private",
        )
        with __import__("pytest").raises(PermissionError):
            asyncio.run(gw.dispatch(req))
