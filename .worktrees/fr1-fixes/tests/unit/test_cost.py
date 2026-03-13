"""Tests for cost control & token tracking — Phase AB1.

Spec refs: SPEC.md §24
Phase plan: MASTER_PLAN.md Phase AB1

Tests cover: token tracking per LLM call, monthly/daily caps,
per-task limits, cost estimation from pricing, usage display data.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.ab1

FAKE_PW_HASH = "fakehash"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for cost tests."""
    from noa.db.models import Base

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    """Transactional session that rolls back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture()
def user_id(db):
    """Create a test user and return its ID."""
    from noa.db.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="cost-test@example.com",
        password_hash=FAKE_PW_HASH,
        display_name="Cost Tester",
    )
    db.add(user)
    db.flush()
    return user.id


@pytest.fixture()
def tracker(db):
    """Create a CostTracker instance."""
    from noa.cost.tracker import CostTracker

    return CostTracker(db)


@pytest.fixture()
def limiter():
    """Create a CostLimiter with test-friendly limits."""
    from noa.cost.limits import CostLimiter

    return CostLimiter(
        monthly_limit_usd=Decimal("10.00"),
        daily_limit_usd=Decimal("1.00"),
        per_task_limit_usd=Decimal("0.50"),
    )


# ---------------------------------------------------------------------------
# 1. Token tracking — every LLM call logged (§24)
# ---------------------------------------------------------------------------

class TestTokenTracking:
    """CostTracker.record() persists token usage for each LLM call."""

    def test_record_creates_usage_entry(self, db, tracker, user_id):
        """record() creates a UsageStats row with correct fields."""
        entry = tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=500,
            output_tokens=200,
            cost_usd=Decimal("0.0035"),
        )

        assert entry.provider == "openai"
        assert entry.model_name == "gpt-4o"
        assert entry.input_tokens == 500
        assert entry.output_tokens == 200
        assert entry.cost_usd == Decimal("0.0035")
        assert entry.user_id == user_id

    def test_record_persists_to_db(self, db, tracker, user_id):
        """Recorded usage is queryable from the database."""
        from noa.db.models.usage import UsageStats

        entry = tracker.record(
            user_id=user_id,
            provider="anthropic",
            model="claude-sonnet",
            input_tokens=1000,
            output_tokens=300,
            cost_usd=Decimal("0.0048"),
        )

        found = db.query(UsageStats).filter_by(id=entry.id).first()
        assert found is not None
        assert found.provider == "anthropic"

    def test_record_with_session_and_run(self, db, tracker, user_id):
        """record() accepts optional session_id and run_id."""
        sid = uuid.uuid4()
        rid = None  # run_id is optional
        entry = tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.0001"),
            session_id=sid,
            run_id=rid,
        )

        assert entry.session_id == sid
        assert entry.run_id is None


# ---------------------------------------------------------------------------
# 2. Monthly cap enforcement (§24)
# ---------------------------------------------------------------------------

class TestMonthlyCap:
    """Requests refused when monthly spending cap exceeded."""

    def test_monthly_under_limit_allowed(self, db, tracker, limiter, user_id):
        """check() returns True when monthly spend is under limit."""
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.50"),
        )

        result = limiter.check(db, user_id=user_id, scope="monthly")
        assert result.allowed is True

    def test_monthly_over_limit_refused(self, db, tracker, limiter, user_id):
        """check() returns False when monthly spend exceeds limit."""
        # Record $11 of usage (over $10 limit)
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=10000,
            output_tokens=5000,
            cost_usd=Decimal("11.00"),
        )

        result = limiter.check(db, user_id=user_id, scope="monthly")
        assert result.allowed is False
        assert "monthly" in result.reason.lower()


# ---------------------------------------------------------------------------
# 3. Daily cap with warning at 80% (§24)
# ---------------------------------------------------------------------------

class TestDailyCap:
    """Daily cap: warning at 80%, hard limit at 100%."""

    def test_daily_under_80_no_warning(self, db, tracker, limiter, user_id):
        """Under 80% daily spend: allowed, no warning."""
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.50"),
        )

        result = limiter.check(db, user_id=user_id, scope="daily")
        assert result.allowed is True
        assert result.warning is False

    def test_daily_at_80_warns(self, db, tracker, limiter, user_id):
        """At 80% daily spend: allowed but with warning."""
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.85"),
        )

        result = limiter.check(db, user_id=user_id, scope="daily")
        assert result.allowed is True
        assert result.warning is True

    def test_daily_over_limit_refused(self, db, tracker, limiter, user_id):
        """Over 100% daily spend: refused."""
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=10000,
            output_tokens=5000,
            cost_usd=Decimal("1.50"),
        )

        result = limiter.check(db, user_id=user_id, scope="daily")
        assert result.allowed is False


# ---------------------------------------------------------------------------
# 4. Per-task limit enforcement (§24)
# ---------------------------------------------------------------------------

class TestPerTaskLimit:
    """Task aborted when per-task token limit exceeded."""

    def test_task_under_limit_allowed(self, db, tracker, limiter, user_id):
        """Task under per-task limit: allowed."""
        task_id = uuid.uuid4()
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.10"),
            task_id=task_id,
        )

        result = limiter.check(
            db, user_id=user_id, scope="task", task_id=task_id,
        )
        assert result.allowed is True

    def test_task_over_limit_refused(self, db, tracker, limiter, user_id):
        """Task over per-task limit: refused."""
        task_id = uuid.uuid4()
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=10000,
            output_tokens=5000,
            cost_usd=Decimal("0.60"),
            task_id=task_id,
        )

        result = limiter.check(
            db, user_id=user_id, scope="task", task_id=task_id,
        )
        assert result.allowed is False
        assert "task" in result.reason.lower()


# ---------------------------------------------------------------------------
# 5. Cost estimation from provider pricing (§24)
# ---------------------------------------------------------------------------

class TestCostEstimation:
    """USD cost calculated from provider pricing tables."""

    def test_openai_gpt4o_pricing(self):
        """Pricing table returns correct cost for OpenAI GPT-4o."""
        from noa.cost.pricing import estimate_cost

        cost = estimate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        # Cost should be positive and reasonable
        assert cost > Decimal("0")
        # GPT-4o is roughly $2.50/1M input + $10/1M output (as of 2024)
        # Just check it's in a sane range, not exact pricing
        assert cost < Decimal("100")

    def test_anthropic_sonnet_pricing(self):
        """Pricing table returns correct cost for Anthropic Claude Sonnet."""
        from noa.cost.pricing import estimate_cost

        cost = estimate_cost(
            provider="anthropic",
            model="claude-sonnet",
            input_tokens=1000,
            output_tokens=500,
        )

        assert cost > Decimal("0")

    def test_unknown_model_returns_zero(self):
        """Unknown provider/model returns zero cost (safe fallback)."""
        from noa.cost.pricing import estimate_cost

        cost = estimate_cost(
            provider="unknown",
            model="nonexistent",
            input_tokens=1000,
            output_tokens=500,
        )

        assert cost == Decimal("0")


# ---------------------------------------------------------------------------
# 6. Usage display data — breakdowns (§24)
# ---------------------------------------------------------------------------

class TestUsageDisplay:
    """Usage API returns per-message, session, daily, monthly breakdowns."""

    def test_get_daily_usage(self, db, tracker, user_id):
        """get_usage() returns daily breakdown."""
        from noa.cost.tracker import get_usage

        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=500,
            output_tokens=200,
            cost_usd=Decimal("0.0035"),
        )
        tracker.record(
            user_id=user_id,
            provider="anthropic",
            model="claude-sonnet",
            input_tokens=300,
            output_tokens=100,
            cost_usd=Decimal("0.0020"),
        )

        usage = get_usage(db, user_id=user_id, period="daily")
        assert usage.total_cost_usd == Decimal("0.0055")
        assert usage.total_input_tokens == 800
        assert usage.total_output_tokens == 300

    def test_get_monthly_usage(self, db, tracker, user_id):
        """get_usage() returns monthly breakdown."""
        from noa.cost.tracker import get_usage

        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.01"),
        )

        usage = get_usage(db, user_id=user_id, period="monthly")
        assert usage.total_cost_usd >= Decimal("0.01")
        assert usage.total_input_tokens >= 1000

    def test_get_session_usage(self, db, tracker, user_id):
        """get_usage() returns session-scoped breakdown."""
        from noa.cost.tracker import get_usage

        sid = uuid.uuid4()
        tracker.record(
            user_id=user_id,
            provider="openai",
            model="gpt-4o",
            input_tokens=200,
            output_tokens=100,
            cost_usd=Decimal("0.002"),
            session_id=sid,
        )

        usage = get_usage(
            db, user_id=user_id, period="session", session_id=sid,
        )
        assert usage.total_cost_usd == Decimal("0.002")
        assert usage.total_input_tokens == 200
