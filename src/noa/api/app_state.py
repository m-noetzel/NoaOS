"""Application-level state shared across modules."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_engine(engine: AsyncEngine) -> None:
    """Store the engine globally for the app lifetime."""
    global _engine  # noqa: PLW0603
    _engine = engine


def get_engine() -> AsyncEngine | None:
    """Return the current engine (may be None before startup)."""
    return _engine


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Store the session factory globally."""
    global _session_factory  # noqa: PLW0603
    _session_factory = factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory; raises if not initialised."""
    if _session_factory is None:
        msg = "Session factory not initialised — app not started?"
        raise RuntimeError(msg)
    return _session_factory
