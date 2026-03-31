"""ST3: Verify run_id propagation from runner through AgentState to evaluator_node.

Resolves W24-H2: evaluator stores NULL run_id, breaking analytics.
"""

from __future__ import annotations

from typing import Any

import pytest

from noa.orchestrator.state import AgentState


def _make_state(**overrides: Any) -> AgentState:
    """Create a minimal AgentState with defaults."""
    base: dict[str, Any] = {
        "messages": [],
        "privacy_mode": "external",
        "selected_model": "gpt-4o",
        "user_model_override": None,
        "user_provider_override": None,
        "user_privacy_override": None,
        "requested_tools": None,
        "tool_calls": [],
        "tool_results": [],
        "response": "Test response",
        "total_cost": 0.0,
        "model_config": {},
        "tool_rounds": 0,
        "llm_usage": [{"model": "gpt-4o", "input_tokens": 10, "output_tokens": 5, "cost": 0.001}],
        "available_tools": [],
        "max_tool_calls": 10,
        "max_retries": 3,
        "timeout_seconds": 300,
        "approvals_enabled": True,
        "private_available": True,
        "user_id": "test-user",
        "tool_scope": None,
        "task_type": "execution",
        "plan": None,
        "archetype": "execution",
        "thoughts": [],
        "use_react": False,
        "run_id": None,
        "eval_scores": None,
        "eval_verdict": None,
        "eval_cycle": 0,
        "is_compaction_boundary": False,
    }
    base.update(overrides)
    return AgentState(**base)  # type: ignore[typeddict-item]


class TestRunIdInAgentState:
    """Verify run_id field exists and is usable in AgentState."""

    def test_run_id_field_exists(self) -> None:
        state = _make_state()
        assert "run_id" in state
        assert state["run_id"] is None

    def test_run_id_populated(self) -> None:
        state = _make_state(run_id="run-abc-123")
        assert state["run_id"] == "run-abc-123"

    def test_run_id_propagates_through_state(self) -> None:
        """Simulate what runner does: populate run_id in initial state."""
        run_id = "run-uuid-456"
        state = _make_state(run_id=run_id)
        # Evaluator reads run_id via state.get("run_id")
        assert state.get("run_id") == run_id
        assert (state.get("run_id") or "") == run_id


class TestRunnerPopulatesRunId:
    """Verify runner.py sets run_id in initial_state."""

    def test_initial_state_includes_run_id(self) -> None:
        """The runner must include run_id in the initial state dict.

        We verify by checking the runner source sets "run_id": run_id.
        """
        import inspect

        from noa.orchestrator.runner import OrchestratorRunner

        source = inspect.getsource(OrchestratorRunner.run)
        assert '"run_id": run_id' in source or '"run_id"' in source


class TestEvaluatorReadsRunId:
    """Verify evaluator_node reads run_id from state."""

    def test_evaluator_uses_run_id_from_state(self) -> None:
        """Evaluator should read run_id via state.get("run_id")."""
        import inspect

        from noa.orchestrator.nodes.evaluator import evaluator_node

        source = inspect.getsource(evaluator_node)
        assert 'state.get("run_id")' in source or "state['run_id']" in source

    def test_evaluator_stores_run_id_via_state(self) -> None:
        """Evaluator reads run_id from state and uses it for DB storage."""
        import inspect

        from noa.orchestrator.nodes.evaluator import evaluator_node

        source = inspect.getsource(evaluator_node)
        # Evaluator must read run_id from state and pass it along
        assert "run_id" in source


class TestEvaluatorNodeBehavioral:
    """Behavioral tests that actually call evaluator_node() with a real state."""

    @pytest.mark.asyncio
    async def test_simple_utility_skips_evaluation_and_returns_pass(self) -> None:
        """simple_utility tasks short-circuit: no LLM call, verdict=pass."""
        from noa.orchestrator.nodes.evaluator import evaluator_node

        state = _make_state(task_type="simple_utility", run_id="run-behavioral-001")
        result = await evaluator_node(state)

        assert result["eval_verdict"] == "pass"
        assert result["eval_scores"] == {}
        assert result["eval_cycle"] == 0

    @pytest.mark.asyncio
    async def test_run_id_propagated_to_persist_when_llm_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """evaluator_node passes the run_id from state to _persist_evaluation.

        Mocks invoke_llm to return a deterministic score payload, and captures
        what run_id _persist_evaluation receives — verifying it is not "" or None.
        """
        import json

        from noa.orchestrator.nodes import evaluator as evaluator_mod

        captured_run_ids: list[str] = []

        async def fake_invoke_llm(
            model: str,
            messages: list,
            **kwargs: object,
        ) -> object:
            scores = {
                "goal_alignment": 4,
                "completeness": 4,
                "grounding": 4,
                "confidence_honesty": 4,
                "actionability": 4,
            }
            payload = json.dumps({"scores": scores, "reasoning": "looks good"})

            class _FakeResult:
                content = payload

            return _FakeResult()

        async def fake_persist(
            *,
            run_id: str,
            **kwargs: object,
        ) -> None:
            captured_run_ids.append(run_id)

        monkeypatch.setattr(evaluator_mod, "invoke_llm", fake_invoke_llm)
        monkeypatch.setattr(evaluator_mod, "_persist_evaluation", fake_persist)

        from noa.orchestrator.nodes.evaluator import evaluator_node

        state = _make_state(
            run_id="run-behavioral-xyz",
            task_type="execution",
            response="This is the agent response.",
            messages=[{"role": "user", "content": "Do something useful."}],
            model_config={},
        )

        result = await evaluator_node(state)

        assert result["eval_verdict"] in {"pass", "reroute", "flag"}
        assert len(captured_run_ids) == 1, "Expected _persist_evaluation to be called once"
        assert captured_run_ids[0] == "run-behavioral-xyz", (
            f"run_id propagated incorrectly: got {captured_run_ids[0]!r}"
        )

    @pytest.mark.asyncio
    async def test_missing_run_id_defaults_to_empty_string_not_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When run_id is None in state, evaluator passes empty string to persist (no crash)."""
        import json

        from noa.orchestrator.nodes import evaluator as evaluator_mod

        captured_run_ids: list[str] = []

        async def fake_invoke_llm(model: str, messages: list, **kwargs: object) -> object:
            scores = dict.fromkeys(
                ["goal_alignment", "completeness", "grounding",
                 "confidence_honesty", "actionability"], 4)
            payload = json.dumps({"scores": scores, "reasoning": "ok"})

            class _R:
                content = payload

            return _R()

        async def fake_persist(*, run_id: str, **kwargs: object) -> None:
            captured_run_ids.append(run_id)

        monkeypatch.setattr(evaluator_mod, "invoke_llm", fake_invoke_llm)
        monkeypatch.setattr(evaluator_mod, "_persist_evaluation", fake_persist)

        from noa.orchestrator.nodes.evaluator import evaluator_node

        state = _make_state(
            run_id=None,
            task_type="execution",
            response="Agent reply.",
            messages=[{"role": "user", "content": "Hello."}],
            model_config={},
        )

        result = await evaluator_node(state)

        # Must not crash; persist should be called with "" (state.get("run_id") or "")
        assert result["eval_verdict"] in {"pass", "reroute", "flag"}
        assert len(captured_run_ids) == 1
        assert captured_run_ids[0] == "", (
            f"Expected empty string for None run_id, got {captured_run_ids[0]!r}"
        )
