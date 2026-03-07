"""Shared LLM exceptions — domain-neutral location.

Moved here so that provider clients in any domain can raise these
without cross-domain imports (C2).
"""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when an upstream LLM provider returns an error."""


class ProviderTimeoutError(ProviderError):
    """Raised when an upstream LLM provider request times out."""
