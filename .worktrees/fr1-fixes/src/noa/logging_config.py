"""Structured JSON logging configuration — SPEC.md §28.3.

Provides:
- JsonFormatter: formats log records as JSON with required fields
- PII_PATTERNS: compiled regexes to detect sensitive data
- sanitize_log_message: redacts PII/secrets from log strings
- configure_logging: sets up root logger with JsonFormatter
- trace_id_var: context variable for request trace ID propagation
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

# Context variable for trace_id propagation across async boundaries.
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

# Compiled regex patterns for PII / secret detection (§28.3).
PII_PATTERNS: list[re.Pattern[str]] = [
    # Email addresses
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    # password=... or password: "..."
    re.compile(
        r'(?i)password\s*[=:]\s*"?([^\s",]+)"?',
    ),
    # API key prefixes (OpenAI sk-, AWS AKIA, etc.)
    re.compile(r"\bsk-[a-zA-Z0-9]{8,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16,}\b"),
    # Bearer tokens
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-.]+"),
]


def sanitize_log_message(msg: str) -> str:
    """Redact PII and secrets from a log message string."""
    result = msg
    for pattern in PII_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Required fields: timestamp, level, logger, message, trace_id,
    module, function.
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Build the message (including any exception info)
        message = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            message = f"{message}\n{record.exc_text}"

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(message),
            "trace_id": trace_id_var.get(),
            "module": record.module,
            "function": record.funcName,
        }
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Set up root logger with JsonFormatter on a StreamHandler.

    Safe to call multiple times; removes prior JsonFormatter handlers
    before adding a new one.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing JsonFormatter handlers to avoid duplicates
    root.handlers = [
        h
        for h in root.handlers
        if not isinstance(h.formatter, JsonFormatter)
    ]

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
