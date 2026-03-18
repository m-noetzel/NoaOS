"""Shared pytest fixtures for Noa test suite."""

import pytest


@pytest.fixture(autouse=True)
def _reset_app_state():
    """Reset module-level app state between tests."""
    yield
    from noa.api.app_state import reset_all
    reset_all()


@pytest.fixture
def test_settings(monkeypatch):
    """Provide test-safe settings with all env vars set."""
    monkeypatch.setenv("NOA_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    from noa.config import Settings

    return Settings()
