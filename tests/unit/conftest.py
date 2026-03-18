"""Unit test configuration and shared fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_app_state():
    """Reset module-level app state between tests to prevent cross-test pollution."""
    yield
    from noa.api.app_state import reset_all
    reset_all()
