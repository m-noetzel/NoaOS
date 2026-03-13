"""Exceptions for the external worker domain."""

from __future__ import annotations

# Re-export shared LLM exceptions for backward compatibility
from noa.llm.exceptions import ProviderError, ProviderTimeoutError

__all__ = [
    "PrivacyViolationError",
    "ProviderError",
    "ProviderTimeoutError",
    "ToolNotFoundError",
]


class PrivacyViolationError(ValueError):
    """Raised when a request violates privacy constraints."""


class ToolNotFoundError(KeyError):
    """Raised when a tool is not found in the registry."""
