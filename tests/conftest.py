"""Shared pytest fixtures for Noa test suite."""

import pytest


@pytest.fixture
def test_settings(monkeypatch):
    """Provide test-safe settings with all env vars set."""
    monkeypatch.setenv("NOA_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    from noa.config import Settings

    return Settings()
