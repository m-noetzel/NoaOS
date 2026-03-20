"""Tests for MC1 — Per-Node Model Configuration.

Verifies:
- node_models stored/retrieved via SettingsService
- runner passes node_models to initial_state model_config
- router_node merges rather than overwrites existing model_config
- classifier reads model from model_config
- settings round-trip (save node_models, read back)
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.orchestrator.nodes.router import router_node
from noa.settings.service import SettingsService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(stored_node_models: str | None = None) -> Any:
    """Create a mock SettingsRepository with optional stored node_models."""
    repo = MagicMock()
    row = MagicMock()
    row.node_models = stored_node_models
    row.scope_overrides = None
    # Set all standard fields used by get_settings
    for field in (
        "default_model", "default_provider", "default_privacy_mode",
        "budget_daily_usd", "budget_monthly_usd", "temperature", "max_tokens",
        "anthropic_api_key", "openai_api_key", "google_client_id",
        "google_client_secret", "notion_token", "tavily_api_key",
        "ollama_base_url", "approvals_enabled", "max_tool_calls",
        "max_retries", "timeout_seconds",
    ):
        setattr(row, field, None)
    repo.get_by_user_id = AsyncMock(return_value=row)
    repo.upsert = AsyncMock(return_value=row)
    return repo


# ---------------------------------------------------------------------------
# SettingsService: node_models round-trip
# ---------------------------------------------------------------------------

class TestNodeModelsSettings:
    """Tests for node_models stored and read via SettingsService."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_none_when_no_node_models(self) -> None:
        """When no node_models stored, get_settings returns None for node_models."""
        repo = _make_repo(stored_node_models=None)
        service = SettingsService(repo)
        result = await service.get_settings(uuid.uuid4())
        assert result.get("node_models") is None

    @pytest.mark.asyncio
    async def test_get_settings_decodes_stored_node_models(self) -> None:
        """Stored JSON node_models blob is decoded to dict on read."""
        stored = json.dumps({"classifier": "openai/gpt-4o-mini", "agent": "openai/gpt-4.1"})
        repo = _make_repo(stored_node_models=stored)
        service = SettingsService(repo)
        result = await service.get_settings(uuid.uuid4())
        nm = result.get("node_models")
        assert nm is not None
        assert nm["classifier"] == "openai/gpt-4o-mini"
        assert nm["agent"] == "openai/gpt-4.1"

    @pytest.mark.asyncio
    async def test_update_settings_encodes_node_models_as_json(self) -> None:
        """update_settings encodes node_models dict to JSON before storing."""
        repo = _make_repo()
        # After upsert, simulate the updated row being returned
        updated_row = MagicMock()
        updated_row.node_models = json.dumps({"classifier": "openai/gpt-4o-mini"})
        updated_row.scope_overrides = None
        for field in (
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature", "max_tokens",
            "anthropic_api_key", "openai_api_key", "google_client_id",
            "google_client_secret", "notion_token", "tavily_api_key",
            "ollama_base_url", "approvals_enabled", "max_tool_calls",
            "max_retries", "timeout_seconds",
        ):
            setattr(updated_row, field, None)
        repo.get_by_user_id = AsyncMock(side_effect=[
            MagicMock(
                node_models=None, scope_overrides=None,
                **dict.fromkeys(("default_model", "default_provider", "default_privacy_mode", "budget_daily_usd", "budget_monthly_usd", "temperature", "max_tokens", "anthropic_api_key", "openai_api_key", "google_client_id", "google_client_secret", "notion_token", "tavily_api_key", "ollama_base_url", "approvals_enabled", "max_tool_calls", "max_retries", "timeout_seconds")),
            ),
            updated_row,
        ])
        service = SettingsService(repo)
        await service.update_settings(
            uuid.uuid4(),
            {"node_models": {"classifier": "openai/gpt-4o-mini"}},
        )
        # Verify upsert was called with JSON-encoded string
        call_args = repo.upsert.call_args
        assert call_args is not None
        fields_passed = call_args[0][1]  # positional arg
        assert "node_models" in fields_passed
        stored_val = fields_passed["node_models"]
        assert isinstance(stored_val, str)
        decoded = json.loads(stored_val)
        assert decoded["classifier"] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_update_settings_strips_none_values_from_node_models(self) -> None:
        """None values in node_models dict are stripped before storing."""
        repo = _make_repo()
        service = SettingsService(repo)
        await service.update_settings(
            uuid.uuid4(),
            {"node_models": {"classifier": "openai/gpt-4o-mini", "agent": None}},
        )
        call_args = repo.upsert.call_args
        assert call_args is not None
        fields_passed = call_args[0][1]
        stored_val = fields_passed["node_models"]
        decoded = json.loads(stored_val)
        assert "agent" not in decoded
        assert decoded["classifier"] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_update_settings_stores_null_when_all_values_are_none(self) -> None:
        """node_models with all-None values stores NULL in DB."""
        repo = _make_repo()
        service = SettingsService(repo)
        await service.update_settings(
            uuid.uuid4(),
            {"node_models": {"classifier": None, "agent": None}},
        )
        call_args = repo.upsert.call_args
        assert call_args is not None
        fields_passed = call_args[0][1]
        assert fields_passed.get("node_models") is None


# ---------------------------------------------------------------------------
# Runner: node_models flows into initial_state
# ---------------------------------------------------------------------------

class TestRunnerNodeModels:
    """Tests that runner passes node_models into the graph's initial state."""

    @pytest.mark.asyncio
    async def test_runner_seeds_model_config_from_node_models(self) -> None:
        """node_models passed to runner appear in initial_state model_config."""
        from noa.orchestrator.runner import OrchestratorRunner

        captured_state: dict[str, Any] = {}

        async def fake_astream(state: dict[str, Any]) -> Any:
            captured_state.update(state)
            # Yield nothing — we just want to capture initial_state
            return
            yield  # make it an async generator

        graph = MagicMock()
        graph.astream = fake_astream
        runner = OrchestratorRunner(graph=graph)

        run_svc = MagicMock()
        run_svc.append_event = AsyncMock()
        run_svc.update_status = AsyncMock()

        node_models = {"classifier": "openai/gpt-4o-mini", "agent": "openai/gpt-4.1"}
        events = []
        async for event in runner.run(
            message="hello",
            run_service=run_svc,
            run_id=str(uuid.uuid4()),
            node_models=node_models,
        ):
            events.append(event)

        assert captured_state.get("model_config") == node_models

    @pytest.mark.asyncio
    async def test_runner_uses_empty_dict_when_no_node_models(self) -> None:
        """When no node_models passed, model_config starts as empty dict."""
        from noa.orchestrator.runner import OrchestratorRunner

        captured_state: dict[str, Any] = {}

        async def fake_astream(state: dict[str, Any]) -> Any:
            captured_state.update(state)
            return
            yield

        graph = MagicMock()
        graph.astream = fake_astream
        runner = OrchestratorRunner(graph=graph)
        run_svc = MagicMock()
        run_svc.append_event = AsyncMock()
        run_svc.update_status = AsyncMock()

        async for _ in runner.run(
            message="hello",
            run_service=run_svc,
            run_id=str(uuid.uuid4()),
        ):
            pass

        assert captured_state.get("model_config") == {}


# ---------------------------------------------------------------------------
# Router node: merge, not overwrite
# ---------------------------------------------------------------------------

class TestRouterNodeMerge:
    """Tests that router_node merges rather than replaces model_config."""

    def _make_state(
        self,
        model_config: dict[str, str] | None = None,
        privacy_mode: str = "external",
    ) -> dict[str, Any]:
        return {
            "messages": [{"role": "user", "content": "hello"}],
            "privacy_mode": privacy_mode,
            "user_privacy_override": privacy_mode,
            "user_model_override": None,
            "user_provider_override": None,
            "model_config": model_config or {},
            "private_available": True,
        }

    def test_router_preserves_user_classifier_model(self) -> None:
        """User-configured classifier model survives router_node pass."""
        state = self._make_state(
            model_config={"classifier": "anthropic/claude-sonnet-4-20250514"},
        )
        result = router_node(state)
        merged = result["model_config"]
        assert merged["classifier"] == "anthropic/claude-sonnet-4-20250514"

    def test_router_enforces_agent_model_from_privacy_mode(self) -> None:
        """Router always sets agent model based on privacy_mode, even if user
        set something different in node_models."""
        state = self._make_state(
            model_config={"agent": "anthropic/claude-opus-4-6"},
            privacy_mode="external",
        )
        result = router_node(state)
        # Router overwrites agent based on privacy_mode resolution
        # (external mode → selected model, not the user's per-node agent override)
        assert "agent" in result["model_config"]

    def test_router_adds_defaults_for_missing_nodes(self) -> None:
        """Router fills in defaults for node keys not present in user config."""
        state = self._make_state(model_config={})
        result = router_node(state)
        merged = result["model_config"]
        # Defaults from ModelConfig should be present
        assert "agent" in merged
        assert "classifier" in merged

    def test_router_merges_user_and_router_configs(self) -> None:
        """User classifier pref + router agent pref coexist in merged config."""
        user_classifier = "openai/gpt-4.1-mini"
        state = self._make_state(
            model_config={"classifier": user_classifier},
            privacy_mode="external",
        )
        result = router_node(state)
        merged = result["model_config"]
        assert merged["classifier"] == user_classifier
        assert "agent" in merged  # Router added agent


# ---------------------------------------------------------------------------
# Classifier node: reads model from model_config
# ---------------------------------------------------------------------------

class TestClassifierNodeUsesModelConfig:
    """Tests that classifier_node reads its model from state.model_config."""

    @pytest.mark.asyncio
    async def test_classifier_uses_model_from_model_config(self) -> None:
        """classifier_node reads classifier model from state model_config."""
        from noa.orchestrator.nodes.classifier import classifier_node

        captured_model: list[str] = []

        async def fake_invoke_llm(
            model: str,
            messages: list[Any],
            **kwargs: Any,
        ) -> Any:
            captured_model.append(model)
            resp = MagicMock()
            resp.content = '{"task_type": "execution", "confidence": 0.9}'
            return resp

        state: dict[str, Any] = {
            "messages": [{"role": "user", "content": "send an email"}],
            "model_config": {"classifier": "anthropic/claude-sonnet-4-20250514"},
        }

        with patch(
            "noa.orchestrator.nodes.classifier.invoke_llm",
            side_effect=fake_invoke_llm,
        ):
            result = await classifier_node(state)

        assert result["task_type"] == "execution"
        assert captured_model == ["anthropic/claude-sonnet-4-20250514"]

    @pytest.mark.asyncio
    async def test_classifier_falls_back_to_default_when_no_model_config(
        self,
    ) -> None:
        """classifier_node falls back to gpt-4o-mini when no model_config."""
        from noa.orchestrator.nodes.classifier import classifier_node

        captured_model: list[str] = []

        async def fake_invoke_llm(model: str, messages: list[Any], **kwargs: Any) -> Any:
            captured_model.append(model)
            resp = MagicMock()
            resp.content = '{"task_type": "simple_utility", "confidence": 0.9}'
            return resp

        state: dict[str, Any] = {
            "messages": [{"role": "user", "content": "what time is it?"}],
            "model_config": {},
        }

        with patch(
            "noa.orchestrator.nodes.classifier.invoke_llm",
            side_effect=fake_invoke_llm,
        ):
            result = await classifier_node(state)

        assert result["task_type"] == "simple_utility"
        assert captured_model == ["openai/gpt-4o-mini"]
