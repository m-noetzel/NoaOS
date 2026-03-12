"""Tests for PR4: Backend Security & Robustness.

Covers:
  BE-H1: Credentials persisted to DB; ProviderRouter reloaded on credential update.
  BE-M3: Artifact path traversal guard in GET /artifacts/{id}/download.
  BE-M2: MemoryStore._persist is private; public persist() is the only external API.
  BE-M4: Structured log context (user_id, run_id, trace_id) in orchestrator logs.

Spec refs: SPEC.md §11.1, §13.2, §22.1
"""

# ruff: noqa: S101, S105, S106

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.pr4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_user(user_id: uuid.UUID | None = None) -> Any:
    from noa.auth.middleware import AuthUser

    return AuthUser(user_id=user_id or uuid.uuid4())


# ---------------------------------------------------------------------------
# BE-M3: Artifact path traversal guard
# ---------------------------------------------------------------------------


class TestArtifactPathTraversalGuard:
    """BE-M3: _validate_artifact_path must reject traversal attempts."""

    def _validate(self, ref: str) -> Path:
        from noa.api.v1.artifacts import _validate_artifact_path

        return _validate_artifact_path(ref)

    def test_valid_path_inside_artifacts_dir(self, tmp_path: Path) -> None:
        """A path inside the configured base dir resolves successfully."""
        from noa.api.v1 import artifacts as artifacts_mod

        original_base = artifacts_mod._ARTIFACTS_BASE
        artifacts_mod._ARTIFACTS_BASE = tmp_path
        try:
            target = tmp_path / "run-123" / "report.pdf"
            result = self._validate(str(target))
            assert result == target.resolve()
        finally:
            artifacts_mod._ARTIFACTS_BASE = original_base

    def test_dotdot_in_path_raises_400(self) -> None:
        """Path containing '..' is rejected immediately."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            self._validate("/data/artifacts/../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_relative_dotdot_raises_400(self) -> None:
        """Relative path with '..' that escapes base dir raises 400."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            self._validate("../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_absolute_escape_raises_400(self, tmp_path: Path) -> None:
        """Absolute path outside the base dir is rejected."""
        from fastapi import HTTPException

        from noa.api.v1 import artifacts as artifacts_mod

        original_base = artifacts_mod._ARTIFACTS_BASE
        artifacts_mod._ARTIFACTS_BASE = tmp_path / "artifacts"
        try:
            # /etc/passwd is outside /tmp/.../artifacts
            with pytest.raises(HTTPException) as exc_info:
                self._validate("/etc/passwd")
            assert exc_info.value.status_code == 400
        finally:
            artifacts_mod._ARTIFACTS_BASE = original_base

    def test_encoded_dotdot_in_literal_path(self, tmp_path: Path) -> None:
        """Path containing literal '..' component is blocked."""
        from fastapi import HTTPException

        from noa.api.v1 import artifacts as artifacts_mod

        original_base = artifacts_mod._ARTIFACTS_BASE
        artifacts_mod._ARTIFACTS_BASE = tmp_path
        try:
            # Path that resolves outside tmp_path via ..
            evil = str(tmp_path) + "/legit/../../../etc/shadow"
            with pytest.raises(HTTPException) as exc_info:
                self._validate(evil)
            assert exc_info.value.status_code == 400
        finally:
            artifacts_mod._ARTIFACTS_BASE = original_base

    def test_download_endpoint_guards_traversal(self) -> None:
        """download_artifact endpoint returns 400 for path traversal attempt."""
        import asyncio

        from fastapi import HTTPException
        from sqlalchemy.ext.asyncio import AsyncSession

        from noa.api.v1.artifacts import download_artifact

        # Build a fake artifact row with a malicious storage_ref
        artifact = MagicMock()
        artifact.storage_ref = "/data/artifacts/../../../etc/passwd"
        artifact.mime_type = "application/pdf"
        artifact.name = "report.pdf"

        run = MagicMock()
        run.user_id = uuid.uuid4()

        user = _make_auth_user()
        artifact_id = uuid.uuid4()

        # Mock the DB session to return our evil artifact
        session = MagicMock(spec=AsyncSession)
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=artifact)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=artifact)
        session.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                download_artifact(
                    artifact_id=artifact_id,
                    request=MagicMock(),
                    user=user,
                    session=session,
                )
            )
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# BE-H1: Credential persistence and ProviderRouter reload
# ---------------------------------------------------------------------------


class TestCredentialPersistenceAndRouterReload:
    """BE-H1: PUT /settings persists credentials to DB and reloads ProviderRouter."""

    def test_reload_called_when_anthropic_key_updated(self) -> None:
        """_reload_llm_pipeline_if_needed triggers when anthropic_api_key is updated."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        mock_router = MagicMock()
        mock_router.available_providers = ["anthropic", "ollama"]

        with (
            patch(
                "noa.external_worker.llm.router.ProviderRouter"
            ) as mock_pr_class,
            patch("noa.api.app_state.set_provider_router") as mock_set,
        ):
            mock_pr_class.from_settings.return_value = mock_router

            updates = {"anthropic_api_key": "sk-ant-newkey123"}
            _reload_llm_pipeline_if_needed(updates, full_settings=updates)

            # ProviderRouter should have been rebuilt
            mock_pr_class.from_settings.assert_called_once()
            # And stored in app_state
            mock_set.assert_called_once_with(mock_router)

    def test_reload_called_when_openai_key_updated(self) -> None:
        """_reload_llm_pipeline_if_needed triggers when openai_api_key is updated."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        mock_router = MagicMock()
        mock_router.available_providers = ["openai", "ollama"]

        with (
            patch(
                "noa.external_worker.llm.router.ProviderRouter"
            ) as mock_pr_class,
            patch("noa.api.app_state.set_provider_router") as mock_set,
        ):
            mock_pr_class.from_settings.return_value = mock_router

            updates = {"openai_api_key": "sk-openai-newkey"}
            _reload_llm_pipeline_if_needed(updates, full_settings=updates)

            mock_pr_class.from_settings.assert_called_once()
            mock_set.assert_called_once_with(mock_router)

    def test_no_reload_when_only_budget_updated(self) -> None:
        """_reload_llm_pipeline_if_needed does NOT trigger for non-credential fields."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        with patch(
            "noa.external_worker.llm.router.ProviderRouter"
        ) as mock_pr_class:
            updates = {"budget_daily_usd": 50.0, "default_model": "gpt-4o"}
            _reload_llm_pipeline_if_needed(updates, full_settings=updates)

            mock_pr_class.from_settings.assert_not_called()

    def test_no_reload_for_empty_updates(self) -> None:
        """_reload_llm_pipeline_if_needed is a no-op for empty dict."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        with patch(
            "noa.external_worker.llm.router.ProviderRouter"
        ) as mock_pr_class:
            _reload_llm_pipeline_if_needed({}, full_settings={})
            mock_pr_class.from_settings.assert_not_called()

    def test_reload_tolerates_provider_router_import_failure(self) -> None:
        """_reload_llm_pipeline_if_needed does not raise on import error."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        with patch(
            "noa.external_worker.llm.router.ProviderRouter"
        ) as mock_pr_class:
            mock_pr_class.from_settings.side_effect = RuntimeError("no providers")
            # Must not raise — reload is best-effort
            updates = {"anthropic_api_key": "sk-test"}
            _reload_llm_pipeline_if_needed(updates, full_settings=updates)

    def test_settings_service_persists_credentials_to_db(self) -> None:
        """SettingsService.update_settings stores credentials via repository."""
        import asyncio

        from noa.settings.service import SettingsService

        repo = MagicMock()
        repo.upsert = AsyncMock(return_value=None)
        repo.get_by_user_id = AsyncMock(return_value=None)

        svc = SettingsService(repo)
        user_id = uuid.uuid4()

        asyncio.run(
            svc.update_settings(
                user_id, {"anthropic_api_key": "sk-ant-testkey"}
            )
        )

        # Repository upsert must be called with the credential
        repo.upsert.assert_called_once()
        call_args = repo.upsert.call_args
        assert call_args[0][0] == user_id
        assert "anthropic_api_key" in call_args[0][1]
        assert call_args[0][1]["anthropic_api_key"] == "sk-ant-testkey"

    def test_reload_also_updates_agent_router(self) -> None:
        """_reload_llm_pipeline_if_needed updates the orchestrator agent router too."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        mock_router = MagicMock()
        mock_router.available_providers = ["anthropic"]

        with (
            patch(
                "noa.external_worker.llm.router.ProviderRouter"
            ) as mock_pr_class,
            patch("noa.api.app_state.set_provider_router"),
            patch(
                "noa.orchestrator.nodes.agent.set_router"
            ) as mock_agent_set,
        ):
            mock_pr_class.from_settings.return_value = mock_router

            updates = {"anthropic_api_key": "sk-ant-x"}
            _reload_llm_pipeline_if_needed(updates, full_settings=updates)

            mock_agent_set.assert_called_once_with(mock_router)

    def test_partial_update_preserves_other_credentials(self) -> None:
        """Partial update must not drop credentials for other providers."""
        from noa.api.v1.settings import _reload_llm_pipeline_if_needed

        captured_settings: list[object] = []
        mock_router = MagicMock()
        mock_router.available_providers = ["openai", "anthropic"]

        with (
            patch("noa.external_worker.llm.router.ProviderRouter") as mock_pr_class,
            patch("noa.api.app_state.set_provider_router"),
        ):
            mock_pr_class.from_settings.side_effect = lambda s: (
                captured_settings.append(s) or mock_router
            )

            # Only openai_api_key in the update; anthropic_api_key is in full_settings
            updates = {"openai_api_key": "sk-new-openai"}
            full_settings = {
                "openai_api_key": "sk-new-openai",
                "anthropic_api_key": "sk-ant-existing",
                "ollama_base_url": "http://private-worker:11434",
            }
            _reload_llm_pipeline_if_needed(updates, full_settings=full_settings)

        assert captured_settings, "ProviderRouter.from_settings must be called"
        dyn = captured_settings[0]
        assert dyn.anthropic_api_key == "sk-ant-existing", (
            "anthropic_api_key must be preserved when only openai_api_key was updated"
        )
        assert dyn.openai_api_key == "sk-new-openai"


# ---------------------------------------------------------------------------
# BE-M2: MemoryStore public/private interface
# ---------------------------------------------------------------------------


class TestMemoryStorePublicInterface:
    """BE-M2: MemoryStore exposes persist() publicly; _persist is private."""

    def test_persist_is_public_method(self) -> None:
        """MemoryStore has a public persist() method."""
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        assert hasattr(store, "persist")
        assert callable(store.persist)

    def test_persist_method_is_not_name_mangled(self) -> None:
        """persist() is accessible without underscore prefix."""
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        # Should not raise AttributeError
        store.persist("nonexistent_id")

    def test_persist_writes_to_disk_when_data_dir_set(self, tmp_path: Path) -> None:
        """Public persist() writes a fact JSON file to disk."""
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore(data_dir=tmp_path)
        fact_id = store.store(
            fact="user prefers dark mode",
            category="preference",
            embedding=[0.1, 0.2, 0.3],
            source_thread_id="thread-1",
        )
        assert fact_id is not None

        # File should already exist (store() calls _persist internally)
        fact_file = tmp_path / f"{fact_id}.json"
        assert fact_file.exists()

        # Calling public persist() again is idempotent
        store.persist(fact_id)
        assert fact_file.exists()

    def test_external_code_uses_public_persist(self) -> None:
        """memory.py endpoint uses store.persist(), not store._persist()."""
        import inspect

        import noa.api.v1.memory as memory_mod

        source = inspect.getsource(memory_mod)
        # Should use public persist(), never _persist
        assert "store.persist(" in source or "store.persist (" in source
        assert "store._persist(" not in source

    def test_update_status_persists_via_internal_method(self, tmp_path: Path) -> None:
        """update_status() saves updated facts to disk (internal _persist call)."""
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore(data_dir=tmp_path)
        fact_id = store.store(
            fact="user wakes at 7am",
            category="habit",
            embedding=[0.4, 0.5],
            source_thread_id="thread-2",
            auto_extracted=True,  # starts as 'pending'
        )
        assert fact_id is not None

        fact_file = tmp_path / f"{fact_id}.json"
        assert fact_file.exists()

        # Approve the fact — should persist updated status
        result = store.update_status(fact_id, "approved")
        assert result is True

        # Verify the file was updated
        import json

        data = json.loads(fact_file.read_text())
        assert data["status"] == "approved"

    def test_no_external_calls_to_private_persist_in_codebase(self) -> None:
        """No production code outside memory_store.py calls ._persist() directly."""
        import glob

        src_root = Path(__file__).parent.parent.parent / "src"
        py_files = glob.glob(str(src_root / "**" / "*.py"), recursive=True)

        violations = []
        for path in py_files:
            if "memory_store.py" in path:
                continue  # Internal calls are fine
            try:
                source = Path(path).read_text()
                if "._persist(" in source:
                    violations.append(path)
            except OSError:
                pass

        assert violations == [], (
            f"External code calls ._persist() directly: {violations}. "
            "Use .persist() instead."
        )


# ---------------------------------------------------------------------------
# BE-M4: Structured log context in orchestrator
# ---------------------------------------------------------------------------


class TestStructuredLogContext:
    """BE-M4: OrchestratorRunner emits log records with user_id, run_id, trace_id."""

    def test_runner_run_logs_start_with_context(self) -> None:
        """run() emits a start log with run_id, user_id, trace_id."""
        import asyncio

        from noa.orchestrator.runner import OrchestratorRunner

        run_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        # Build a minimal mock graph
        graph = MagicMock()
        graph.ainvoke = AsyncMock(
            return_value={
                "response": "hello",
                "tool_calls": [],
                "tool_results": [],
                "total_cost": 0.0,
                "llm_usage": [],
            }
        )

        runner = OrchestratorRunner(graph=graph)
        run_svc = MagicMock()
        run_svc.update_status = AsyncMock()
        run_svc.append_event = AsyncMock()

        log_records: list[logging.LogRecord] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_records.append(record)

        handler = CapturingHandler()
        orch_logger = logging.getLogger("noa.orchestrator.runner")
        orch_logger.addHandler(handler)
        orch_logger.setLevel(logging.DEBUG)

        try:
            async def _collect() -> list[dict[str, Any]]:
                events = []
                async for ev in runner.run(
                    message="test",
                    run_service=run_svc,
                    run_id=run_id,
                    user_id=user_id,
                    trace_id=trace_id,
                ):
                    events.append(ev)
                return events

            asyncio.run(_collect())
        finally:
            orch_logger.removeHandler(handler)

        # Find the start log record
        start_records = [r for r in log_records if "Run started" in r.getMessage()]
        assert start_records, "No 'Run started' log record found"
        record = start_records[0]
        # Structured context should be present in the message or extra
        assert run_id in record.getMessage()
        assert user_id in record.getMessage()
        assert trace_id in record.getMessage()

    def test_runner_accepts_user_id_and_trace_id_kwargs(self) -> None:
        """OrchestratorRunner.run() signature accepts user_id and trace_id."""
        import inspect

        from noa.orchestrator.runner import OrchestratorRunner

        sig = inspect.signature(OrchestratorRunner.run)
        params = sig.parameters
        assert "user_id" in params, "run() missing user_id parameter"
        assert "trace_id" in params, "run() missing trace_id parameter"

    def test_runner_log_context_contains_correct_run_id(self) -> None:
        """Log extra dict includes the correct run_id value."""
        import asyncio

        from noa.orchestrator.runner import OrchestratorRunner

        run_id = "run-test-" + str(uuid.uuid4())[:8]
        user_id = "user-test-" + str(uuid.uuid4())[:8]
        trace_id = "trace-test-" + str(uuid.uuid4())[:8]

        graph = MagicMock()
        graph.ainvoke = AsyncMock(
            return_value={
                "response": "done",
                "tool_calls": [],
                "tool_results": [],
                "total_cost": 0.0,
                "llm_usage": [],
            }
        )

        runner = OrchestratorRunner(graph=graph)
        run_svc = MagicMock()
        run_svc.update_status = AsyncMock()
        run_svc.append_event = AsyncMock()

        extra_dicts: list[dict[str, Any]] = []

        class ExtraCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if hasattr(record, "run_id"):
                    extra_dicts.append({
                        "run_id": record.run_id,  # type: ignore[attr-defined]
                        "user_id": getattr(record, "user_id", None),
                        "trace_id": getattr(record, "trace_id", None),
                    })

        handler = ExtraCapture()
        orch_logger = logging.getLogger("noa.orchestrator.runner")
        orch_logger.addHandler(handler)
        orch_logger.setLevel(logging.DEBUG)

        try:
            async def _run() -> None:
                async for _ in runner.run(
                    message="hi",
                    run_service=run_svc,
                    run_id=run_id,
                    user_id=user_id,
                    trace_id=trace_id,
                ):
                    pass

            asyncio.run(_run())
        finally:
            orch_logger.removeHandler(handler)

        assert extra_dicts, "No log records with run_id extra found"
        for d in extra_dicts:
            assert d["run_id"] == run_id
            assert d["user_id"] == user_id
            assert d["trace_id"] == trace_id

    def test_runner_run_completed_log_emitted(self) -> None:
        """run() emits a completion log on success."""
        import asyncio

        from noa.orchestrator.runner import OrchestratorRunner

        run_id = str(uuid.uuid4())
        graph = MagicMock()
        graph.ainvoke = AsyncMock(
            return_value={
                "response": "ok",
                "tool_calls": [],
                "tool_results": [],
                "total_cost": 0.0,
                "llm_usage": [],
            }
        )

        runner = OrchestratorRunner(graph=graph)
        run_svc = MagicMock()
        run_svc.update_status = AsyncMock()
        run_svc.append_event = AsyncMock()

        log_messages: list[str] = []

        class MsgCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_messages.append(record.getMessage())

        handler = MsgCapture()
        orch_logger = logging.getLogger("noa.orchestrator.runner")
        orch_logger.addHandler(handler)
        orch_logger.setLevel(logging.DEBUG)

        try:
            async def _run() -> None:
                async for _ in runner.run(
                    message="hello",
                    run_service=run_svc,
                    run_id=run_id,
                ):
                    pass

            asyncio.run(_run())
        finally:
            orch_logger.removeHandler(handler)

        completed_logs = [m for m in log_messages if "completed" in m.lower()]
        assert completed_logs, f"No completion log found; got: {log_messages}"
