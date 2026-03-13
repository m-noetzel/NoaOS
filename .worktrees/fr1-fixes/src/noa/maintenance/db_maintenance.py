"""Postgres DB maintenance scheduler — pool stats, VACUUM, index bloat — OP4."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class DbMaintenanceScheduler:
    """Background scheduler for Postgres maintenance tasks.

    Periodically runs VACUUM ANALYZE and index-bloat checks.
    Also exposes pool statistics for the health endpoint.
    """

    def __init__(
        self, engine: AsyncEngine, interval_hours: int = 24
    ) -> None:
        self._engine = engine
        self._interval_seconds = interval_hours * 3600
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background maintenance loop."""
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "DbMaintenanceScheduler started (interval=%ds)",
            self._interval_seconds,
        )

    async def stop(self) -> None:
        """Stop the background task."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("DbMaintenanceScheduler stopped")

    async def _loop(self) -> None:
        """Run maintenance on a fixed interval."""
        while True:
            await asyncio.sleep(self._interval_seconds)
            try:
                await self.run_vacuum_analyze()
                bloat = await self.check_index_bloat()
                if bloat:
                    logger.info("Index bloat report: %s", bloat)
            except Exception:  # noqa: BLE001
                logger.exception("Maintenance cycle failed")

    # ------------------------------------------------------------------
    # Maintenance operations
    # ------------------------------------------------------------------

    async def run_vacuum_analyze(self) -> None:
        """Run VACUUM ANALYZE on key tables.

        VACUUM cannot run inside a transaction, so we use a raw
        (driver-level) connection with autocommit.
        """
        tables = ["audit_log", "runs"]
        raw_conn = await self._engine.raw_connection()
        try:
            driver = raw_conn.driver_connection
            for table in tables:
                await driver.execute(f"VACUUM ANALYZE {table}")  # type: ignore[union-attr]
                logger.info("VACUUM ANALYZE %s complete", table)
        finally:
            await raw_conn.close()  # type: ignore[func-returns-value]

    async def check_index_bloat(self) -> list[dict[str, Any]]:
        """Query pg_stat_user_indexes for bloat indicators.

        Returns a list of dicts with keys: schema, table, index,
        size_bytes, scans.
        """
        query = sa.text(
            """
            SELECT
                schemaname,
                relname,
                indexrelname,
                pg_relation_size(indexrelid) AS size_bytes,
                idx_scan
            FROM pg_stat_user_indexes
            ORDER BY pg_relation_size(indexrelid) DESC
            """
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        return [
            {
                "schema": row[0],
                "table": row[1],
                "index": row[2],
                "size_bytes": row[3],
                "scans": row[4],
            }
            for row in rows
        ]

    async def get_pool_stats(self) -> dict[str, int]:
        """Return current connection pool statistics."""
        pool: Any = self._engine.pool
        return {
            "pool_size": pool.size(),
            "pool_checkedin": pool.checkedin(),
            "pool_checkedout": pool.checkedout(),
            "pool_overflow": pool.overflow(),
        }
