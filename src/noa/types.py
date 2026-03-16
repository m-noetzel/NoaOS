"""Shared domain types for Noa — StrEnums for type-safe string constants.

StrEnum values compare equal to their plain-string equivalents, so existing
DB values, JSON payloads, and comparisons remain fully backward-compatible.
"""

from __future__ import annotations

from enum import StrEnum


class PrivacyMode(StrEnum):
    """Privacy domain for a request or thread (SPEC.md §4, §14)."""

    PRIVATE = "private"
    EXTERNAL = "external"


class RiskTier(StrEnum):
    """Risk classification tier for tool actions (SPEC.md §21)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
