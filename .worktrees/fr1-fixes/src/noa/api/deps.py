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


async def get_current_user() -> dict[str, Any]:
    """Placeholder for user authentication — implemented in F4."""
    return {"id": "anonymous", "role": "guest"}
