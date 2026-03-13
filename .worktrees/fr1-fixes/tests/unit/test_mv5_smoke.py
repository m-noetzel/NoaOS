"""MV5: Integration smoke tests — verify all stubs are eliminated.

Phase: Wave 17 MV5 (Integration Smoke & Verification).
Spec refs: SPEC.md §13.2, §17.2, §22.3, §29.6
"""

# ruff: noqa: S101, S105, S106, E501

from __future__ import annotations

import ast
import inspect
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "noa" / "api" / "v1"


# ---------------------------------------------------------------------------
# Stub detector
# ---------------------------------------------------------------------------


def _has_stub_return(source: str) -> list[str]:
    """Return list of stub function names (return empty list literal or TODO raise)."""
    stubs = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return stubs

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for stmt in node.body:
            # Detect: return success_envelope(data=[], ...)
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                for kw in call.keywords:
                    if kw.arg == "data" and isinstance(kw.value, ast.List) and not kw.value.elts:
                        stubs.append(node.name)
            # Detect: raise HTTPException(status_code=404, detail="Artifact not found")
            # where the function body is just that raise with a TODO comment
            if isinstance(stmt, ast.Raise):
                func_source = ast.unparse(stmt)
                if "TODO" in source and "not found" in func_source.lower():
                    stubs.append(f"{node.name}(stub-raise)")

    return list(dict.fromkeys(stubs))  # deduplicate


# ---------------------------------------------------------------------------
# MV5: Per-endpoint stub checks
# ---------------------------------------------------------------------------


class TestNoStubsInApprovals:
    """Verify approvals.py has no stub endpoints."""

    def test_list_pending_approvals_not_stub(self) -> None:
        """list_pending_approvals must query the DB (not return [])."""
        source = (SRC_ROOT / "approvals.py").read_text()
        stubs = _has_stub_return(source)
        assert "list_pending_approvals" not in stubs, (
            "list_pending_approvals is still a stub returning []"
        )

    def test_list_pending_approvals_imports_sqlalchemy(self) -> None:
        """approvals.py must import sqlalchemy.select for real DB queries."""
        source = (SRC_ROOT / "approvals.py").read_text()
        assert "from sqlalchemy" in source, (
            "approvals.py must import sqlalchemy for real DB queries"
        )

    def test_decide_approval_persists(self) -> None:
        """decide_approval must call session.flush() to persist."""
        source = (SRC_ROOT / "approvals.py").read_text()
        assert "session.flush" in source, (
            "decide_approval must flush the session to persist the decision"
        )


class TestNoStubsInMemory:
    """Verify memory.py routes through MemoryStore."""

    def test_list_facts_calls_store(self) -> None:
        """list_facts must call _get_memory_store(), not return hardcoded []."""
        source = (SRC_ROOT / "memory.py").read_text()
        stubs = _has_stub_return(source)
        assert "list_facts" not in stubs, (
            "list_facts is still a stub returning []"
        )

    def test_memory_py_references_store(self) -> None:
        """memory.py must reference _get_memory_store for real data."""
        source = (SRC_ROOT / "memory.py").read_text()
        assert "_get_memory_store" in source, (
            "memory.py must use _get_memory_store to access MemoryStore"
        )


class TestNoStubsInQueue:
    """Verify queue.py queries TaskQueue table."""

    def test_list_queue_not_stub(self) -> None:
        """list_queue must query the DB (not return [])."""
        source = (SRC_ROOT / "queue.py").read_text()
        stubs = _has_stub_return(source)
        assert "list_queue" not in stubs, (
            "list_queue is still a stub returning []"
        )

    def test_queue_imports_task_queue_model(self) -> None:
        """queue.py must import TaskQueue model."""
        source = (SRC_ROOT / "queue.py").read_text()
        assert "TaskQueue" in source, (
            "queue.py must import and use the TaskQueue model"
        )


class TestNoStubsInArtifacts:
    """Verify artifacts.py queries Artifact table and streams files."""

    def test_list_artifacts_not_stub(self) -> None:
        """list_artifacts must query the DB (not return [])."""
        source = (SRC_ROOT / "artifacts.py").read_text()
        stubs = _has_stub_return(source)
        assert "list_artifacts" not in stubs, (
            "list_artifacts is still a stub returning []"
        )

    def test_download_artifact_not_stub_raise(self) -> None:
        """download_artifact must not be a stub that always raises 404."""
        source = (SRC_ROOT / "artifacts.py").read_text()
        # Real implementation queries DB first before raising 404
        assert "scalar_one_or_none" in source or "FileResponse" in source, (
            "download_artifact must query DB and stream files via FileResponse"
        )

    def test_artifacts_imports_file_response(self) -> None:
        """artifacts.py must import FileResponse for file streaming."""
        source = (SRC_ROOT / "artifacts.py").read_text()
        assert "FileResponse" in source, (
            "artifacts.py must use FileResponse to stream artifact files"
        )


class TestNoStubsInThreads:
    """Verify threads.py queries Conversation/Message tables."""

    def test_list_threads_not_stub(self) -> None:
        """list_threads must query the DB."""
        source = (SRC_ROOT / "threads.py").read_text()
        stubs = _has_stub_return(source)
        assert "list_threads" not in stubs, (
            "list_threads is still a stub returning []"
        )

    def test_threads_imports_conversation_model(self) -> None:
        """threads.py must import Conversation model."""
        source = (SRC_ROOT / "threads.py").read_text()
        assert "Conversation" in source, (
            "threads.py must use the Conversation model for real DB queries"
        )


class TestWiringCompleteness:
    """Verify all stub-prone endpoints are wired with get_db_session."""

    EXPECTED_WIRED = [
        ("approvals", "list_pending_approvals"),
        ("approvals", "decide_approval"),
        ("queue", "list_queue"),
        ("artifacts", "list_artifacts"),
        ("artifacts", "download_artifact"),
        ("threads", "list_threads"),
        ("threads", "list_messages"),
    ]

    def test_all_endpoints_have_db_session_dependency(self) -> None:
        """All real-data endpoints must declare get_db_session dependency."""
        import importlib

        from noa.api.deps import get_db_session

        failures = []
        for module_name, fn_name in self.EXPECTED_WIRED:
            mod = importlib.import_module(f"noa.api.v1.{module_name}")
            fn = getattr(mod, fn_name, None)
            if fn is None:
                failures.append(f"{module_name}.{fn_name}: function not found")
                continue
            sig = inspect.signature(fn)
            deps = [
                p.default
                for p in sig.parameters.values()
                if hasattr(p.default, "dependency")
            ]
            dep_fns = [d.dependency for d in deps]
            if get_db_session not in dep_fns:
                failures.append(f"{module_name}.{fn_name}: missing get_db_session dep")

        assert not failures, "Wiring failures:\n" + "\n".join(failures)

    def test_app_state_memory_store_wired(self) -> None:
        """app_state must expose get_memory_store and set_memory_store."""
        from noa.api import app_state

        assert callable(getattr(app_state, "get_memory_store", None))
        assert callable(getattr(app_state, "set_memory_store", None))
