"""Tests for structured JSON logging — SPEC.md §28.3.

Verifies:
- JSON formatter produces valid JSON with required fields
- No PII/secrets patterns leak into formatted output
- Trace ID propagates through log context
"""

from __future__ import annotations

import json
import logging
import re
import uuid

import pytest

from noa.logging_config import (
    PII_PATTERNS,
    JsonFormatter,
    configure_logging,
    sanitize_log_message,
    trace_id_var,
)


class TestJsonFormatter:
    """JsonFormatter must emit valid JSON with all required fields."""

    def _make_record(self, msg: str = "hello") -> logging.LogRecord:
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
            func="test_func",
        )

    def test_output_is_valid_json(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        output = fmt.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))

        required = {"timestamp", "level", "logger", "message", "trace_id"}
        assert required.issubset(parsed.keys()), (
            f"Missing fields: {required - parsed.keys()}"
        )

    def test_timestamp_is_iso8601(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        # ISO 8601 basic pattern check
        assert re.match(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", parsed["timestamp"]
        )

    def test_level_matches_record(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert parsed["level"] == "INFO"

    def test_logger_name(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert parsed["logger"] == "test.logger"

    def test_message_content(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record("my message")
        parsed = json.loads(fmt.format(record))
        assert parsed["message"] == "my message"

    def test_module_and_function_present(self) -> None:
        fmt = JsonFormatter()
        record = self._make_record()
        parsed = json.loads(fmt.format(record))
        assert "module" in parsed
        assert "function" in parsed

    def test_trace_id_from_context_var(self) -> None:
        tid = str(uuid.uuid4())
        token = trace_id_var.set(tid)
        try:
            fmt = JsonFormatter()
            record = self._make_record()
            parsed = json.loads(fmt.format(record))
            assert parsed["trace_id"] == tid
        finally:
            trace_id_var.reset(token)

    def test_trace_id_default_when_unset(self) -> None:
        # Reset to default (None / empty)
        token = trace_id_var.set(None)  # type: ignore[arg-type]
        try:
            fmt = JsonFormatter()
            record = self._make_record()
            parsed = json.loads(fmt.format(record))
            # Should still have trace_id key, value can be None or empty
            assert "trace_id" in parsed
        finally:
            trace_id_var.reset(token)


class TestPIISanitization:
    """Verify PII/secrets are redacted from log messages (§28.3)."""

    def test_email_redacted(self) -> None:
        msg = "User logged in: alice@example.com"
        result = sanitize_log_message(msg)
        assert "alice@example.com" not in result
        assert "***" in result or "REDACTED" in result.upper()

    def test_password_field_redacted(self) -> None:
        msg = 'password=secret123 and password: "hunter2"'
        result = sanitize_log_message(msg)
        assert "secret123" not in result
        assert "hunter2" not in result

    def test_api_key_redacted(self) -> None:
        msg = "Using key sk-abc123xyz and AKIA1234567890ABCDEF"
        result = sanitize_log_message(msg)
        assert "sk-abc123xyz" not in result
        assert "AKIA1234567890ABCDEF" not in result

    def test_clean_message_unchanged(self) -> None:
        msg = "Processing request for item 42"
        result = sanitize_log_message(msg)
        assert result == msg

    def test_pii_patterns_is_nonempty_list(self) -> None:
        assert isinstance(PII_PATTERNS, list)
        assert len(PII_PATTERNS) > 0
        # Each pattern should be a compiled regex or a string
        for pat in PII_PATTERNS:
            assert hasattr(pat, "pattern") or isinstance(pat, str)


class TestConfigureLogging:
    """configure_logging sets up root logger correctly."""

    def test_configure_sets_level(self) -> None:
        configure_logging(level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING
        # Reset to avoid side effects
        configure_logging(level="INFO")

    def test_configure_adds_json_handler(self) -> None:
        configure_logging(level="INFO")
        root = logging.getLogger()
        json_handlers = [
            h for h in root.handlers if isinstance(h.formatter, JsonFormatter)
        ]
        assert len(json_handlers) >= 1
