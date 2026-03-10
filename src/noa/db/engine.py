"""Async database engine and session factory — SPEC.md §10.1."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from noa.config import Settings


def create_async_engine_from_config(
    settings: Settings | None = None,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine from app settings."""
    if settings is None:
        settings = Settings()
    url = settings.database_url
    # SQLite (used in tests) does not support connection pool parameters.
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {
        "echo": settings.noa_env.value == "development",
        "pool_pre_ping": not is_sqlite,
    }
    if not is_sqlite:
        kwargs.update(
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            pool_timeout=30,
        )
    return create_async_engine(url, **kwargs)


def async_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    if engine is None:
        engine = create_async_engine_from_config()
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
