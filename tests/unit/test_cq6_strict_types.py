"""Tests for CQ6: Strict Types & DI Cleanup.

Spec refs: ARCH_INVARIANTS L1-L11, SPEC.md §2.1
Phase plan: CQ6 — Zero Any in public signatures, typed DI helpers.

Verifies:
- app_state module functions accept/return typed objects (not Any)
- get_runner/get_gateway/get_memory_store return typed values or None
- set_router in agent.py accepts ProviderRouter
- chat.py DI helpers return typed values
- drain.py accepts typed runner/health_checker
- TypedDict field access works correctly in agent_node
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.cq6


# ---------------------------------------------------------------------------
# app_state: typed getters return correct types or None
# ---------------------------------------------------------------------------


class TestAppStateTypedGetters:
    """Verify app_state returns typed objects from proper set* calls."""

    def setup_method(self) -> None:
        from noa.api import app_state
        app_state.reset_all()

    def teardown_method(self) -> None:
        from noa.api import app_state
        app_state.reset_all()

    def test_get_runner_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_runner
        assert get_runner() is None

    def test_get_gateway_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_gateway
        assert get_gateway() is None

    def test_get_memory_store_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_memory_store
        assert get_memory_store() is None

    def test_get_apns_service_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_apns_service
        assert get_apns_service() is None

    def test_get_external_memory_store_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_external_memory_store
        assert get_external_memory_store() is None

    def test_get_provider_router_returns_none_before_set(self) -> None:
        from noa.api.app_state import get_provider_router
        assert get_provider_router() is None

    def test_set_and_get_runner(self) -> None:
        from noa.api.app_state import get_runner, set_runner
        from noa.orchestrator.runner import OrchestratorRunner

        mock_graph = MagicMock()
        runner = OrchestratorRunner(graph=mock_graph)
        set_runner(runner)

        result = get_runner()
        assert result is runner
        assert isinstance(result, OrchestratorRunner)

    def test_set_and_get_gateway(self) -> None:
        from noa.api.app_state import get_gateway, set_gateway
        from noa.tools.gateway import ToolGateway

        gateway = ToolGateway()
        set_gateway(gateway)

        result = get_gateway()
        assert result is gateway
        assert isinstance(result, ToolGateway)

    def test_set_and_get_memory_store(self) -> None:
        from noa.api.app_state import get_memory_store, set_memory_store
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        set_memory_store(store)

        result = get_memory_store()
        assert result is store
        assert isinstance(result, MemoryStore)

    def test_reset_all_clears_typed_fields(self) -> None:
        from noa.api.app_state import (
            get_gateway,
            get_memory_store,
            get_runner,
            reset_all,
            set_gateway,
            set_memory_store,
            set_runner,
        )
        from noa.orchestrator.runner import OrchestratorRunner
        from noa.private_worker.memory_store import MemoryStore
        from noa.tools.gateway import ToolGateway

        set_runner(OrchestratorRunner(graph=MagicMock()))
        set_gateway(ToolGateway())
        set_memory_store(MemoryStore())

        reset_all()

        assert get_runner() is None
        assert get_gateway() is None
        assert get_memory_store() is None

    def test_app_state_backed_runner_retrieval(self) -> None:
        """Runner stored on app.state is returned when app is registered."""
        from fastapi import FastAPI

        from noa.api.app_state import get_runner, set_app, set_runner
        from noa.orchestrator.runner import OrchestratorRunner

        app = FastAPI()
        set_app(app)

        runner = OrchestratorRunner(graph=MagicMock())
        set_runner(runner)

        result = get_runner()
        assert result is runner
        # Also verify it's stored on app.state
        assert hasattr(app.state, "runner")


# ---------------------------------------------------------------------------
# agent.py: set_router / get_router typed
# ---------------------------------------------------------------------------


class TestAgentRouterTyped:
    """Verify agent node router wiring works with real ProviderRouter."""

    def setup_method(self) -> None:
        from noa.orchestrator.nodes import agent as agent_mod
        agent_mod._router = None

    def teardown_method(self) -> None:
        from noa.orchestrator.nodes import agent as agent_mod
        agent_mod._router = None

    def test_get_router_returns_none_before_set(self) -> None:
        from noa.orchestrator.nodes.agent import get_router
        assert get_router() is None

    def test_set_router_stores_and_get_router_retrieves(self) -> None:
        from noa.external_worker.llm.router import ProviderRouter
        from noa.orchestrator.nodes.agent import get_router, set_router

        router = ProviderRouter(
            config={"default_provider": "openai", "providers": {}},
        )
        set_router(router)
        result = get_router()
        assert result is router
        assert isinstance(result, ProviderRouter)

    def test_invoke_llm_raises_without_router(self) -> None:
        import asyncio

        from noa.orchestrator.nodes.agent import invoke_llm

        with pytest.raises(RuntimeError, match="no router configured"):
            # Use asyncio.run() to avoid "no current event loop" errors
            # after async tests have closed the loop.
            asyncio.run(invoke_llm("openai/gpt-4", []))


# ---------------------------------------------------------------------------
# agent_node: max_tokens cast is int (not object)
# ---------------------------------------------------------------------------


class TestAgentNodeMaxTokensCast:
    """Verify max_tokens is always int when passed to invoke_llm."""

    def test_max_tokens_from_state_is_int(self) -> None:
        """agent_node casts state max_tokens to int before invoke_llm."""
        from noa.orchestrator.nodes.agent import agent_node

        # Inspect the source to confirm int cast is present
        source = inspect.getsource(agent_node)
        # The cast/int conversion must be there to prevent "object" type error
        assert "int(state.get" in source or "cast(int," in source, (
            "agent_node must cast max_tokens to int to avoid mypy object error"
        )


# ---------------------------------------------------------------------------
# chat.py: DI helpers return typed values
# ---------------------------------------------------------------------------


class TestChatDIHelpers:
    """Verify chat.py DI helpers return proper typed objects."""

    def setup_method(self) -> None:
        from noa.api import app_state
        app_state.reset_all()

    def teardown_method(self) -> None:
        from noa.api import app_state
        app_state.reset_all()

    def test_get_runner_returns_none_when_not_configured(self) -> None:
        from noa.api.v1.chat import get_runner
        assert get_runner() is None

    def test_get_runner_returns_orchestrator_runner_when_set(self) -> None:
        from noa.api.app_state import set_runner
        from noa.api.v1.chat import get_runner
        from noa.orchestrator.runner import OrchestratorRunner

        runner = OrchestratorRunner(graph=MagicMock())
        set_runner(runner)
        result = get_runner()
        assert isinstance(result, OrchestratorRunner)

    def test_get_health_checker_returns_none_when_not_configured(self) -> None:
        from noa.api.v1.chat import get_health_checker
        assert get_health_checker() is None

    def test_get_session_factory_returns_none_when_not_configured(self) -> None:
        from noa.api.v1.chat import get_session_factory
        assert get_session_factory() is None


# ---------------------------------------------------------------------------
# drain.py: typed constructor
# ---------------------------------------------------------------------------


class TestQueueDrainWorkerTyped:
    """Verify QueueDrainWorker accepts typed runner parameter."""

    def test_drain_worker_accepts_none_runner(self) -> None:
        from noa.queue.drain import QueueDrainWorker
        from noa.queue.health import HealthChecker

        checker = HealthChecker(poll_url="http://localhost:8001/health")
        worker = QueueDrainWorker(
            session_factory=MagicMock(),
            health_checker=checker,
            runner=None,
        )
        assert worker._runner is None

    def test_drain_worker_accepts_orchestrator_runner(self) -> None:
        from noa.orchestrator.runner import OrchestratorRunner
        from noa.queue.drain import QueueDrainWorker
        from noa.queue.health import HealthChecker

        checker = HealthChecker(poll_url="http://localhost:8001/health")
        runner = OrchestratorRunner(graph=MagicMock())
        worker = QueueDrainWorker(
            session_factory=MagicMock(),
            health_checker=checker,
            runner=runner,
        )
        assert worker._runner is runner
        assert isinstance(worker._runner, OrchestratorRunner)


# ---------------------------------------------------------------------------
# TypedDict access: approvals_enabled cast in tools.py
# ---------------------------------------------------------------------------


class TestToolsNodeTypeAccess:
    """Verify TypedDict access patterns are correct after CQ6 cleanup."""

    def test_approvals_enabled_cast_to_bool(self) -> None:
        """tools.py must use bool() cast, not bare .get() assignment."""
        from noa.orchestrator.nodes import tools as tools_mod

        source = inspect.getsource(tools_mod)
        # After removing type: ignore, we should use bool() cast
        assert "bool(state.get" in source, (
            "tools.py must use bool() cast for approvals_enabled TypedDict access"
        )

    def test_no_unused_type_ignore_comments(self) -> None:
        """Verify the # type: ignore[assignment] comments are removed."""
        from noa.orchestrator.nodes import tools as tools_mod

        source = inspect.getsource(tools_mod)
        # Should not have the old type: ignore patterns
        assert "type: ignore[assignment]" not in source, (
            "tools.py should not have type: ignore[assignment] after CQ6 cleanup"
        )
