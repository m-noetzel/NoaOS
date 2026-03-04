"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.app_state import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_current_user() -> dict[str, Any]:
    """Placeholder for user authentication — implemented in F4."""
    return {"id": "anonymous", "role": "guest"}
