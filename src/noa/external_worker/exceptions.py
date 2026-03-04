"""Exceptions for the external worker domain."""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when an upstream LLM provider returns an error."""


class ProviderTimeoutError(ProviderError):
    """Raised when an upstream LLM provider request times out."""


class PrivacyViolationError(ValueError):
    """Raised when a request violates privacy constraints."""


class ToolNotFoundError(KeyError):
    """Raised when a tool is not found in the registry."""
