"""Tests for RLS1 — Postgres Row-Level Security.

Verifies:
- Migration 025 has correct metadata (revision chain, dialect guard).
- set_domain_context is a no-op on SQLite (test DB dialect).
- set_domain_context issues the correct SQL on Postgres dialect.
- clear_domain_context delegates to set_domain_context with empty string.
- Policy naming convention matches what the migration creates.
- downgrade cleans up all policies.

RLS enforcement itself (actual row filtering) is a Postgres-only behaviour
tested via integration tests in tests/integration/ when a real Postgres DB
is available.  The unit tests here focus on the guard logic and SQL emitted.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_migration(name: str) -> ModuleType:
    path = VERSIONS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Migration metadata
# ---------------------------------------------------------------------------


class TestMigration025Metadata:
    def test_revision_is_025(self) -> None:
        mod = _load_migration("025_row_level_security")
        assert mod.revision == "025"

    def test_down_revision_is_024(self) -> None:
        mod = _load_migration("025_row_level_security")
        assert mod.down_revision == "024"

    def test_domain_tables_list(self) -> None:
        mod = _load_migration("025_row_level_security")
        tables = mod.DOMAIN_TABLES
        assert "conversations" in tables
        assert "approvals" in tables
        assert "memory_facts" in tables
        assert "audit_log" in tables
        assert "custom_tools" in tables

    def test_runs_table_not_in_domain_tables(self) -> None:
        """runs uses privacy_mode, handled separately in the migration."""
        mod = _load_migration("025_row_level_security")
        assert "runs" not in mod.DOMAIN_TABLES


# ---------------------------------------------------------------------------
# Migration dialect guard
# ---------------------------------------------------------------------------


class TestMigration025DialectGuard:
    def test_upgrade_skips_non_postgres(self) -> None:
        """upgrade() must return without issuing any SQL on non-Postgres dialects."""
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute") as mock_exec:
            mod.upgrade()
            mock_exec.assert_not_called()

    def test_downgrade_skips_non_postgres(self) -> None:
        """downgrade() must return without issuing any SQL on non-Postgres dialects."""
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute") as mock_exec:
            mod.downgrade()
            mock_exec.assert_not_called()

    def test_upgrade_executes_on_postgres(self) -> None:
        """upgrade() must call op.execute at least once per table on Postgres."""
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute") as mock_exec, \
             patch("sqlalchemy.text", side_effect=lambda x: x):
            mod.upgrade()
            # 5 domain tables × 5 statements (ENABLE + 4 policies) + 6 for runs = 31
            assert mock_exec.call_count >= 30

    def test_downgrade_executes_on_postgres(self) -> None:
        """downgrade() must call op.execute at least once per table on Postgres."""
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute") as mock_exec, \
             patch("sqlalchemy.text", side_effect=lambda x: x):
            mod.downgrade()
            # 6 tables × (4 DROP POLICY + 1 DISABLE) = 30
            assert mock_exec.call_count >= 30


# ---------------------------------------------------------------------------
# Policy naming convention
# ---------------------------------------------------------------------------


class TestPolicyNaming:
    """Policy names must follow the {table}_domain_{action} convention."""

    def test_upgrade_sql_contains_correct_policy_names(self) -> None:
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        executed_sql: list[str] = []

        def capture(stmt: object) -> None:
            executed_sql.append(str(stmt))

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute", side_effect=capture), \
             patch("sqlalchemy.text", side_effect=lambda x: x):
            mod.upgrade()

        policy_sql = [s for s in executed_sql if "CREATE POLICY" in s]
        # Each domain table must have 4 policies
        for table in mod.DOMAIN_TABLES:
            for action in ("select", "insert", "update", "delete"):
                expected = f"{table}_domain_{action}"
                assert any(expected in s for s in policy_sql), (
                    f"Missing policy {expected!r} in upgrade SQL"
                )

        # runs table policies
        for action in ("select", "insert", "update", "delete"):
            expected = f"runs_domain_{action}"
            assert any(expected in s for s in policy_sql), (
                f"Missing policy {expected!r} in upgrade SQL for runs"
            )

    def test_downgrade_sql_drops_correct_policy_names(self) -> None:
        mod = _load_migration("025_row_level_security")
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        executed_sql: list[str] = []

        def capture(stmt: object) -> None:
            executed_sql.append(str(stmt))

        with patch("alembic.op.get_bind", return_value=mock_bind), \
             patch("alembic.op.execute", side_effect=capture), \
             patch("sqlalchemy.text", side_effect=lambda x: x):
            mod.downgrade()

        drop_sql = [s for s in executed_sql if "DROP POLICY" in s]
        all_tables = list(mod.DOMAIN_TABLES) + ["runs"]
        for table in all_tables:
            for action in ("select", "insert", "update", "delete"):
                expected = f"{table}_domain_{action}"
                assert any(expected in s for s in drop_sql), (
                    f"Missing DROP POLICY for {expected!r}"
                )


# ---------------------------------------------------------------------------
# RLS context helpers — set_domain_context / clear_domain_context
# ---------------------------------------------------------------------------


class TestSetDomainContextSQLite:
    """On SQLite the helpers must be silent no-ops."""

    @pytest.mark.asyncio
    async def test_no_sql_on_sqlite(self) -> None:
        """set_domain_context must not execute any SQL against a SQLite session."""
        from noa.db.rls import set_domain_context

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            # Should not raise and should not execute any SQL
            # (SQLite ignores `set_config` which is Postgres-only)
            await set_domain_context(session, "private")
            await set_domain_context(session, "external")
            await set_domain_context(session, "")
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_clear_domain_context_sqlite(self) -> None:
        """clear_domain_context must not raise on SQLite."""
        from noa.db.rls import clear_domain_context

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await clear_domain_context(session)
        await engine.dispose()


class TestSetDomainContextPostgres:
    """On a mocked Postgres session the correct SQL must be emitted."""

    @pytest.mark.asyncio
    async def test_emits_set_config_sql(self) -> None:
        """set_domain_context must call session.execute with the correct SQL."""
        from noa.db.rls import set_domain_context

        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        # Simulate a Postgres-backed sync session
        sync_sess = MagicMock()
        sync_bind = MagicMock()
        sync_bind.dialect.name = "postgresql"
        sync_sess.get_bind.return_value = sync_bind
        session.sync_session = sync_sess

        await set_domain_context(session, "private")

        session.execute.assert_called_once()
        call_args = session.execute.call_args
        # First positional arg must be a text() with set_config
        sql_stmt = call_args[0][0]
        assert "set_config" in str(sql_stmt)
        # Second positional arg must be the params dict
        params = call_args[0][1]
        assert params == {"domain": "private"}

    @pytest.mark.asyncio
    async def test_emits_correct_domain_value(self) -> None:
        """The domain value passed must be forwarded to set_config unchanged."""
        from noa.db.rls import set_domain_context

        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        sync_sess = MagicMock()
        sync_bind = MagicMock()
        sync_bind.dialect.name = "postgresql"
        sync_sess.get_bind.return_value = sync_bind
        session.sync_session = sync_sess

        await set_domain_context(session, "external")

        params = session.execute.call_args[0][1]
        assert params["domain"] == "external"

    @pytest.mark.asyncio
    async def test_clear_delegates_with_empty_string(self) -> None:
        """clear_domain_context must call set_domain_context with domain=''."""
        from noa.db.rls import clear_domain_context

        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        sync_sess = MagicMock()
        sync_bind = MagicMock()
        sync_bind.dialect.name = "postgresql"
        sync_sess.get_bind.return_value = sync_bind
        session.sync_session = sync_sess

        await clear_domain_context(session)

        session.execute.assert_called_once()
        params = session.execute.call_args[0][1]
        assert params["domain"] == ""


# ---------------------------------------------------------------------------
# Integration: set_domain_context on a real SQLite async session (no-op path)
# ---------------------------------------------------------------------------


class TestSetDomainContextIntegration:
    """Full round-trip: real async SQLite session, RLS helper is a no-op."""

    @pytest.mark.asyncio
    async def test_sqlite_session_survives_set_domain_context(self) -> None:
        """A full async SQLite session remains usable after set_domain_context."""
        from noa.db.rls import set_domain_context

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await set_domain_context(session, "private")
            # Session must still be usable for queries
            result = await session.execute(sa.text("SELECT 1"))
            row = result.scalar()
            assert row == 1
        await engine.dispose()
