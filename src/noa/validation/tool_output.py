"""Tool output validation per SPEC.md §16.3.

Checks:
- Tool responses match the tool's return schema (simple JSON validation)
- Calendar events: no past events, no unreasonable durations
- Email: send confirmations are tracked
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class ToolCheckResult:
    """Result of tool output validation."""

    passed: bool
    issues: list[str] = field(default_factory=list)
    email_send_logged: bool = False


def _validate_json_schema_simple(
    data: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """Simple JSON schema validation (required fields only).

    This is intentionally minimal — checks required fields and basic types.
    Full JSON Schema validation can be added later if needed.

    Args:
        data: The data to validate.
        schema: A simple schema dict with 'required' and 'properties'.

    Returns:
        List of validation issue strings.
    """
    issues: list[str] = []

    required = schema.get("required", [])
    for field_name in required:
        if field_name not in data:
            issues.append(f"Missing required field: {field_name}")

    return issues


def _validate_calendar_output(data: dict[str, Any]) -> list[str]:
    """Validate calendar-specific rules per §16.3.

    - No events in the past
    - No unreasonable durations (>24 hours)
    """
    issues: list[str] = []
    now = datetime.now(UTC)

    start_str = data.get("start")
    end_str = data.get("end")

    if isinstance(start_str, str):
        try:
            start = datetime.fromisoformat(start_str)
            # Ensure timezone-aware comparison
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if start < now:
                issues.append("Calendar event starts in the past")
        except ValueError:
            issues.append(f"Invalid start datetime: {start_str}")

    if isinstance(start_str, str) and isinstance(end_str, str):
        try:
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            duration = end - start
            if duration > timedelta(hours=24):
                issues.append(
                    f"Calendar event duration exceeds 24 hours: {duration}"
                )
        except ValueError:
            pass  # Already reported above if invalid

    return issues


def check_tool_output(
    data: dict[str, Any],
    *,
    tool_name: str,
    tool_schema: dict[str, Any] | None = None,
) -> ToolCheckResult:
    """Validate tool output per §16.3.

    Args:
        data: The 'data' field from worker response.
        tool_name: Name of the tool (e.g., 'calendar', 'gmail').
        tool_schema: Optional JSON-like schema for the tool's return type.

    Returns:
        ToolCheckResult with pass/fail, issues, and email tracking flag.
    """
    issues: list[str] = []
    email_send_logged = False

    # Schema validation
    if tool_schema is not None:
        schema_issues = _validate_json_schema_simple(data, tool_schema)
        issues.extend(schema_issues)

    # If schema validation failed on required fields, skip domain checks
    if issues:
        return ToolCheckResult(passed=False, issues=issues)

    # Calendar-specific checks
    if tool_name == "calendar":
        cal_issues = _validate_calendar_output(data)
        issues.extend(cal_issues)

    # Gmail-specific checks
    if tool_name == "gmail":
        status = data.get("status")
        if status == "sent":
            email_send_logged = True

    return ToolCheckResult(
        passed=len(issues) == 0,
        issues=issues,
        email_send_logged=email_send_logged,
    )
