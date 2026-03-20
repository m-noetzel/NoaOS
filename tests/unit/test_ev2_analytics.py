"""Tests for EV2 analytics endpoints.

Spec ref: SPEC.md — EV2 (Self-Improvement Analytics).

Coverage:
- eval-trends: aggregation by dimension, model, task_type, archetype
- eval-trends: divergence detection (>1.5 threshold)
- eval-trends: empty data handling
- worst-dimensions: returns lowest-scoring dimensions sorted ascending
- auth required (401 on missing token)
- integration: full flow through real file-backed SQLite DB
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from noa.api.app_state import reset_all, set_session_factory
from noa.db.models.base import Base
from noa.db.models.conversation import Conversation
from noa.db.models.response_evaluation import ResponseEvaluation
from noa.db.models.run import Run
from noa.db.models.user import User

FAKE_PW_HASH = "fakehash"  # noqa: S105
_TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_TEST_SESSION_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path) -> Path:
    """Return a path to a temp SQLite file."""
    return tmp_path / "ev2_test.db"


@pytest.fixture()
def sync_db(db_path):
    """Synchronous SQLite session for seeding test data.

    Using a file-backed DB (not :memory:) so that the async engine used
    by the endpoint can read the same data — in-memory DBs are per-connection.
    Each test method should call db.commit() after seeding so the file is
    flushed before the endpoint reads it.
    """
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def app_client(db_path, sync_db):
    """TestClient wired to the same file-backed SQLite via async engine.

    The factory is set AFTER the TestClient enters its lifespan context so
    it overrides whatever the lifespan sets up (which points to Postgres
    by default).
    """
    from noa.api.app import create_app
    from noa.auth.middleware import AuthUser, require_auth

    async_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _mock_require_auth():
        return AuthUser(user_id=_TEST_USER_ID, session_id=_TEST_SESSION_ID)

    app = create_app()
    app.dependency_overrides[require_auth] = _mock_require_auth

    with TestClient(app, raise_server_exceptions=True) as client:
        # Override the factory AFTER lifespan has run — this ensures our
        # test factory (pointing to the temp SQLite file) wins over whatever
        # the app lifespan sets up.
        set_session_factory(factory)
        yield client, sync_db

    reset_all()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_user(session: Session) -> None:
    existing = session.query(User).filter_by(id=_TEST_USER_ID).first()
    if existing is None:
        session.add(User(
            id=_TEST_USER_ID,
            email="ev2-test@example.com",
            password_hash=FAKE_PW_HASH,
            display_name="EV2 Tester",
        ))
        session.flush()


def _make_run(session: Session) -> Run:
    conv = Conversation(id=uuid.uuid4(), user_id=_TEST_USER_ID)
    session.add(conv)
    session.flush()
    run = Run(
        id=uuid.uuid4(),
        user_id=_TEST_USER_ID,
        thread_id=conv.id,
        status="completed",
        privacy_mode="external",
    )
    session.add(run)
    session.flush()
    return run


def _make_eval(
    run: Run,
    scores: dict[str, float],
    overall: float,
    *,
    task_type: str | None = None,
    archetype: str | None = None,
    eval_model: str = "claude-3-haiku-20240307",
    user_rating: int | None = None,
    created_at: datetime | None = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        id=uuid.uuid4(),
        run_id=str(run.id),
        scores=scores,
        overall=overall,
        verdict="pass" if overall >= 3.0 else "flag",
        eval_model=eval_model,
        eval_ms=50.0,
        task_type=task_type,
        archetype=archetype,
        user_rating=user_rating,
        created_at=created_at or datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests: Auth (no DB required)
# ---------------------------------------------------------------------------


def test_eval_trends_requires_auth():
    """Unauthenticated request returns 401."""
    from noa.api.app import create_app

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/analytics/eval-trends")
    assert resp.status_code == 401


def test_worst_dimensions_requires_auth():
    """Unauthenticated request returns 401."""
    from noa.api.app import create_app

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/analytics/worst-dimensions")
    assert resp.status_code == 401


def test_eval_trends_invalid_group_by(app_client):
    """Invalid group_by returns error envelope."""
    client, _ = app_client
    resp = client.get("/api/v1/analytics/eval-trends?group_by=invalid_key")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INVALID_GROUP_BY"


def test_eval_trends_invalid_period(app_client):
    """Invalid period returns HTTP 422 from FastAPI query validation."""
    client, _ = app_client
    resp = client.get("/api/v1/analytics/eval-trends?period=invalid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Empty data
# ---------------------------------------------------------------------------


def test_eval_trends_empty_no_runs(app_client):
    """When user has no runs, eval-trends returns empty data."""
    client, db = app_client
    _seed_user(db)
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=dimension")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["data"] == []
    assert data["overall_avg"] == 0.0
    assert data["divergence_alerts"] == []


def test_worst_dimensions_empty(app_client):
    """When user has no runs, worst-dimensions returns empty worst list."""
    client, db = app_client
    _seed_user(db)
    db.commit()

    resp = client.get("/api/v1/analytics/worst-dimensions?period=7d")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["worst"] == []


# ---------------------------------------------------------------------------
# Integration tests: data seeded via sync session, read via HTTP endpoint
# ---------------------------------------------------------------------------


def test_eval_trends_by_dimension(app_client):
    """Aggregation by dimension computes per-rubric averages correctly."""
    client, db = app_client
    _seed_user(db)

    run1 = _make_run(db)
    run2 = _make_run(db)
    db.add(_make_eval(run1, scores={"goal_alignment": 4.0, "completeness": 3.0}, overall=3.5))
    db.add(_make_eval(run2, scores={"goal_alignment": 2.0, "completeness": 5.0}, overall=3.5))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=dimension")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]

    by_key = {item["key"]: item for item in data["data"]}
    assert "goal_alignment" in by_key
    assert "completeness" in by_key
    # goal_alignment avg = (4.0 + 2.0) / 2 = 3.0
    assert by_key["goal_alignment"]["avg_score"] == pytest.approx(3.0, abs=0.01)
    # completeness avg = (3.0 + 5.0) / 2 = 4.0
    assert by_key["completeness"]["avg_score"] == pytest.approx(4.0, abs=0.01)
    assert by_key["goal_alignment"]["count"] == 2
    # overall_avg = (3.5 + 3.5) / 2 = 3.5
    assert data["overall_avg"] == pytest.approx(3.5, abs=0.01)


def test_eval_trends_by_model(app_client):
    """Aggregation by model groups by eval_model column."""
    client, db = app_client
    _seed_user(db)

    run1 = _make_run(db)
    run2 = _make_run(db)
    db.add(_make_eval(run1, scores={"x": 4.0}, overall=4.0, eval_model="model-a"))
    db.add(_make_eval(run2, scores={"x": 2.0}, overall=2.0, eval_model="model-b"))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=model")
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_key = {item["key"]: item for item in data["data"]}
    assert "model-a" in by_key
    assert "model-b" in by_key
    assert by_key["model-a"]["avg_score"] == pytest.approx(4.0, abs=0.01)
    assert by_key["model-b"]["avg_score"] == pytest.approx(2.0, abs=0.01)


def test_eval_trends_by_task_type(app_client):
    """Aggregation by task_type groups correctly."""
    client, db = app_client
    _seed_user(db)

    run1 = _make_run(db)
    run2 = _make_run(db)
    db.add(_make_eval(run1, scores={"x": 5.0}, overall=5.0, task_type="research"))
    db.add(_make_eval(run2, scores={"x": 3.0}, overall=3.0, task_type="coding"))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=task_type")
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_key = {item["key"]: item for item in data["data"]}
    assert "research" in by_key
    assert "coding" in by_key


def test_eval_trends_by_archetype(app_client):
    """Aggregation by archetype groups correctly."""
    client, db = app_client
    _seed_user(db)

    run1 = _make_run(db)
    db.add(_make_eval(run1, scores={"x": 4.5}, overall=4.5, archetype="analyst"))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=archetype")
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_key = {item["key"]: item for item in data["data"]}
    assert "analyst" in by_key
    assert by_key["analyst"]["avg_score"] == pytest.approx(4.5, abs=0.01)


def test_eval_trends_period_filter_excludes_old(app_client):
    """Evals older than the period are excluded from results."""
    client, db = app_client
    _seed_user(db)

    run1 = _make_run(db)
    run2 = _make_run(db)

    old_ts = datetime.now(UTC) - timedelta(days=10)
    recent_ts = datetime.now(UTC) - timedelta(hours=1)

    db.add(_make_eval(run1, scores={"x": 1.0}, overall=1.0, created_at=old_ts))
    db.add(_make_eval(run2, scores={"x": 5.0}, overall=5.0, created_at=recent_ts))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=dimension")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Only the recent eval should count; overall_avg must be 5.0 (not 3.0)
    assert data["overall_avg"] == pytest.approx(5.0, abs=0.01)


def test_divergence_detection_above_threshold(app_client):
    """Divergence > 1.5 between eval score and normalised user_rating is flagged."""
    client, db = app_client
    _seed_user(db)

    # Eval says grounding = 4.5; users give thumbs down → normalised 1.0
    # divergence = |4.5 - 1.0| = 3.5 > 1.5
    for _ in range(3):
        run = _make_run(db)
        db.add(_make_eval(run, scores={"grounding": 4.5}, overall=4.5, user_rating=-1))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=dimension")
    assert resp.status_code == 200
    data = resp.json()["data"]
    alerts = data["divergence_alerts"]
    assert len(alerts) >= 1
    grounding_alert = next((a for a in alerts if a["dimension"] == "grounding"), None)
    assert grounding_alert is not None
    assert grounding_alert["divergence"] > 1.5


def test_divergence_detection_below_threshold(app_client):
    """Divergence <= 1.5 is NOT flagged."""
    client, db = app_client
    _seed_user(db)

    run = _make_run(db)
    # Eval says clarity = 4.0; user thumbs up → normalised 5.0
    # divergence = |4.0 - 5.0| = 1.0 ≤ 1.5 → no alert
    db.add(_make_eval(run, scores={"clarity_nodiv": 4.0}, overall=4.0, user_rating=1))
    db.commit()

    resp = client.get("/api/v1/analytics/eval-trends?period=7d&group_by=dimension")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # no alert for clarity_nodiv
    alerts = [a for a in data["divergence_alerts"] if a["dimension"] == "clarity_nodiv"]
    assert alerts == []


def test_worst_dimensions_sorted_ascending(app_client):
    """worst-dimensions returns dimensions sorted by avg_score ascending."""
    client, db = app_client
    _seed_user(db)

    run = _make_run(db)
    db.add(_make_eval(
        run,
        scores={"ws_grounding": 1.5, "ws_completeness": 3.0, "ws_goal_alignment": 4.5},
        overall=3.0,
    ))
    db.commit()

    resp = client.get("/api/v1/analytics/worst-dimensions?period=7d")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    worst = body["data"]["worst"]
    assert len(worst) >= 1
    # Lowest score first
    assert worst[0]["dimension"] == "ws_grounding"
    assert worst[0]["avg_score"] == pytest.approx(1.5, abs=0.01)


def test_worst_dimensions_respects_top_n(app_client):
    """top_n parameter limits the number of dimensions returned."""
    client, db = app_client
    _seed_user(db)

    run = _make_run(db)
    db.add(_make_eval(
        run,
        scores={"tn_a": 1.0, "tn_b": 2.0, "tn_c": 3.0, "tn_d": 4.0, "tn_e": 5.0},
        overall=3.0,
    ))
    db.commit()

    resp = client.get("/api/v1/analytics/worst-dimensions?period=7d&top_n=2")
    assert resp.status_code == 200
    worst = resp.json()["data"]["worst"]
    assert len(worst) == 2
    keys = {w["dimension"] for w in worst}
    assert "tn_a" in keys
    assert "tn_b" in keys
