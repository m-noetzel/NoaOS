"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.app_state import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    async with factory() as session:
        yield session


async def get_domain_db_session(
    domain: str,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session with RLS domain context set (RLS1).

    On Postgres this sets ``noa.domain`` via ``set_config()`` (transaction-local)
    so that row-level security policies automatically enforce domain isolation.
    On SQLite (tests) the call is a no-op; application-level WHERE clauses
    remain as defence-in-depth.

    Args:
        domain: ``"private"`` or ``"external"``.  Pass ``""`` to clear the
                restriction (admin / cross-domain queries).
    """
    from noa.db.rls import set_domain_context

    factory = get_session_factory()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    async with factory() as session:
        await set_domain_context(session, domain)
        yield session


async def get_current_user() -> dict[str, Any]:
    """Placeholder for user authentication — implemented in F4."""
    return {"id": "anonymous", "role": "guest"}
