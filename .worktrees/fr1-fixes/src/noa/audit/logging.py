"""Structured JSON logging — SPEC.md §28.3.

Provides get_structured_logger() and format_log_record() for consistent,
machine-readable log output with trace_id propagation and secret filtering.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

# Keys whose values must never appear in logs
_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|api_key|token|credential|private_key)", re.IGNORECASE
)


def _strip_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Remove entries whose keys match secret-like patterns."""
    return {
        k: v for k, v in data.items() if not _SECRET_KEY_PATTERN.search(k)
    }


class _JsonFormatter(logging.Formatter):
    """Logging formatter that outputs JSON records."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self._service,
            "message": record.getMessage(),
        }
        trace_id = getattr(record, "trace_id", None)
        if trace_id is not None:
            log_entry["trace_id"] = trace_id
        return json.dumps(log_entry)


def get_structured_logger(service: str) -> logging.Logger:
    """Return a logger configured for structured JSON output.

    Args:
        service: The service name to include in every log record.
    """
    logger = logging.getLogger(f"noa.{service}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter(service))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


def format_log_record(
    *,
    service: str,
    level: str,
    message: str,
    trace_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    """Format a structured log record as a JSON string.

    Secret-like keys in *data* are stripped before serialisation (§28.3).

    Args:
        service: Originating service name.
        level: Log level (info, debug, warning, error).
        message: Human-readable log message.
        trace_id: Optional trace correlation ID.
        data: Optional structured payload (secrets auto-stripped).

    Returns:
        A JSON string with timestamp, level, service, message, and optionally
        trace_id and data fields.
    """
    record: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "service": service,
        "message": message,
    }
    if trace_id is not None:
        record["trace_id"] = trace_id
    if data is not None:
        record["data"] = _strip_secrets(data)
    return json.dumps(record)
