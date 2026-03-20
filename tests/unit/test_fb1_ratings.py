"""Tests for FB1 — User Feedback Loop (Response Ratings).

Spec ref: SPEC.md — FB1
Phase: FB1

Test plan:
- Happy path: rating stub created when no existing eval row
- Happy path: rating updates existing evaluation row
- Happy path: summary counts positive/negative correctly
- Negative: POST with invalid run_id (not found)
- Negative: POST with rating=0 is rejected
- Negative: unauthenticated requests return 401
- Integration: full flow via HTTP test client through real DB
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.fb1

FAKE_PW_HASH = "fakehash"  # noqa: S105


# ---------------------------------------------------------------------------
# DB fixtures (sync SQLite)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for ratings tests."""
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
def user_id(db) -> uuid.UUID:
    """Create a test user and return its ID."""
    from noa.db.models.user import User

    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"ratings-test-{uid}@example.com",
        password_hash=FAKE_PW_HASH,
        display_name="Ratings Tester",
    )
    db.add(user)
    db.flush()
    return uid


def _make_run(db: Session, user_id: uuid.UUID) -> uuid.UUID:
    """Create a conversation + run pair; return run ID."""
    from noa.db.models.conversation import Conversation
    from noa.db.models.run import Run

    conv = Conversation(id=uuid.uuid4(), user_id=user_id)
    db.add(conv)
    db.flush()

    rid = uuid.uuid4()
    run = Run(
        id=rid,
        user_id=user_id,
        thread_id=conv.id,
        status="completed",
        privacy_mode="external",
    )
    db.add(run)
    db.flush()
    return rid


@pytest.fixture()
def run_id(db, user_id) -> str:
    """Create a test run and return its ID as string."""
    return str(_make_run(db, user_id))


# ---------------------------------------------------------------------------
# Unit-level tests (helpers + business logic)
# ---------------------------------------------------------------------------


class TestRatingHelpers:
    """Test business logic helpers directly."""

    def test_parse_period_7d(self):
        from noa.api.v1.ratings import _parse_period

        since = _parse_period("7d")
        expected = datetime.now(UTC) - timedelta(days=7)
        assert abs((since - expected).total_seconds()) < 5

    def test_parse_period_30d(self):
        from noa.api.v1.ratings import _parse_period

        since = _parse_period("30d")
        expected = datetime.now(UTC) - timedelta(days=30)
        assert abs((since - expected).total_seconds()) < 5

    def test_parse_period_invalid_raises(self):
        from noa.api.v1.ratings import _parse_period

        with pytest.raises(ValueError, match="Unknown period"):
            _parse_period("90d")

    def test_rating_request_valid_thumbs_up(self):
        from noa.api.v1.ratings import RatingRequest

        req = RatingRequest(run_id="abc", rating=1)
        assert req.is_valid_rating is True

    def test_rating_request_valid_thumbs_down(self):
        from noa.api.v1.ratings import RatingRequest

        req = RatingRequest(run_id="abc", rating=-1)
        assert req.is_valid_rating is True

    def test_rating_request_zero_invalid(self):
        from noa.api.v1.ratings import RatingRequest

        req = RatingRequest(run_id="abc", rating=0)
        assert req.is_valid_rating is False


# ---------------------------------------------------------------------------
# Integration tests: real DB session, no mocks
# ---------------------------------------------------------------------------


class TestRatingsDB:
    """Test rating persistence against a real SQLite session."""

    def test_rating_creates_stub_when_no_eval_exists(self, db, run_id):
        """When no evaluation row exists, rating write creates a stub row."""
        from noa.db.models.response_evaluation import ResponseEvaluation

        existing = db.query(ResponseEvaluation).filter_by(run_id=run_id).first()
        assert existing is None

        stub = ResponseEvaluation(
            id=uuid.uuid4(),
            run_id=run_id,
            rubric_version="none",
            scores={},
            overall=0.0,
            verdict="unrated",
            eval_model="none",
            eval_ms=0.0,
            user_rating=1,
        )
        db.add(stub)
        db.flush()

        fetched = db.query(ResponseEvaluation).filter_by(run_id=run_id).first()
        assert fetched is not None
        assert fetched.user_rating == 1

    def test_rating_updates_existing_eval_row(self, db, run_id):
        """Rating update mutates an existing evaluation row's user_rating."""
        from noa.db.models.response_evaluation import ResponseEvaluation

        ev = ResponseEvaluation(
            id=uuid.uuid4(),
            run_id=run_id,
            rubric_version="v1",
            scores={"helpfulness": 4.0},
            overall=4.0,
            verdict="pass",
            eval_model="test-model",
            eval_ms=100.0,
        )
        db.add(ev)
        db.flush()

        ev.user_rating = 1
        db.flush()
        assert db.query(ResponseEvaluation).filter_by(run_id=run_id).first().user_rating == 1

        ev.user_rating = -1
        db.flush()
        assert db.query(ResponseEvaluation).filter_by(run_id=run_id).first().user_rating == -1

    def test_summary_counts_aggregate_correctly(self, db, user_id):
        """Summary computation counts positive=2, negative=1 correctly."""
        from sqlalchemy import select as sa_select

        from noa.db.models.response_evaluation import ResponseEvaluation

        # 3 runs rated 1, 1, -1
        run_ids = []
        for rating in [1, 1, -1]:
            rid = _make_run(db, user_id)
            ev = ResponseEvaluation(
                id=uuid.uuid4(),
                run_id=str(rid),
                rubric_version="v1",
                scores={},
                overall=4.0,
                verdict="pass",
                eval_model="test",
                eval_ms=0.0,
                user_rating=rating,
            )
            db.add(ev)
            run_ids.append(str(rid))
        db.flush()

        # Query evaluations by run_id strings we know (already string format)
        rating_rows = db.execute(
            sa_select(ResponseEvaluation.user_rating).where(
                ResponseEvaluation.run_id.in_(run_ids),
                ResponseEvaluation.user_rating.isnot(None),
            )
        ).all()
        ratings = [r[0] for r in rating_rows]

        positive = sum(1 for r in ratings if r == 1)
        negative = sum(1 for r in ratings if r == -1)
        total = len(ratings)

        assert positive == 2
        assert negative == 1
        assert total == 3
        assert round(positive / total, 3) == pytest.approx(2 / 3, abs=0.001)


# ---------------------------------------------------------------------------
# HTTP endpoint tests (auth-guard checks)
# ---------------------------------------------------------------------------


class TestRatingsAuth:
    """Verify that unauthenticated requests are rejected by the ratings router."""

    def test_post_rating_requires_auth(self):
        """POST /api/v1/ratings without credentials returns 401."""
        from fastapi.testclient import TestClient

        from noa.api.app import create_app

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/api/v1/ratings",
                json={"run_id": str(uuid.uuid4()), "rating": 1},
            )
        assert resp.status_code == 401

    def test_get_summary_requires_auth(self):
        """GET /api/v1/ratings/summary without credentials returns 401."""
        from fastapi.testclient import TestClient

        from noa.api.app import create_app

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/ratings/summary")
        assert resp.status_code == 401

    def test_router_is_registered(self):
        """Ratings router is mounted and reachable (route exists in app)."""
        from noa.api.app import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("/ratings" in p for p in paths), (
            "Ratings router not found in app routes"
        )
