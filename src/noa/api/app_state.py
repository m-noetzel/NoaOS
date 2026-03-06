"""Application-level state shared across modules."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from noa.queue.health import HealthChecker

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_health_checker: HealthChecker | None = None


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


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Return the session factory (None before startup)."""
    return _session_factory


def set_health_checker(checker: HealthChecker) -> None:
    """Store the HealthChecker globally."""
    global _health_checker  # noqa: PLW0603
    _health_checker = checker


def get_health_checker() -> HealthChecker | None:
    """Return the current HealthChecker (may be None)."""
    return _health_checker
