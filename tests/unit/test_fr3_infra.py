"""FR3: Backend Data Integrity & Infra — tests.

Spec refs: SPEC.md §10.1 (threads), §28.7 (data integrity), §20.1 (security)

Findings addressed:
  W21-H1 — DELETE /threads returns 500 when runs+usage_stats exist
  W21-H2 — Backup container crash-loops from cap_drop (compose fix)
  W21-M1 — /docs and /openapi.json exposed unconditionally (env gating)
  W21-M2 — traceability.py --check overwrites TRACEABILITY.md

All tests use in-memory SQLite via real ASGI TestClient (no mocks).
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.fr3


# ---------------------------------------------------------------------------
# W21-H1: DELETE /threads — FK cascade when runs + usage_stats exist
# ---------------------------------------------------------------------------


async def _make_thread_with_run_and_usage(
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> object:
    """Create in-memory SQLite DB with a thread, a run, and a usage_stats row."""
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from noa.db.models.base import Base
    from noa.db.models.conversation import Conversation
    from noa.db.models.run import Run
    from noa.db.models.usage import UsageStats

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Seed: conversation (thread)
        conv = Conversation(id=thread_id, user_id=user_id, title="Thread With Run")
        session.add(conv)

        # Seed: run pointing to the thread
        run_id = uuid.uuid4()
        run = Run(
            id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            status="completed",
        )
        session.add(run)

        # Seed: usage_stats row pointing to the run
        usage = UsageStats(
            user_id=user_id,
            provider="openai",
            model_name="gpt-4.1-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.0001"),
            run_id=run_id,
        )
        session.add(usage)
        await session.commit()

    return factory


def _build_app(factory: object, user_id: uuid.UUID) -> object:
    """Return FastAPI app with DB and auth overrides."""
    from noa.api.app import create_app
    from noa.api.deps import get_db_session
    from noa.auth.middleware import AuthUser, require_auth

    app = create_app()

    async def _fake_auth() -> AuthUser:
        return AuthUser(user_id=user_id, session_id=uuid.uuid4())

    async def _fake_db():  # type: ignore[return]
        async with factory() as session:  # type: ignore[attr-defined]
            yield session

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[get_db_session] = _fake_db
    return app


class TestDeleteThreadWithData:
    """W21-H1: Thread deletion must succeed when runs and usage_stats exist."""

    @pytest.mark.asyncio
    async def test_delete_thread_with_run_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DELETE /threads/{id} returns 200 even when a run row exists for the thread.

        This is the regression test for W21-H1: the FK from runs to conversations
        has ondelete=CASCADE, so deleting the conversation cascades to runs.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        factory = await _make_thread_with_run_and_usage(user_id, thread_id)

        from httpx import ASGITransport, AsyncClient

        app = _build_app(factory, user_id)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/threads/{thread_id}")

        assert resp.status_code == 200, (
            f"DELETE /threads/{{id}} returned {resp.status_code} (expected 200). "
            f"Body: {resp.text[:500]}. "
            "W21-H1: FK cascade from runs to conversations must be in place."
        )

    @pytest.mark.asyncio
    async def test_delete_thread_with_usage_stats_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DELETE /threads/{id} returns 200 even when usage_stats rows exist for runs.

        The FK from usage_stats to runs uses ondelete=SET NULL, so deleting
        the run (via CASCADE from conversation) sets usage_stats.run_id = NULL.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from decimal import Decimal

        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from noa.db.models.base import Base
        from noa.db.models.conversation import Conversation
        from noa.db.models.run import Run
        from noa.db.models.usage import UsageStats

        user_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        run_id = uuid.uuid4()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            session.add(Conversation(id=thread_id, user_id=user_id, title="T"))
            session.add(Run(id=run_id, thread_id=thread_id, user_id=user_id, status="done"))
            session.add(UsageStats(
                user_id=user_id,
                provider="openai",
                model_name="gpt-4.1-mini",
                input_tokens=10,
                output_tokens=5,
                cost_usd=Decimal("0"),
                run_id=run_id,
            ))
            await session.commit()

        from httpx import ASGITransport, AsyncClient

        app = _build_app(factory, user_id)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/threads/{thread_id}")

        assert resp.status_code == 200, (
            f"DELETE returned {resp.status_code}: {resp.text[:300]}"
        )

        # Verify the thread is gone (conversation was deleted)
        async with factory() as session:
            from noa.db.models.conversation import Conversation as _Conv  # noqa: I001
            from sqlalchemy import select
            result = await session.execute(
                select(_Conv).where(_Conv.id == thread_id)
            )
            assert result.scalar_one_or_none() is None, (
                "Conversation row should be deleted after DELETE /threads/{id}."
            )

        # Note: in SQLite without PRAGMA foreign_keys=ON, SET NULL is not enforced.
        # The ORM model declaration is validated by test_usage_stats_fk_model_has_set_null.
        # The Postgres behavior (SET NULL) is validated by the integration tests.

    @pytest.mark.asyncio
    async def test_usage_stats_fk_model_has_set_null(self) -> None:
        """W21-H1: UsageStats.run_id FK ondelete must be SET NULL in the ORM model."""
        from noa.db.models.usage import UsageStats

        table = UsageStats.__table__
        fk_on_delete = None
        for fk in table.foreign_keys:
            if fk.column.table.name == "runs":
                fk_on_delete = fk.ondelete
                break

        assert fk_on_delete is not None, "UsageStats.run_id has no FK to runs table"
        assert fk_on_delete.upper() == "SET NULL", (
            f"UsageStats.run_id FK ondelete={fk_on_delete!r}, expected SET NULL. "
            "W21-H1: must be SET NULL so thread deletes don't fail."
        )

    def test_migration_015_exists(self) -> None:
        """W21-H1: Migration 015 must exist to ensure FK fix is applied on all engines."""
        repo_root = Path(__file__).parents[2]
        migration = repo_root / "alembic/versions/015_cascade_thread_delete.py"
        assert migration.exists(), (
            f"Migration 015 not found at {migration}. "
            "W21-H1 fix requires a migration to apply the ON DELETE SET NULL constraint."
        )


# ---------------------------------------------------------------------------
# W21-H2: Backup container — compose config must not cap_drop all capabilities
# ---------------------------------------------------------------------------


class TestBackupContainerConfig:
    """W21-H2: Backup service must not have cap_drop: ALL (needs SETUID/SETGID for dcron)."""

    def test_backup_service_has_no_cap_drop_all(self) -> None:
        """docker-compose.yml backup service must not have 'cap_drop: [ALL]'.

        DE3 hardening added cap_drop to all services, but the backup container
        runs dcron which needs SETUID/SETGID capabilities to fork cron jobs.
        The backup service is exempt from the cap_drop hardening (§8.1 exemption).
        """
        import yaml  # type: ignore[import-untyped]

        repo_root = Path(__file__).parents[2]
        compose_path = repo_root / "docker-compose.yml"

        with compose_path.open() as f:
            compose = yaml.safe_load(f)

        backup_svc = compose.get("services", {}).get("backup", {})
        assert backup_svc, "backup service not found in docker-compose.yml"

        cap_drop = backup_svc.get("cap_drop", [])
        assert "ALL" not in cap_drop and "all" not in [c.lower() for c in cap_drop], (
            "backup service has cap_drop: ALL. "
            "W21-H2: dcron needs SETUID/SETGID — backup is exempt from cap_drop hardening."
        )

    def test_backup_service_has_init_true(self) -> None:
        """backup service must have init: true to prevent PID 1 setpgid issues.

        When cron is PID 1, setpgid() fails with EPERM. init: true runs a minimal
        init process as PID 1 so crond can fork cleanly.
        """
        import yaml  # type: ignore[import-untyped]

        repo_root = Path(__file__).parents[2]
        compose_path = repo_root / "docker-compose.yml"

        with compose_path.open() as f:
            compose = yaml.safe_load(f)

        backup_svc = compose.get("services", {}).get("backup", {})
        assert backup_svc.get("init") is True, (
            "backup service is missing 'init: true'. "
            "W21-H2: init: true is required to prevent crond setpgid permission denied."
        )


# ---------------------------------------------------------------------------
# W21-M1: OpenAPI docs gated behind NOA_ENV != production
# ---------------------------------------------------------------------------


class TestOpenAPIDocsGating:
    """W21-M1: /docs and /openapi.json must not be exposed in production."""

    def test_docs_hidden_when_noa_env_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When NOA_ENV=production, FastAPI must be created with docs_url=None."""
        monkeypatch.setenv("NOA_ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        # Force a fresh app creation (not the cached module-level app)
        from noa.api.app import create_app

        app = create_app()

        assert app.docs_url is None, (
            f"docs_url={app.docs_url!r} when NOA_ENV=production (expected None). "
            "W21-M1: /docs must not be accessible in production."
        )
        assert app.redoc_url is None, (
            f"redoc_url={app.redoc_url!r} when NOA_ENV=production (expected None). "
            "W21-M1: /redoc must not be accessible in production."
        )
        assert app.openapi_url is None, (
            f"openapi_url={app.openapi_url!r} when NOA_ENV=production (expected None). "
            "W21-M1: /openapi.json must not be accessible in production."
        )

    def test_docs_visible_when_noa_env_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When NOA_ENV=development, /docs and /openapi.json must be accessible."""
        monkeypatch.setenv("NOA_ENV", "development")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from noa.api.app import create_app

        app = create_app()

        assert app.docs_url is not None, (
            "docs_url=None when NOA_ENV=development. "
            "W21-M1 fix must only suppress docs in production, not development."
        )
        assert app.openapi_url is not None, (
            "openapi_url=None when NOA_ENV=development. "
            "W21-M1 fix must only suppress docs in production, not development."
        )

    def test_docs_hidden_when_environment_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENVIRONMENT=production (legacy var) also hides docs — fallback support.

        NOA_ENV is cleared so ENVIRONMENT takes sole precedence.
        """
        monkeypatch.delenv("NOA_ENV", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from noa.api.app import create_app

        app = create_app()

        assert app.docs_url is None, (
            f"docs_url={app.docs_url!r} when ENVIRONMENT=production (expected None). "
            "W21-M1: ENVIRONMENT=production must also suppress docs."
        )

    @pytest.mark.asyncio
    async def test_openapi_endpoint_returns_404_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /openapi.json returns 404 when NOA_ENV=production."""
        monkeypatch.setenv("NOA_ENV", "production")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.setenv("SECRET_KEY", "test-secret")

        from noa.api.app import create_app  # noqa: I001
        from httpx import ASGITransport, AsyncClient

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/openapi.json")

        assert resp.status_code == 404, (
            f"GET /openapi.json returned {resp.status_code} in production mode (expected 404). "
            "W21-M1: OpenAPI schema must not be accessible in production."
        )


# ---------------------------------------------------------------------------
# W21-M2: traceability.py --check must not overwrite TRACEABILITY.md
# ---------------------------------------------------------------------------


class TestTraceabilityCheckMode:
    """W21-M2: traceability.py --check must be read-only (no file writes)."""

    def test_check_mode_does_not_write_output_file(self) -> None:
        """run(check_mode=True) must not write or modify the output file."""
        import sys

        # Add tools/ to sys.path if needed
        repo_root = Path(__file__).parents[2]
        tools_dir = str(repo_root / "tools")
        added = False
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            added = True

        try:
            from traceability import run  # type: ignore[import-not-found]

            with tempfile.NamedTemporaryFile(
                suffix=".md", delete=False, mode="w", encoding="utf-8"
            ) as f:
                sentinel_content = "# ORIGINAL CONTENT — must not be overwritten"
                f.write(sentinel_content)
                tmp_path = Path(f.name)

            try:
                # Run in check mode — must not modify the file
                run(output_path=tmp_path, check_mode=True)

                actual = tmp_path.read_text(encoding="utf-8")
                assert actual == sentinel_content, (
                    "traceability.py --check overwrote the output file. "
                    "W21-M2: --check must be read-only. "
                    f"File was changed to: {actual[:200]!r}"
                )
            finally:
                tmp_path.unlink(missing_ok=True)
        finally:
            if added and tools_dir in sys.path:
                sys.path.remove(tools_dir)

    def test_check_mode_none_output_still_works(self) -> None:
        """run(output_path=None, check_mode=True) must run analysis without writing."""
        import sys

        repo_root = Path(__file__).parents[2]
        tools_dir = str(repo_root / "tools")
        added = False
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            added = True

        try:
            from traceability import run  # type: ignore[import-not-found]

            # output_path=None + check_mode=True: should not raise, just analyze
            result = run(output_path=None, check_mode=True)
            assert isinstance(result, int), (
                f"run() must return an int exit code, got {type(result)}"
            )
        finally:
            if added and tools_dir in sys.path:
                sys.path.remove(tools_dir)

    def test_non_check_mode_writes_file(self) -> None:
        """run(check_mode=False) must still write the output file (normal mode)."""
        import sys

        repo_root = Path(__file__).parents[2]
        tools_dir = str(repo_root / "tools")
        added = False
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            added = True

        try:
            from traceability import run  # type: ignore[import-not-found]

            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / "TRACEABILITY.md"
                run(output_path=out, check_mode=False)
                assert out.exists(), (
                    "traceability.py without --check should write the output file, "
                    "but the file was not created."
                )
                content = out.read_text(encoding="utf-8")
                assert "Requirements Traceability Matrix" in content, (
                    "Output file does not look like a traceability matrix."
                )
        finally:
            if added and tools_dir in sys.path:
                sys.path.remove(tools_dir)

    def test_check_mode_preserves_manual_sections(self) -> None:
        """--check must not touch manual sections (sentinel preservation)."""
        import sys

        repo_root = Path(__file__).parents[2]
        tools_dir = str(repo_root / "tools")
        added = False
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            added = True

        try:
            from traceability import run  # type: ignore[import-not-found]

            sentinel = "<!-- MANUAL SECTIONS -->"
            manual_content = f"{sentinel}\n## My Manual Section\n\nCustom notes here.\n"

            with tempfile.NamedTemporaryFile(
                suffix=".md", delete=False, mode="w", encoding="utf-8"
            ) as f:
                f.write(manual_content)
                tmp_path = Path(f.name)

            try:
                run(output_path=tmp_path, check_mode=True)

                actual = tmp_path.read_text(encoding="utf-8")
                assert actual == manual_content, (
                    "--check modified the output file (even though it contains manual sections). "
                    f"Expected unchanged content, got: {actual[:300]!r}"
                )
            finally:
                tmp_path.unlink(missing_ok=True)
        finally:
            if added and tools_dir in sys.path:
                sys.path.remove(tools_dir)
