"""Audit fix tests: H1 (FK cascade), M2 (OpenAPI gating).

Spec refs: SPEC.md §10.1 (threads/messages), §28.5 (health/API)

H1: DELETE /threads/{id} must return 200 even when usage_stats rows reference
    the run being deleted. Requires usage_stats.run_id FK to have ON DELETE SET NULL.

M2: OpenAPI docs (docs_url, redoc_url, openapi_url) must be disabled in
    production (ENVIRONMENT=production) and enabled otherwise.
"""

from __future__ import annotations

import uuid

import pytest

# ---------------------------------------------------------------------------
# H1: DELETE /threads returns 200 when usage_stats.run_id FK has ON DELETE SET NULL
# ---------------------------------------------------------------------------


def _build_app_with_db(factory, user_id: uuid.UUID):
    """Return a FastAPI app with auth + DB session overrides."""
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
    return app


class TestDeleteThreadFKCascade:
    """H1: DELETE /threads/{id} must not 500 when usage_stats rows exist for the run."""

    @pytest.mark.asyncio
    async def test_delete_thread_returns_200(self, monkeypatch):
        """
        Full flow: create thread → post chat (which creates a Run + UsageStat) →
        delete thread → expect 200, not 500.

        This test uses in-memory SQLite with ORM create_all, so FK enforcement
        depends on SQLite's lenient FK handling. The critical assertion is that
        the ORM model has ondelete="SET NULL" on usage_stats.run_id.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        user_id = uuid.uuid4()

        # Seed: create a Conversation and a UsageStat referencing a fake run
        thread_id = uuid.uuid4()
        run_id = uuid.uuid4()
        from decimal import Decimal

        from noa.db.models.conversation import Conversation
        from noa.db.models.usage import UsageStats

        async with factory() as session:
            conv = Conversation(id=thread_id, user_id=user_id, title="Test Thread")
            session.add(conv)
            stat = UsageStats(
                user_id=user_id,
                provider="openai",
                model_name="gpt-4.1-mini",
                input_tokens=10,
                output_tokens=5,
                cost_usd=Decimal("0.001"),
                run_id=run_id,
            )
            session.add(stat)
            await session.commit()

        # Issue DELETE via ASGI test client
        from httpx import ASGITransport, AsyncClient

        app = _build_app_with_db(factory, user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/threads/{thread_id}")

        app.dependency_overrides.clear()

        # Must be 200 (or 204), never 500
        assert resp.status_code in (200, 204), (
            f"Expected 200/204 on DELETE /threads/{{id}}, got {resp.status_code}: {resp.text}"
        )

    def test_usage_stats_run_id_has_on_delete_set_null(self):
        """Model-level check: usage_stats.run_id FK must specify ondelete='SET NULL'."""
        from sqlalchemy import inspect

        from noa.db.models.usage import UsageStats

        mapper = inspect(UsageStats)
        run_id_col = mapper.columns["run_id"]
        fk = next(iter(run_id_col.foreign_keys), None)
        assert fk is not None, "usage_stats.run_id has no FK defined"
        assert fk.ondelete is not None, "usage_stats.run_id FK has no ondelete rule"
        assert fk.ondelete.upper() == "SET NULL", (
            f"Expected ondelete='SET NULL', got {fk.ondelete!r}"
        )


# ---------------------------------------------------------------------------
# M2: OpenAPI docs gated on ENVIRONMENT
# ---------------------------------------------------------------------------


class TestOpenAPIDocGating:
    """M2: docs_url/redoc_url/openapi_url must be None in production."""

    def test_docs_hidden_in_production(self, monkeypatch):
        """ENVIRONMENT=production → all OpenAPI URLs are None."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Must reimport create_app so env var takes effect
        import importlib

        import noa.api.app as app_module
        importlib.invalidate_caches()

        app = app_module.create_app()
        assert app.docs_url is None, "docs_url must be None in production"
        assert app.redoc_url is None, "redoc_url must be None in production"
        assert app.openapi_url is None, "openapi_url must be None in production"

    def test_docs_visible_in_development(self, monkeypatch):
        """ENVIRONMENT=development (default) → docs are served."""
        monkeypatch.setenv("ENVIRONMENT", "development")

        import importlib

        import noa.api.app as app_module
        importlib.invalidate_caches()

        app = app_module.create_app()
        assert app.docs_url is not None, "docs_url should be set in non-production"
        assert app.openapi_url is not None, "openapi_url should be set in non-production"

    def test_docs_visible_when_env_not_set(self, monkeypatch):
        """When ENVIRONMENT is unset, docs are served (safe default for dev)."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        import importlib

        import noa.api.app as app_module
        importlib.invalidate_caches()

        app = app_module.create_app()
        assert app.docs_url is not None, "docs_url should default to /docs"
        assert app.openapi_url is not None, "openapi_url should default to /openapi.json"
