"""Transaction abstraction — async context manager for commit/rollback.

Phase QC8 / A5.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


@asynccontextmanager
async def transactional(session: Any) -> AsyncIterator[Any]:
    """Async context manager that commits on success, rolls back on error.

    Usage::

        async with transactional(session):
            session.add(obj)

    On successful exit, ``session.commit()`` is awaited.
    On exception, ``session.rollback()`` is awaited and the exception
    is re-raised.

    Args:
        session: An async SQLAlchemy session (or AsyncMock in tests).

    Yields:
        The session itself.
    """
    try:
        yield session
        await session.commit()
    except Exception:  # noqa: BLE001 — re-raised after rollback
        await session.rollback()
        raise
