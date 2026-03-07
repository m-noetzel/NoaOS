"""Application-level state shared across modules."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from noa.queue.health import HealthChecker

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_health_checker: HealthChecker | None = None
_provider_router: Any | None = None
_runner: Any | None = None
_gateway: Any | None = None


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


def set_provider_router(router: Any) -> None:
    """Store the ProviderRouter globally."""
    global _provider_router  # noqa: PLW0603
    _provider_router = router


def get_provider_router() -> Any | None:
    """Return the current ProviderRouter (may be None)."""
    return _provider_router


def set_runner(runner: Any) -> None:
    """Store the OrchestratorRunner globally."""
    global _runner  # noqa: PLW0603
    _runner = runner


def get_runner() -> Any | None:
    """Return the current OrchestratorRunner (may be None)."""
    return _runner


def set_gateway(gateway: Any) -> None:
    """Store the ToolGateway globally."""
    global _gateway  # noqa: PLW0603
    _gateway = gateway


def get_gateway() -> Any | None:
    """Return the current ToolGateway (may be None)."""
    return _gateway


def reset_all() -> None:
    """Reset all global state to None.

    Useful for testing and clean shutdown.  Phase QC8 / A1.
    """
    global _engine, _session_factory, _health_checker  # noqa: PLW0603
    global _provider_router, _runner, _gateway  # noqa: PLW0603
    _engine = None
    _session_factory = None
    _health_checker = None
    _provider_router = None
    _runner = None
    _gateway = None
