"""DLP (Data Loss Prevention) and PII redaction per SPEC.md §9.3."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# PII patterns for redaction
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")),
    ("phone", re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]

REDACTED = "[REDACTED]"


@dataclass
class RedactionResult:
    """Result of PII redaction on text."""

    text: str
    redaction_occurred: bool


@dataclass
class PassthroughResult:
    """Result of checking for query passthrough."""

    has_passthrough: bool


def redact_pii(text: str) -> RedactionResult:
    """Scan text for PII patterns and replace with [REDACTED].

    Returns a RedactionResult with the redacted text and whether
    any redaction occurred.
    """
    redacted = False
    result = text

    for pattern_name, pattern in _PII_PATTERNS:
        if pattern.search(result):
            result = pattern.sub(REDACTED, result)
            redacted = True
            logger.info("pii_redacted: %s", pattern_name)

    return RedactionResult(text=result, redaction_occurred=redacted)


def check_no_passthrough(
    original_query: str,
    response_text: str,
) -> PassthroughResult:
    """Ensure the response does not echo back the original query per §9.3.

    Returns a PassthroughResult indicating whether the query was echoed.
    """
    if original_query and original_query in response_text:
        logger.warning(
            "query_passthrough_detected: query_length=%d",
            len(original_query),
        )
        return PassthroughResult(has_passthrough=True)

    return PassthroughResult(has_passthrough=False)
