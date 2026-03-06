"""Tests for DB maintenance: pool tuning, VACUUM, index bloat, pool stats — OP4."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.maintenance.db_maintenance import DbMaintenanceScheduler


# ---------------------------------------------------------------------------
# Engine pool parameter tests
# ---------------------------------------------------------------------------


class TestEnginePoolParameters:
    """Verify create_async_engine_from_config sets correct pool params."""

    @patch("noa.db.engine.create_async_engine")
    def test_pool_size(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["pool_size"] == 10

    @patch("noa.db.engine.create_async_engine")
    def test_max_overflow(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["max_overflow"] == 20

    @patch("noa.db.engine.create_async_engine")
    def test_pool_recycle(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["pool_recycle"] == 1800

    @patch("noa.db.engine.create_async_engine")
    def test_pool_timeout(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["pool_timeout"] == 30

    @patch("noa.db.engine.create_async_engine")
    def test_all_pool_params_together(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["pool_size"] == 10
        assert kwargs["max_overflow"] == 20
        assert kwargs["pool_recycle"] == 1800
        assert kwargs["pool_timeout"] == 30
        assert kwargs["pool_pre_ping"] is True


# ---------------------------------------------------------------------------
# VACUUM ANALYZE tests
# ---------------------------------------------------------------------------


class TestVacuumAnalyze:
    """VACUUM ANALYZE executes correct SQL via raw connection."""

    @pytest.mark.asyncio
    async def test_vacuum_analyze_executes_sql(self) -> None:
        engine = MagicMock()
        raw_conn = AsyncMock()
        # engine.raw_connection() returns an awaitable that yields raw_conn
        engine.raw_connection = AsyncMock(return_value=raw_conn)
        raw_conn.driver_connection = AsyncMock()
        raw_conn.driver_connection.execute = AsyncMock()
        raw_conn.close = AsyncMock()

        scheduler = DbMaintenanceScheduler(engine=engine, interval_hours=24)
        await scheduler.run_vacuum_analyze()

        # Should have called execute at least once with VACUUM ANALYZE
        calls = raw_conn.driver_connection.execute.call_args_list
        assert len(calls) > 0
        sql_texts = [str(c[0][0]) for c in calls]
        vacuum_calls = [s for s in sql_texts if "VACUUM ANALYZE" in s.upper()]
        assert len(vacuum_calls) > 0, f"Expected VACUUM ANALYZE calls, got: {sql_texts}"


# ---------------------------------------------------------------------------
# Index bloat check tests
# ---------------------------------------------------------------------------


class TestIndexBloatCheck:
    """check_index_bloat returns valid stats structure."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self) -> None:
        engine = MagicMock()

        # Mock engine.connect() -> async context manager -> conn
        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        engine.connect = MagicMock(return_value=mock_ctx)

        # Mock result set
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("public", "my_table", "my_index", 8192, 100),
        ]
        mock_conn.execute = AsyncMock(return_value=mock_result)

        scheduler = DbMaintenanceScheduler(engine=engine)
        result = await scheduler.check_index_bloat()

        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        assert "table" in row
        assert "index" in row
        assert "size_bytes" in row
        assert "scans" in row

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        engine = MagicMock()
        mock_conn = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        engine.connect = MagicMock(return_value=mock_ctx)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)

        scheduler = DbMaintenanceScheduler(engine=engine)
        result = await scheduler.check_index_bloat()

        assert result == []


# ---------------------------------------------------------------------------
# Pool stats tests
# ---------------------------------------------------------------------------


class TestPoolStats:
    """get_pool_stats returns connection count info."""

    @pytest.mark.asyncio
    async def test_pool_stats_structure(self) -> None:
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 8
        pool.checkedout.return_value = 2
        pool.overflow.return_value = 0
        engine.pool = pool

        scheduler = DbMaintenanceScheduler(engine=engine)
        stats = await scheduler.get_pool_stats()

        assert stats["pool_size"] == 10
        assert stats["pool_checkedin"] == 8
        assert stats["pool_checkedout"] == 2
        assert stats["pool_overflow"] == 0

    @pytest.mark.asyncio
    async def test_pool_stats_with_overflow(self) -> None:
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 0
        pool.checkedout.return_value = 10
        pool.overflow.return_value = 5
        engine.pool = pool

        scheduler = DbMaintenanceScheduler(engine=engine)
        stats = await scheduler.get_pool_stats()

        assert stats["pool_overflow"] == 5
        assert stats["pool_checkedout"] == 10


# ---------------------------------------------------------------------------
# pool_recycle parameter test
# ---------------------------------------------------------------------------


class TestPoolRecycle:
    """Connections older than 1800s are recycled."""

    @patch("noa.db.engine.create_async_engine")
    def test_pool_recycle_is_1800(self, mock_create: MagicMock) -> None:
        from noa.db.engine import create_async_engine_from_config

        settings = MagicMock()
        settings.database_url = "postgresql+asyncpg://u:p@localhost/test"
        settings.noa_env.value = "production"

        create_async_engine_from_config(settings)

        _, kwargs = mock_create.call_args
        assert kwargs["pool_recycle"] == 1800, (
            "pool_recycle should be 1800 to recycle connections after 30 min"
        )


# ---------------------------------------------------------------------------
# Start / stop lifecycle tests
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    """DbMaintenanceScheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        engine = MagicMock()
        scheduler = DbMaintenanceScheduler(engine=engine, interval_hours=24)
        assert scheduler._task is None

        # Patch _loop so it doesn't actually run
        with patch.object(scheduler, "_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler._task is not None
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        engine = MagicMock()
        scheduler = DbMaintenanceScheduler(engine=engine, interval_hours=24)

        with patch.object(scheduler, "_loop", new_callable=AsyncMock):
            await scheduler.start()
            task = scheduler._task
            await scheduler.stop()
            assert scheduler._task is None
