"""Application-level state — FastAPI app.state backed with module fallback.

Resolves A1: services are stored on the FastAPI app.state instance during
lifespan, eliminating module-level mutable globals as the primary store.
The module-level variables remain only as a fallback for contexts where
the app instance is not available (e.g., CLI scripts, early startup).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from noa.queue.health import HealthChecker

# The FastAPI app instance — set once at startup
_app_instance: Any | None = None

# Module-level fallbacks (used before app is created or in non-request contexts)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_health_checker: HealthChecker | None = None
_provider_router: Any | None = None
_runner: Any | None = None
_gateway: Any | None = None


def set_app(app: Any) -> None:
    """Register the FastAPI app instance for state storage."""
    global _app_instance  # noqa: PLW0603
    _app_instance = app


def _get_from_app(key: str) -> Any:
    """Try to read from app.state first."""
    if _app_instance is not None:
        return getattr(_app_instance.state, key, None)
    return None


def _set_on_app(key: str, value: Any) -> None:
    """Store on app.state if available."""
    if _app_instance is not None:
        setattr(_app_instance.state, key, value)


def set_engine(engine: AsyncEngine) -> None:
    global _engine  # noqa: PLW0603
    _engine = engine
    _set_on_app("engine", engine)


def get_engine() -> AsyncEngine | None:
    return _get_from_app("engine") or _engine


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    global _session_factory  # noqa: PLW0603
    _session_factory = factory
    _set_on_app("session_factory", factory)


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    return _get_from_app("session_factory") or _session_factory


def set_health_checker(checker: HealthChecker) -> None:
    global _health_checker  # noqa: PLW0603
    _health_checker = checker
    _set_on_app("health_checker", checker)


def get_health_checker() -> HealthChecker | None:
    return _get_from_app("health_checker") or _health_checker


def set_provider_router(router: Any) -> None:
    global _provider_router  # noqa: PLW0603
    _provider_router = router
    _set_on_app("provider_router", router)


def get_provider_router() -> Any | None:
    return _get_from_app("provider_router") or _provider_router


def set_runner(runner: Any) -> None:
    global _runner  # noqa: PLW0603
    _runner = runner
    _set_on_app("runner", runner)


def get_runner() -> Any | None:
    return _get_from_app("runner") or _runner


def set_gateway(gateway: Any) -> None:
    global _gateway  # noqa: PLW0603
    _gateway = gateway
    _set_on_app("gateway", gateway)


def get_gateway() -> Any | None:
    return _get_from_app("gateway") or _gateway


_apns_service: Any | None = None


def set_apns_service(service: Any) -> None:
    global _apns_service  # noqa: PLW0603
    _apns_service = service
    _set_on_app("apns_service", service)


def get_apns_service() -> Any | None:
    return _get_from_app("apns_service") or _apns_service


_memory_store: Any | None = None


def set_memory_store(store: Any) -> None:
    global _memory_store  # noqa: PLW0603
    _memory_store = store
    _set_on_app("memory_store", store)


def get_memory_store() -> Any | None:
    return _get_from_app("memory_store") or _memory_store


def reset_all() -> None:
    """Reset all state — for testing."""
    global _engine, _session_factory, _health_checker  # noqa: PLW0603
    global _provider_router, _runner, _gateway, _app_instance  # noqa: PLW0603
    global _apns_service, _memory_store  # noqa: PLW0603
    _engine = None
    _session_factory = None
    _health_checker = None
    _provider_router = None
    _runner = None
    _gateway = None
    _app_instance = None
    _apns_service = None
    _memory_store = None
