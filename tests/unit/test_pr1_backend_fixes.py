"""Tests for PR1: Backend Critical Fixes — Data Integrity.

Covers:
  BE-C1: Runs endpoints join UsageStats for real cost/token/model data.
  BE-C2: Memory endpoints user-scoped via MemoryStore user_id filtering.
  BE-H2: RunService methods are async (select/execute pattern).

Spec refs: SPEC.md §13.2, §22.1, §22.2
"""

# ruff: noqa: S101, S105, S106

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.pr1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_user(user_id: uuid.UUID | None = None) -> Any:
    from noa.auth.middleware import AuthUser

    return AuthUser(user_id=user_id or uuid.uuid4())


def _make_run(
    user_id: uuid.UUID,
    *,
    run_id: uuid.UUID | None = None,
    thread_id: uuid.UUID | None = None,
    status: str = "completed",
) -> Any:
    """Create a minimal Run-like object."""
    from datetime import UTC, datetime, timedelta

    r = MagicMock()
    r.id = run_id or uuid.uuid4()
    r.user_id = user_id
    r.thread_id = thread_id or uuid.uuid4()
    r.status = status
    r.risk_tier = "low"
    r.privacy_mode = "external"
    r.summary = None
    now = datetime.now(UTC)
    r.created_at = now - timedelta(seconds=5)
    r.updated_at = now
    return r


def _make_usage_row(
    run_id: uuid.UUID,
    *,
    provider: str = "anthropic",
    model_name: str = "claude-3-haiku",
    input_tokens: int = 100,
    output_tokens: int = 200,
    cost_usd: Decimal = Decimal("0.001"),
) -> Any:
    """Create a minimal UsageStats-like row."""
    row = MagicMock()
    row.run_id = run_id
    row.provider = provider
    row.model_name = model_name
    row.tokens_in = input_tokens
    row.tokens_out = output_tokens
    row.cost_usd = cost_usd
    return row


def _mock_request() -> Any:
    from starlette.requests import Request as StarletteRequest

    return MagicMock(spec=StarletteRequest)


# ===========================================================================
# BE-C1: Runs endpoints — UsageStats join
# ===========================================================================


class TestListRunsUsageJoin:
    """BE-C1 list_runs returns real cost/token/model when UsageStats row exists."""

    async def test_list_runs_returns_usage_data_when_stats_exist(self) -> None:
        """list_runs aggregates UsageStats and returns real model/tokens/cost."""
        from noa.api.v1.runs import list_runs

        user = _make_auth_user()
        run_id = uuid.uuid4()
        run = _make_run(user.user_id, run_id=run_id)

        # Build the aggregated usage row that the SQL query returns
        usage_agg = MagicMock()
        usage_agg.run_id = run_id
        usage_agg.provider = "anthropic"
        usage_agg.model_name = "claude-3-haiku"
        usage_agg.tokens_in = 100
        usage_agg.tokens_out = 200
        usage_agg.cost_usd = Decimal("0.001")

        run_result = MagicMock()
        run_result.scalars.return_value.all.return_value = [run]

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_agg]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[run_result, usage_result])

        request = _mock_request()

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = "trace-1"
            response = await list_runs(
                request=request, user=user, db=db, limit=50, offset=0
            )

        assert response["ok"] is True
        items = response["data"]
        assert len(items) == 1
        item = items[0]
        assert item["model"] == "claude-3-haiku"
        assert item["provider"] == "anthropic"
        assert item["tokens_in"] == 100
        assert item["tokens_out"] == 200
        assert item["cost_usd"] > 0

    async def test_list_runs_returns_zeros_when_no_usage_stats(self) -> None:
        """list_runs returns zeros/empty strings when no UsageStats exist."""
        from noa.api.v1.runs import list_runs

        user = _make_auth_user()
        run = _make_run(user.user_id)

        run_result = MagicMock()
        run_result.scalars.return_value.all.return_value = [run]

        # No usage rows for this run
        usage_result = MagicMock()
        usage_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[run_result, usage_result])

        request = _mock_request()

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await list_runs(
                request=request, user=user, db=db, limit=50, offset=0
            )

        assert response["ok"] is True
        items = response["data"]
        assert len(items) == 1
        item = items[0]
        assert item["model"] == ""
        assert item["provider"] == ""
        assert item["tokens_in"] == 0
        assert item["tokens_out"] == 0
        assert item["cost_usd"] == 0.0

    async def test_list_runs_computes_duration_ms(self) -> None:
        """list_runs computes duration_ms from created_at to updated_at."""
        from datetime import UTC, datetime, timedelta

        from noa.api.v1.runs import list_runs

        user = _make_auth_user()
        run = MagicMock()
        run.id = uuid.uuid4()
        run.user_id = user.user_id
        run.thread_id = uuid.uuid4()
        run.status = "completed"
        run.risk_tier = "low"
        run.privacy_mode = "external"
        run.summary = None
        now = datetime.now(UTC)
        run.created_at = now - timedelta(seconds=2)
        run.updated_at = now

        run_result = MagicMock()
        run_result.scalars.return_value.all.return_value = [run]
        usage_result = MagicMock()
        usage_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[run_result, usage_result])

        request = _mock_request()

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await list_runs(
                request=request, user=user, db=db, limit=50, offset=0
            )

        item = response["data"][0]
        # Should be approximately 2000ms (2 seconds)
        assert item["duration_ms"] >= 1900


class TestGetRunUsageJoin:
    """BE-C1 get_run returns real data from UsageStats join."""

    async def test_get_run_returns_usage_data_when_stats_exist(self) -> None:
        """get_run returns real model/tokens/cost when UsageStats row exists."""
        from noa.api.v1.runs import get_run

        user = _make_auth_user()
        run_id = uuid.uuid4()
        run = _make_run(user.user_id, run_id=run_id)

        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = run

        # Aggregated usage row
        usage_row = MagicMock()
        usage_row.provider = "openai"
        usage_row.model_name = "gpt-4o"
        usage_row.tokens_in = 50
        usage_row.tokens_out = 150
        usage_row.cost_usd = Decimal("0.005")

        usage_result = MagicMock()
        usage_result.one.return_value = usage_row

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[run_result, usage_result])

        request = _mock_request()

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = "trace-2"
            response = await get_run(
                run_id=run_id, request=request, user=user, db=db
            )

        assert response["ok"] is True
        data = response["data"]
        assert data["model"] == "gpt-4o"
        assert data["provider"] == "openai"
        assert data["tokens_in"] == 50
        assert data["tokens_out"] == 150
        assert data["cost_usd"] > 0

    async def test_get_run_returns_zeros_when_no_usage_stats(self) -> None:
        """get_run returns zeros when no UsageStats row exists."""
        from noa.api.v1.runs import get_run

        user = _make_auth_user()
        run_id = uuid.uuid4()
        run = _make_run(user.user_id, run_id=run_id)

        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = run

        # Empty aggregation (coalesce gives None → 0)
        usage_row = MagicMock()
        usage_row.provider = None
        usage_row.model_name = None
        usage_row.tokens_in = None
        usage_row.tokens_out = None
        usage_row.cost_usd = None

        usage_result = MagicMock()
        usage_result.one.return_value = usage_row

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[run_result, usage_result])

        request = _mock_request()

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await get_run(
                run_id=run_id, request=request, user=user, db=db
            )

        data = response["data"]
        assert data["model"] == ""
        assert data["provider"] == ""
        assert data["tokens_in"] == 0
        assert data["tokens_out"] == 0
        assert data["cost_usd"] == 0.0


# ===========================================================================
# BE-C2: Memory endpoints — user scoping
# ===========================================================================


class TestMemoryStoreUserScoping:
    """BE-C2 MemoryStore filters facts by user_id."""

    def _make_store(self) -> Any:
        from noa.private_worker.memory_store import MemoryStore

        return MemoryStore()

    def _add_fact(self, store: Any, user_id: str, fact_text: str) -> str:
        """Add a fact directly to the store with user_id set."""
        fact_id = store.store(
            fact=fact_text,
            category="preference",
            embedding=[0.1, 0.2, 0.3],
            source_thread_id="thread-abc",
        )
        if fact_id is not None:
            store._facts[fact_id]["user_id"] = user_id  # noqa: SLF001
        return fact_id  # type: ignore[return-value]

    def test_list_all_filters_by_user_id(self) -> None:
        """list_all(user_id=x) returns only facts for user x."""
        store = self._make_store()
        uid_a = "user-a"
        uid_b = "user-b"
        fid_a = self._add_fact(store, uid_a, "User A likes cats")
        fid_b = self._add_fact(store, uid_b, "User B likes dogs")

        facts_a = store.list_all(user_id=uid_a)
        assert len(facts_a) == 1
        assert facts_a[0]["id"] == fid_a

        facts_b = store.list_all(user_id=uid_b)
        assert len(facts_b) == 1
        assert facts_b[0]["id"] == fid_b

    def test_list_all_returns_empty_for_unknown_user(self) -> None:
        """list_all returns empty list when user has no facts."""
        store = self._make_store()
        self._add_fact(store, "user-a", "Some fact")

        facts = store.list_all(user_id="user-nobody")
        assert facts == []

    def test_approve_fact_only_approves_owned_facts(self) -> None:
        """update_status with user_id only updates facts owned by that user."""
        store = self._make_store()
        uid_a = "user-a"
        uid_b = "user-b"
        fid_a = self._add_fact(store, uid_a, "User A fact")
        self._add_fact(store, uid_b, "User B fact")

        # user_b tries to approve user_a's fact — must fail
        updated = store.update_status(fid_a, "approved", user_id=uid_b)
        assert updated is False

        # user_a can approve their own fact
        updated = store.update_status(fid_a, "approved", user_id=uid_a)
        assert updated is True

    def test_update_fact_uses_public_persist_method(self) -> None:
        """MemoryStore.persist() is a public method (not _persist)."""
        store = self._make_store()
        fid = self._add_fact(store, "user-a", "Some preference")
        assert fid is not None

        # persist() must be callable and not raise
        store.persist(fid)

    def test_delete_fact_only_deletes_owned_facts(self) -> None:
        """delete with user_id only removes facts owned by that user."""
        store = self._make_store()
        uid_a = "user-a"
        uid_b = "user-b"
        fid_a = self._add_fact(store, uid_a, "User A sensitive fact")

        # user_b attempts deletion — must fail
        deleted = store.delete(fid_a, user_id=uid_b)
        assert deleted is False
        assert store.get_by_id(fid_a) is not None

        # user_a deletes their own fact — must succeed
        deleted = store.delete(fid_a, user_id=uid_a)
        assert deleted is True
        assert store.get_by_id(fid_a) is None


# ===========================================================================
# BE-H2: RunService — async methods
# ===========================================================================


class TestRunServiceAsync:
    """BE-H2 RunService uses async execute pattern on async session."""

    def _make_service(self) -> tuple[Any, Any]:
        """Return (service, mock_session)."""
        from noa.runs.service import RunService

        session = AsyncMock()
        svc = RunService(session=session)
        return svc, session

    async def test_create_run_adds_and_flushes(self) -> None:
        """create_run adds a Run and calls session.flush()."""
        svc, session = self._make_service()
        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()

        run = await svc.create_run(user_id=user_id, thread_id=thread_id)

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert run.user_id == user_id
        assert run.thread_id == thread_id
        assert run.status == "pending"

    async def test_get_run_returns_none_when_not_found(self) -> None:
        """get_run returns None when no run matches."""
        svc, session = self._make_service()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.get_run(uuid.uuid4())
        assert result is None

    async def test_get_run_returns_run_when_found(self) -> None:
        """get_run returns the Run object when found."""
        svc, session = self._make_service()
        run_id = uuid.uuid4()

        fake_run = MagicMock()
        fake_run.id = run_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_run
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.get_run(run_id)
        assert result is fake_run

    async def test_list_runs_returns_all_matching(self) -> None:
        """list_runs returns all matching runs."""
        svc, session = self._make_service()
        fake_runs = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = fake_runs
        session.execute = AsyncMock(return_value=mock_result)

        result = await svc.list_runs()
        assert len(result) == 2

    async def test_list_runs_filters_by_thread_id(self) -> None:
        """list_runs filters by thread_id when provided."""


        svc, session = self._make_service()
        thread_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await svc.list_runs(thread_id=thread_id)

        # Verify execute was called (the WHERE clause is embedded in the stmt)
        session.execute.assert_called_once()
        stmt_arg = session.execute.call_args[0][0]
        # The compiled WHERE clause should reference thread_id
        compiled = str(stmt_arg.compile())
        assert "thread_id" in compiled

    async def test_list_runs_filters_by_user_id(self) -> None:
        """list_runs filters by user_id when provided."""
        svc, session = self._make_service()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await svc.list_runs(user_id=user_id)

        session.execute.assert_called_once()
        stmt_arg = session.execute.call_args[0][0]
        compiled = str(stmt_arg.compile())
        assert "user_id" in compiled

    async def test_update_status_valid_transition(self) -> None:
        """update_status transitions status when transition is valid."""
        svc, session = self._make_service()
        run_id = uuid.uuid4()

        fake_run = MagicMock()
        fake_run.id = run_id
        fake_run.status = "pending"
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = fake_run
        session.execute = AsyncMock(return_value=mock_result)

        updated = await svc.update_status(run_id, "running")

        assert updated.status == "running"
        session.flush.assert_called_once()

    async def test_update_status_raises_for_invalid_transition(self) -> None:
        """update_status raises ValueError for invalid status transition."""
        svc, session = self._make_service()
        run_id = uuid.uuid4()

        fake_run = MagicMock()
        fake_run.id = run_id
        fake_run.status = "completed"  # terminal — no valid outbound transitions
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = fake_run
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid status transition"):
            await svc.update_status(run_id, "running")

    async def test_append_event_stores_event(self) -> None:
        """append_event creates a RunEvent and flushes the session."""
        svc, session = self._make_service()
        run_id = uuid.uuid4()

        event = await svc.append_event(
            run_id,
            "message_received",
            {"message": "hello"},
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert event.run_id == run_id
        assert event.event_type == "message_received"
        assert event.payload == {"message": "hello"}
