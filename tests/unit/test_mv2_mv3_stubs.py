"""MV2 + MV3: Verify stub elimination — real DB wiring for approvals, memory, queue, artifacts.

Phase: Wave 17 MV2 (Approvals list + Memory facts) + MV3 (Queue, Artifacts).
Spec refs: SPEC.md §13.2, §17.2, §22.3, §29.6
"""

# ruff: noqa: S101, S105, S106, E501, N817

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request as StarletteRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_user(user_id: uuid.UUID | None = None) -> Any:
    from noa.auth.middleware import AuthUser

    uid = user_id or uuid.uuid4()
    return AuthUser(user_id=uid)


def _mock_request() -> Any:
    return MagicMock(spec=StarletteRequest)


# ---------------------------------------------------------------------------
# MV2a: list_pending_approvals — real DB query
# ---------------------------------------------------------------------------


class TestListPendingApprovals:
    """MV2a — list_pending_approvals uses real DB (not stub [])."""

    def test_endpoint_wired_with_session(self) -> None:
        """list_pending_approvals must depend on get_db_session."""
        import inspect

        from noa.api.deps import get_db_session
        from noa.api.v1.approvals import list_pending_approvals

        sig = inspect.signature(list_pending_approvals)
        deps = [
            p.default
            for p in sig.parameters.values()
            if hasattr(p.default, "dependency")
        ]
        dep_fns = [d.dependency for d in deps]
        assert get_db_session in dep_fns, (
            "list_pending_approvals must depend on get_db_session for real DB"
        )

    def test_returns_db_rows(self) -> None:
        """list_pending_approvals returns real rows from DB session."""
        from noa.api.v1.approvals import list_pending_approvals
        from noa.db.models.approval import Approval

        user_id = uuid.uuid4()
        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=user_id,
            risk_tier="high",
            preview_text="Send email to boss",
            decision="pending",
            domain="external",
            requested_at=datetime.now(UTC),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [approval]
        mock_session.execute = AsyncMock(return_value=mock_result)

        auth_user = _make_auth_user(user_id)

        async def _run() -> dict:
            return await list_pending_approvals(
                request=_mock_request(),
                user=auth_user,
                session=mock_session,
            )

        result = asyncio.run(_run())
        assert result["ok"] is True
        data = result["data"]
        assert len(data) == 1
        assert data[0]["risk_tier"] == "high"
        assert data[0]["preview_text"] == "Send email to boss"

    def test_returns_empty_list_when_no_pending(self) -> None:
        """list_pending_approvals returns [] when no pending rows exist."""
        from noa.api.v1.approvals import list_pending_approvals

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _run() -> dict:
            return await list_pending_approvals(
                request=_mock_request(), user=_make_auth_user(), session=mock_session
            )

        result = asyncio.run(_run())
        assert result["data"] == []


# ---------------------------------------------------------------------------
# MV2b: memory facts — MemoryStore wired
# ---------------------------------------------------------------------------


class TestMemoryFactsWiring:
    """MV2b — memory endpoints call MemoryStore instead of returning stubs."""

    def test_list_facts_calls_store_list_all(self) -> None:
        """list_facts calls store.list_all() when store is available."""
        from noa.api.v1.memory import list_facts

        fake_store = MagicMock()
        fake_store.list_all.return_value = [
            {"id": str(uuid.uuid4()), "fact": "I prefer Python", "status": "approved"}
        ]

        async def _run() -> dict:
            with patch("noa.api.v1.memory._get_memory_store", return_value=fake_store):
                return await list_facts(request=_mock_request(), user=_make_auth_user())

        result = asyncio.run(_run())
        assert result["ok"] is True
        assert len(result["data"]) == 1
        fake_store.list_all.assert_called_once()

    def test_list_facts_returns_empty_when_store_none(self) -> None:
        """list_facts returns [] gracefully when no store is wired."""
        from noa.api.v1.memory import list_facts

        async def _run() -> dict:
            with patch("noa.api.v1.memory._get_memory_store", return_value=None):
                return await list_facts(request=_mock_request(), user=_make_auth_user())

        result = asyncio.run(_run())
        assert result["data"] == []

    def test_approve_fact_calls_update_status(self) -> None:
        """approve_fact calls store.update_status with 'approved'."""
        from noa.api.v1.memory import approve_fact

        fact_id = uuid.uuid4()
        fake_store = MagicMock()
        fake_store.update_status.return_value = True

        async def _run() -> dict:
            with patch("noa.api.v1.memory._get_memory_store", return_value=fake_store):
                return await approve_fact(
                    request=_mock_request(), fact_id=fact_id, user=_make_auth_user()
                )

        result = asyncio.run(_run())
        assert result["data"]["status"] == "approved"
        # user_id is now passed for user-scoped update (BE-C2)
        call_args = fake_store.update_status.call_args
        assert call_args.args == (str(fact_id), "approved")
        assert "user_id" in call_args.kwargs

    def test_approve_fact_404_when_not_found(self) -> None:
        """approve_fact raises 404 when store.update_status returns False."""
        from fastapi import HTTPException

        from noa.api.v1.memory import approve_fact

        fact_id = uuid.uuid4()
        fake_store = MagicMock()
        fake_store.update_status.return_value = False

        async def _run() -> None:
            with patch("noa.api.v1.memory._get_memory_store", return_value=fake_store):
                await approve_fact(
                    request=_mock_request(), fact_id=fact_id, user=_make_auth_user()
                )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_run())
        assert exc_info.value.status_code == 404

    def test_delete_fact_calls_store_delete(self) -> None:
        """delete_fact calls store.delete()."""
        from noa.api.v1.memory import delete_fact

        fact_id = uuid.uuid4()
        fake_store = MagicMock()
        fake_store.delete.return_value = True

        async def _run() -> dict:
            with patch("noa.api.v1.memory._get_memory_store", return_value=fake_store):
                return await delete_fact(
                    request=_mock_request(), fact_id=fact_id, user=_make_auth_user()
                )

        result = asyncio.run(_run())
        assert result["data"]["status"] == "deleted"
        # user_id is now passed for user-scoped delete (BE-C2)
        call_args = fake_store.delete.call_args
        assert call_args.args == (str(fact_id),)
        assert "user_id" in call_args.kwargs

    def test_app_state_has_memory_store_accessors(self) -> None:
        """app_state exports get_memory_store / set_memory_store."""
        from noa.api import app_state

        assert hasattr(app_state, "get_memory_store"), "Missing get_memory_store"
        assert hasattr(app_state, "set_memory_store"), "Missing set_memory_store"

    def test_memory_store_round_trip(self) -> None:
        """set/get_memory_store round-trips through app_state."""
        from noa.api import app_state

        fake = object()
        app_state.set_memory_store(fake)
        assert app_state.get_memory_store() is fake
        app_state._memory_store = None  # noqa: SLF001


# ---------------------------------------------------------------------------
# MV3a: queue — real DB
# ---------------------------------------------------------------------------


class TestQueueRealDB:
    """MV3a — list_queue uses real DB (not stub [])."""

    def test_endpoint_wired_with_session(self) -> None:
        """list_queue must depend on get_db_session."""
        import inspect

        from noa.api.deps import get_db_session
        from noa.api.v1.queue import list_queue

        sig = inspect.signature(list_queue)
        deps = [
            p.default
            for p in sig.parameters.values()
            if hasattr(p.default, "dependency")
        ]
        dep_fns = [d.dependency for d in deps]
        assert get_db_session in dep_fns

    def test_returns_queued_tasks(self) -> None:
        """list_queue returns real task_queue rows."""
        from noa.api.v1.queue import list_queue
        from noa.db.models.task_queue import TaskQueue

        task = TaskQueue(
            id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            task_type="run",
            status="queued",
            retry_count=0,
            queued_at=datetime.now(UTC),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [task]
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _run() -> dict:
            return await list_queue(
                request=_mock_request(), user=_make_auth_user(), session=mock_session
            )

        result = asyncio.run(_run())
        assert result["ok"] is True
        assert len(result["data"]) == 1
        item = result["data"][0]
        assert item["status"] == "queued"
        assert item["position"] == 0
        assert "run_id" in item
        assert "estimated_wait" in item


# ---------------------------------------------------------------------------
# MV3b: artifacts — real DB
# ---------------------------------------------------------------------------


class TestArtifactsRealDB:
    """MV3b — list_artifacts and download_artifact use real DB."""

    def test_list_artifacts_wired_with_session(self) -> None:
        """list_artifacts must depend on get_db_session."""
        import inspect

        from noa.api.deps import get_db_session
        from noa.api.v1.artifacts import list_artifacts

        sig = inspect.signature(list_artifacts)
        deps = [
            p.default
            for p in sig.parameters.values()
            if hasattr(p.default, "dependency")
        ]
        dep_fns = [d.dependency for d in deps]
        assert get_db_session in dep_fns

    def test_list_artifacts_returns_rows(self) -> None:
        """list_artifacts returns real artifact rows joined through runs."""
        from noa.api.v1.artifacts import list_artifacts
        from noa.db.models.artifact import Artifact

        user_id = uuid.uuid4()
        artifact = Artifact(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            type="file",
            name="report.pdf",
            mime_type="application/pdf",
            size_bytes=12345,
            storage_ref="/data/artifacts/report.pdf",
            created_at=datetime.now(UTC),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [artifact]
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _run() -> dict:
            return await list_artifacts(
                request=_mock_request(),
                user=_make_auth_user(user_id),
                session=mock_session,
                limit=50,
                offset=0,
            )

        result = asyncio.run(_run())
        assert result["ok"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["name"] == "report.pdf"
        assert result["data"][0]["size_bytes"] == 12345

    def test_download_artifact_404_when_not_found(self) -> None:
        """download_artifact raises 404 when artifact not in DB."""
        from fastapi import HTTPException

        from noa.api.v1.artifacts import download_artifact

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _run() -> None:
            await download_artifact(
                artifact_id=uuid.uuid4(),
                request=_mock_request(),
                user=_make_auth_user(),
                session=mock_session,
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_run())
        assert exc_info.value.status_code == 404

    def test_download_artifact_404_when_file_missing(self, tmp_path: Path) -> None:
        """download_artifact raises 404 when storage_ref path doesn't exist."""
        from fastapi import HTTPException

        from noa.api.v1.artifacts import download_artifact
        from noa.db.models.artifact import Artifact

        artifact = Artifact(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            type="file",
            name="gone.txt",
            mime_type="text/plain",
            size_bytes=0,
            storage_ref=str(tmp_path / "nonexistent.txt"),
            created_at=datetime.now(UTC),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = artifact
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def _run() -> None:
            await download_artifact(
                artifact_id=artifact.id,
                request=_mock_request(),
                user=_make_auth_user(),
                session=mock_session,
            )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_run())
        assert exc_info.value.status_code == 404
