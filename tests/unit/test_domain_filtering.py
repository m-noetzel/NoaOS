"""W22-M1: Domain filtering for runs and cost endpoints.

Spec refs: SPEC.md §4.1 (domain isolation), §22.4 (runs)
Phase: W22-M1

Test plan:
  Happy paths:
    - list_runs with no privacy_mode returns runs from all domains
    - list_runs with privacy_mode=private returns only private runs
    - list_runs with privacy_mode=external returns only external runs
    - cost_records with no privacy_mode returns records from all runs
    - cost_records with privacy_mode=private returns only private-run records
    - cost_summary with privacy_mode=private sums only private-run costs
  Negative paths:
    - list_runs with privacy_mode=private does NOT return external runs
    - list_runs with privacy_mode=external does NOT return private runs
    - cost_records with privacy_mode=external does NOT include private-run records
    - invalid privacy_mode value rejected with 422
  Integration:
    - Full flow through ASGI test client with real in-memory SQLite DB
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# DB + app helpers — same pattern as test_fr1_domain_isolation.py
# ---------------------------------------------------------------------------


async def _make_db_with_runs():
    """Create an in-memory SQLite DB with one private run and one external run.

    Both runs have associated UsageStats records.

    Returns (factory, user_id, private_run_id, external_run_id).
    """
    from datetime import UTC, datetime

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.base import Base
    from noa.db.models.conversation import Conversation
    from noa.db.models.run import Run
    from noa.db.models.usage import UsageStats

    uid = uuid.uuid4()
    priv_run_id = uuid.uuid4()
    ext_run_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Need a conversation row for the FK constraint
        session.add(Conversation(id=thread_id, user_id=uid, title="Test Thread", domain="private"))
        await session.flush()

        now = datetime.now(UTC)
        session.add(Run(
            id=priv_run_id,
            thread_id=thread_id,
            user_id=uid,
            status="completed",
            risk_tier="low",
            privacy_mode="private",
            created_at=now,
            updated_at=now,
        ))
        session.add(Run(
            id=ext_run_id,
            thread_id=thread_id,
            user_id=uid,
            status="completed",
            risk_tier="low",
            privacy_mode="external",
            created_at=now,
            updated_at=now,
        ))
        await session.flush()

        session.add(UsageStats(
            user_id=uid,
            provider="anthropic",
            model_name="claude-3",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.001"),
            run_id=priv_run_id,
            timestamp=now,
        ))
        session.add(UsageStats(
            user_id=uid,
            provider="openai",
            model_name="gpt-4",
            input_tokens=200,
            output_tokens=100,
            cost_usd=Decimal("0.002"),
            run_id=ext_run_id,
            timestamp=now,
        ))
        await session.commit()

    return factory, uid, priv_run_id, ext_run_id


def _build_app(factory, user_id: uuid.UUID):
    """Build a test FastAPI app with auth + DB overrides."""
    from noa.api.app import create_app
    from noa.api.deps import get_db_session
    from noa.auth.middleware import AuthUser, require_auth

    app = create_app()

    async def _fake_auth():
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db

    # Wire the session factory into app_state so cost endpoints can use it
    from noa.api import app_state
    app_state.set_session_factory(factory)

    return app


# ---------------------------------------------------------------------------
# list_runs: domain filtering
# ---------------------------------------------------------------------------


class TestListRunsDomainFiltering:
    """GET /api/v1/runs?privacy_mode=X — domain isolation."""

    async def test_no_filter_returns_all_runs(self, monkeypatch):
        """When no privacy_mode param is given, runs from all domains are returned."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/runs")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["data"]]
        assert str(priv_run_id) in ids
        assert str(ext_run_id) in ids

    async def test_private_filter_returns_only_private_runs(self, monkeypatch):
        """privacy_mode=private returns only runs with privacy_mode='private'."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/runs?privacy_mode=private")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["data"]]
        assert str(priv_run_id) in ids
        assert str(ext_run_id) not in ids

    async def test_external_filter_returns_only_external_runs(self, monkeypatch):
        """privacy_mode=external returns only runs with privacy_mode='external'."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/runs?privacy_mode=external")

        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["data"]]
        assert str(ext_run_id) in ids
        assert str(priv_run_id) not in ids

    async def test_invalid_privacy_mode_rejected(self, monkeypatch):
        """An unrecognised privacy_mode value returns 422 Unprocessable Entity."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, _, _ = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/runs?privacy_mode=unknown")

        assert resp.status_code == 422

    async def test_private_filter_response_shape(self, monkeypatch):
        """Filtered run response includes privacy_mode field matching the filter."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, _ = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/runs?privacy_mode=private")

        assert resp.status_code == 200
        runs = resp.json()["data"]
        assert all(r["privacy_mode"] == "private" for r in runs)


# ---------------------------------------------------------------------------
# cost_records: domain filtering
# ---------------------------------------------------------------------------


class TestCostRecordsDomainFiltering:
    """GET /api/v1/cost/records?privacy_mode=X — domain isolation."""

    async def test_no_filter_returns_all_records(self, monkeypatch):
        """When no privacy_mode param is given, cost records from all runs are returned."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/records")

        assert resp.status_code == 200
        records = resp.json()["data"]
        run_ids = {r["run_id"] for r in records}
        assert str(priv_run_id) in run_ids
        assert str(ext_run_id) in run_ids

    async def test_private_filter_returns_only_private_run_records(self, monkeypatch):
        """privacy_mode=private returns only records linked to private runs."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/records?privacy_mode=private")

        assert resp.status_code == 200
        records = resp.json()["data"]
        run_ids = {r["run_id"] for r in records}
        assert str(priv_run_id) in run_ids
        assert str(ext_run_id) not in run_ids

    async def test_external_filter_excludes_private_run_records(self, monkeypatch):
        """privacy_mode=external does not return records from private runs."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/records?privacy_mode=external")

        assert resp.status_code == 200
        records = resp.json()["data"]
        run_ids = {r["run_id"] for r in records}
        assert str(ext_run_id) in run_ids
        assert str(priv_run_id) not in run_ids

    async def test_invalid_privacy_mode_rejected(self, monkeypatch):
        """An unrecognised privacy_mode value returns 422."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, _, _ = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/records?privacy_mode=bad")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# cost_summary: domain filtering
# ---------------------------------------------------------------------------


class TestCostSummaryDomainFiltering:
    """GET /api/v1/cost/summary?privacy_mode=X — aggregated cost isolation."""

    async def test_private_filter_sums_only_private_run_costs(self, monkeypatch):
        """privacy_mode=private summary reflects only costs from private runs."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/summary?period=daily&privacy_mode=private")

        assert resp.status_code == 200
        summaries = resp.json()["data"]
        daily = next(s for s in summaries if s["period"] == "daily")
        # Private run has cost 0.001 USD; external run has 0.002. Filtered sum: 0.001
        assert daily["cost_usd"] == pytest.approx(0.001, abs=1e-5)

    async def test_external_filter_sums_only_external_run_costs(self, monkeypatch):
        """privacy_mode=external summary reflects only costs from external runs."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, priv_run_id, ext_run_id = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/summary?period=daily&privacy_mode=external")

        assert resp.status_code == 200
        summaries = resp.json()["data"]
        daily = next(s for s in summaries if s["period"] == "daily")
        # External run has cost 0.002 USD
        assert daily["cost_usd"] == pytest.approx(0.002, abs=1e-5)

    async def test_no_filter_sums_all_costs(self, monkeypatch):
        """Without privacy_mode, summary includes all domains."""
        monkeypatch.setenv("SECRET_KEY", "test-secret")
        factory, uid, _, _ = await _make_db_with_runs()
        app = _build_app(factory, uid)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/cost/summary?period=daily")

        assert resp.status_code == 200
        summaries = resp.json()["data"]
        daily = next(s for s in summaries if s["period"] == "daily")
        # Both runs: 0.001 + 0.002 = 0.003
        assert daily["cost_usd"] == pytest.approx(0.003, abs=1e-5)
