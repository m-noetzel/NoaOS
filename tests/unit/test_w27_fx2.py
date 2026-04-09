"""W27-FX2 regression tests — CQ9-M1 approval fix, Ollama temperature, dead callback removal.

These tests verify that the three fixes from W27-FX2 remain in place:
1. CQ9-M1: _create_approval() populates tool_name and function_name columns
2. ADHOC-M2: OllamaClient uses temperature: float | None = None (omits when None)
3. W26-L3: Dead _stream_callback / set_stream_callback / get_stream_callback removed from agent.py
"""

from __future__ import annotations

import ast
import inspect
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. Ollama temperature default tests (ADHOC-M2)
# ---------------------------------------------------------------------------

class TestOllamaTemperatureDefault:
    """OllamaClient must default temperature to None and omit it from requests."""

    def test_complete_signature_defaults_to_none(self) -> None:
        """complete() signature has temperature: float | None = None."""
        from noa.llm.providers.ollama import OllamaClient

        sig = inspect.signature(OllamaClient.complete)
        param = sig.parameters["temperature"]
        assert param.default is None, (
            f"OllamaClient.complete temperature default should be None, got {param.default!r}"
        )

    def test_build_request_omits_temperature_when_none(self) -> None:
        """build_request() must NOT include 'temperature' key in options when None."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(model_manifest={"test-model": "test"})
        req = client.build_request(
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            temperature=None,
        )
        assert "temperature" not in req["options"], (
            "temperature=None should not appear in request options"
        )

    def test_build_request_includes_temperature_when_set(self) -> None:
        """build_request() includes temperature in options when explicitly set."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(model_manifest={"test-model": "test"})
        req = client.build_request(
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            temperature=0.5,
        )
        assert req["options"]["temperature"] == 0.5

    def test_complete_stream_signature_defaults_to_none(self) -> None:
        """complete_stream() also defaults temperature to None."""
        from noa.llm.providers.ollama import OllamaClient

        sig = inspect.signature(OllamaClient.complete_stream)
        param = sig.parameters["temperature"]
        assert param.default is None

    def test_build_request_no_temperature_zero_default(self) -> None:
        """Calling build_request with no temperature arg must not inject temperature=0."""
        from noa.llm.providers.ollama import OllamaClient

        client = OllamaClient(model_manifest={"m": "m"})
        req = client.build_request(
            messages=[{"role": "user", "content": "test"}],
            model="m",
        )
        # temperature should be absent, not present as 0 or 0.7
        assert "temperature" not in req["options"]


# ---------------------------------------------------------------------------
# 2. Dead callback removal tests (W26-L3)
# ---------------------------------------------------------------------------

class TestDeadCallbackRemoval:
    """agent.py must not contain module-level _stream_callback or related functions."""

    def _agent_source(self) -> str:
        import noa.orchestrator.nodes.agent as mod
        return inspect.getsource(mod)

    def test_no_stream_callback_global(self) -> None:
        """No module-level _stream_callback variable in agent.py."""
        src = self._agent_source()
        tree = ast.parse(src)
        top_level_names = {
            node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
        }
        assert "_stream_callback" not in top_level_names, (
            "Dead _stream_callback global still present in agent.py"
        )

    def test_no_set_stream_callback_function(self) -> None:
        """set_stream_callback() must not exist in agent.py."""
        import noa.orchestrator.nodes.agent as mod
        assert not hasattr(mod, "set_stream_callback"), (
            "Dead set_stream_callback() still present in agent.py"
        )

    def test_no_get_stream_callback_function(self) -> None:
        """get_stream_callback() must not exist in agent.py."""
        import noa.orchestrator.nodes.agent as mod
        assert not hasattr(mod, "get_stream_callback"), (
            "Dead get_stream_callback() still present in agent.py"
        )

    def test_token_callback_from_state_only(self) -> None:
        """agent_node must get token_callback from state, not a module global."""
        src = self._agent_source()
        # The only way cb should be obtained is from state.get("token_callback")
        assert 'state.get("token_callback")' in src or "state.get('token_callback')" in src, (
            "agent_node should read token_callback from state dict"
        )
        # Must NOT reference _stream_callback as fallback
        assert "or _stream_callback" not in src, (
            "Dead fallback 'or _stream_callback' still present in agent.py"
        )


# ---------------------------------------------------------------------------
# 3. CQ9-M1: Approval creation populates tool_name / function_name
# ---------------------------------------------------------------------------

class TestApprovalFieldsPopulated:
    """_create_approval() must populate tool_name and function_name columns."""

    @pytest.mark.asyncio
    async def test_create_approval_sets_tool_name(self) -> None:
        """_create_approval passes tool_name to the Approval model."""
        captured: dict[str, Any] = {}

        # Patch _get_session_factory to provide a mock DB session
        mock_session = AsyncMock()

        def capture_add(obj: Any) -> None:
            captured["tool_name"] = obj.tool_name
            captured["function_name"] = obj.function_name

        mock_session.add = MagicMock(side_effect=capture_add)

        # Create an async context manager mock for the session factory
        mock_factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = ctx

        # Mock transactional context manager
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_transactional(session: Any) -> Any:
            yield session

        with (
            patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory),
            patch("noa.db.transaction.transactional", mock_transactional),
        ):
            from noa.api.v1.chat import _create_approval

            result = await _create_approval(
                user_id=str(uuid.uuid4()),
                run_id=str(uuid.uuid4()),
                payload={
                    "tool": "google_calendar",
                    "function": "list_events",
                    "args": {"max_results": 10},
                    "risk_tier": "medium",
                },
            )

        assert captured.get("tool_name") == "google_calendar", (
            f"tool_name should be 'google_calendar', got {captured.get('tool_name')!r}"
        )
        assert captured.get("function_name") == "list_events", (
            f"function_name should be 'list_events', got {captured.get('function_name')!r}"
        )

    def test_approval_model_has_tool_name_column(self) -> None:
        """Approval model has tool_name and function_name mapped columns."""
        from noa.db.models.approval import Approval

        mapper = inspect.getmembers(Approval)
        column_names = [name for name, _ in mapper]
        assert "tool_name" in column_names, "Approval model missing tool_name column"
        assert "function_name" in column_names, "Approval model missing function_name column"
