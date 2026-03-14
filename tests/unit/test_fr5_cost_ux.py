"""FR5 — Cost, Runs & Dashboard UX tests.

Tests for:
- UX-H7: cost_summary includes budget_limit_usd per period
- UX-H8: GET /api/v1/cost/pricing returns model pricing table
- UX-H11: budget_limit_usd is None when no settings exist
- UX-M7: cost records have run_id linkable field

Spec refs: SPEC.md §24 (cost tracking), §25 (API)

Pattern: in-memory SQLite + create_app() + dependency_overrides
(same as test_mv1_threads.py — the established working pattern)
"""

# ruff: noqa: S105, S106, E501
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared in-memory DB factory
# ---------------------------------------------------------------------------

async def _make_db():
    """Return (factory, engine) with all tables created.

    UserSettings lives outside noa.db.models so must be imported explicitly
    before create_all — see noa/db/models/__init__.py note on circular imports.
    """
    import noa.settings.models  # noqa: F401 — registers UserSettings on Base.metadata
    from noa.db.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory, engine


def _build_app(factory, user_id: uuid.UUID):
    """Minimal app with cost router, auth + DB overridden.

    The cost endpoint uses _get_session_factory() (not get_db_session DI),
    so we wire it via app_state.set_session_factory().
    """
    from noa.api.app import create_app
    from noa.api.app_state import set_session_factory
    from noa.api.deps import get_db_session
    from noa.auth.middleware import AuthUser, require_auth

    app = create_app()

    # Wire session factory so cost.py's _get_session_factory() finds it
    set_session_factory(factory)

    async def _fake_auth():
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db
    return app


# ---------------------------------------------------------------------------
# Helper: seed data
# ---------------------------------------------------------------------------

async def _insert_usage(
    factory: Any,
    user_id: uuid.UUID,
    *,
    cost: float = 0.01,
    tokens_in: int = 100,
    tokens_out: int = 50,
    provider: str = "openai",
    model: str = "gpt-4o",
    run_id: uuid.UUID | None = None,
) -> None:
    from noa.db.models.usage import UsageStats

    async with factory() as sess:
        row = UsageStats(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            model_name=model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cost_usd=Decimal(str(cost)),
            timestamp=datetime.now(UTC),
            run_id=run_id,
        )
        sess.add(row)
        await sess.commit()


async def _insert_settings(
    factory: Any,
    user_id: uuid.UUID,
    *,
    budget_daily: float | None = 10.0,
    budget_monthly: float | None = 200.0,
) -> None:
    from noa.settings.models import UserSettings

    async with factory() as sess:
        row = UserSettings(
            id=uuid.uuid4(),
            user_id=user_id,
            budget_daily_usd=budget_daily,
            budget_monthly_usd=budget_monthly,
        )
        sess.add(row)
        await sess.commit()


# ---------------------------------------------------------------------------
# 1. cost_summary returns both periods
# ---------------------------------------------------------------------------

async def test_cost_summary_returns_both_periods(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/summary?period=monthly")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    periods = {s["period"] for s in data["data"]}
    assert "daily" in periods
    assert "monthly" in periods


# ---------------------------------------------------------------------------
# 2. budget_limit_usd included when settings exist
# ---------------------------------------------------------------------------

async def test_cost_summary_includes_budget_limit(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    await _insert_settings(factory, uid, budget_daily=5.0, budget_monthly=100.0)
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/summary?period=monthly")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    summaries = resp.json()["data"]
    by_period = {s["period"]: s for s in summaries}

    assert by_period["daily"]["budget_limit_usd"] == 5.0
    assert by_period["monthly"]["budget_limit_usd"] == 100.0


# ---------------------------------------------------------------------------
# 3. budget_limit_usd is None when no settings
# ---------------------------------------------------------------------------

async def test_cost_summary_no_settings_budget_null(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    # No settings inserted
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/summary?period=monthly")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    summaries = resp.json()["data"]
    for s in summaries:
        assert s["budget_limit_usd"] is None


# ---------------------------------------------------------------------------
# 4. pricing endpoint returns all models
# ---------------------------------------------------------------------------

async def test_cost_pricing_returns_all_models(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/pricing")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    entries = data["data"]
    assert len(entries) > 0
    providers = {e["provider"] for e in entries}
    assert "openai" in providers
    assert "anthropic" in providers


# ---------------------------------------------------------------------------
# 5. pricing entries have correct fields
# ---------------------------------------------------------------------------

async def test_cost_pricing_has_correct_fields(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/pricing")
    app.dependency_overrides.clear()

    entries = resp.json()["data"]
    for entry in entries:
        assert "provider" in entry
        assert "model" in entry
        assert "input_price_per_m" in entry
        assert "output_price_per_m" in entry
        assert isinstance(entry["input_price_per_m"], float)
        assert isinstance(entry["output_price_per_m"], float)


# ---------------------------------------------------------------------------
# 6. records returns empty list when no usage
# ---------------------------------------------------------------------------

async def test_cost_records_empty(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/records")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# 7. records returns data after insert
# ---------------------------------------------------------------------------

async def test_cost_records_with_data(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    run_id = uuid.uuid4()
    await _insert_usage(factory, uid, cost=0.05, run_id=run_id)
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/records?limit=50&offset=0")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    records = resp.json()["data"]
    assert len(records) >= 1
    run_ids = [r["run_id"] for r in records]
    assert str(run_id) in run_ids


# ---------------------------------------------------------------------------
# 8. known models have non-zero pricing
# ---------------------------------------------------------------------------

async def test_cost_pricing_no_zero_for_known_models(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/pricing")
    app.dependency_overrides.clear()

    entries = resp.json()["data"]
    paid_entries = [e for e in entries if e["provider"] != "ollama"]
    assert len(paid_entries) > 0
    for e in paid_entries:
        assert e["input_price_per_m"] > 0
        assert e["output_price_per_m"] > 0


# ---------------------------------------------------------------------------
# 9. daily cost <= monthly cost
# ---------------------------------------------------------------------------

async def test_cost_summary_daily_subset_of_monthly(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    await _insert_usage(factory, uid, cost=0.02)
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/summary?period=monthly")
    app.dependency_overrides.clear()

    summaries = resp.json()["data"]
    by_period = {s["period"]: s for s in summaries}
    assert by_period["daily"]["cost_usd"] <= by_period["monthly"]["cost_usd"]


# ---------------------------------------------------------------------------
# 10. records pagination works
# ---------------------------------------------------------------------------

async def test_cost_records_pagination(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    for _ in range(3):
        await _insert_usage(factory, uid, cost=0.001)
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp_all = await c.get("/api/v1/cost/records?limit=50&offset=0")
        resp_one = await c.get("/api/v1/cost/records?limit=1&offset=0")
    app.dependency_overrides.clear()

    assert len(resp_all.json()["data"]) >= 3
    assert len(resp_one.json()["data"]) == 1


# ---------------------------------------------------------------------------
# 11. ollama is free
# ---------------------------------------------------------------------------

async def test_cost_pricing_ollama_is_free(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/pricing")
    app.dependency_overrides.clear()

    entries = resp.json()["data"]
    ollama_entries = [e for e in entries if e["provider"] == "ollama"]
    assert len(ollama_entries) > 0
    for e in ollama_entries:
        assert e["input_price_per_m"] == 0.0
        assert e["output_price_per_m"] == 0.0


# ---------------------------------------------------------------------------
# 12. summary returns 0 cost when no usage_stats rows
# ---------------------------------------------------------------------------

async def test_cost_summary_empty_no_data(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-fr5-cost-ux-testing12345")
    factory, _ = await _make_db()
    uid = uuid.uuid4()
    app = _build_app(factory, uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/cost/summary?period=monthly")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    summaries = resp.json()["data"]
    assert len(summaries) > 0
    for s in summaries:
        assert s["cost_usd"] == 0.0
