"""Validation pipeline per SPEC.md §16.1.

Pipeline stages run in order:
    schema → size → content_filter → [coding_check | tool_check] → policy
Early failure short-circuits — subsequent stages are not executed.

Integration contract:
    ValidationPipeline.validate(output, context) → ValidationResult
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from noa.validation.coding import check_coding_output
from noa.validation.content_filter import scan_output_recursive
from noa.validation.tool_output import check_tool_output

# Default max output size: 1MB
_DEFAULT_MAX_SIZE_BYTES = 1 * 1024 * 1024


@dataclass
class ValidationContext:
    """Context for validation — determines which stages run.

    Attributes:
        output_type: One of 'generic', 'coding', 'tool'.
        workspace_root: For coding outputs, the scoped workspace path.
        allowed_dependencies: For coding outputs, authorized dep names.
        tool_name: For tool outputs, the tool name.
        tool_schema: For tool outputs, the expected return schema.
        max_size_bytes: Maximum output size in bytes.
    """

    output_type: str = "generic"
    workspace_root: str | None = None
    allowed_dependencies: frozenset[str] | None = None
    tool_name: str | None = None
    tool_schema: dict[str, Any] | None = None
    max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES


@dataclass
class ValidationFailure:
    """A single validation failure.

    Attributes:
        stage: The pipeline stage that produced this failure.
        message: Human-readable description.
    """

    stage: str
    message: str


@dataclass
class ValidationResult:
    """Result of the full validation pipeline.

    Attributes:
        passed: True if all stages passed.
        failures: List of failures from all stages.
        filtered_output: The output dict if passed, empty dict if failed.
        stages_executed: Ordered list of stages that were executed.
        email_send_logged: Whether an email send was logged (§16.3).
    """

    passed: bool
    failures: list[ValidationFailure] = field(default_factory=list)
    filtered_output: dict[str, Any] = field(default_factory=dict)
    stages_executed: list[str] = field(default_factory=list)
    email_send_logged: bool = False


class ValidationPipeline:
    """Output validation pipeline per §16.1.

    Stages:
        1. schema — validates basic response structure
        2. size — checks response size limits
        3. content_filter — scans for prompt injection / exfiltration
        4. coding_check — (coding outputs only) validates diffs
        5. tool_check — (tool outputs only) validates tool-specific rules
        6. policy — placeholder for future policy stage
    """

    def validate(
        self,
        output: dict[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        """Run the validation pipeline on a worker output.

        Args:
            output: The worker response dict.
            context: Validation context determining which stages run.

        Returns:
            ValidationResult with pass/fail, failures, and metadata.
        """
        result = ValidationResult(passed=True)

        # Stage 1: Schema validation
        result.stages_executed.append("schema")
        schema_failures = self._check_schema(output)
        if schema_failures:
            result.passed = False
            result.failures.extend(schema_failures)
            return result

        # Stage 2: Size check
        result.stages_executed.append("size")
        size_failures = self._check_size(output, context.max_size_bytes)
        if size_failures:
            result.passed = False
            result.failures.extend(size_failures)
            return result

        # Stage 3: Content filter
        result.stages_executed.append("content_filter")
        content_failures = self._check_content(output)
        if content_failures:
            result.passed = False
            result.failures.extend(content_failures)
            return result

        # Stage 4a: Coding checks (if coding output)
        if context.output_type == "coding":
            result.stages_executed.append("coding_check")
            coding_failures = self._check_coding(output, context)
            if coding_failures:
                result.passed = False
                result.failures.extend(coding_failures)
                return result

        # Stage 4b: Tool checks (if tool output)
        if context.output_type == "tool":
            result.stages_executed.append("tool_check")
            tool_failures, email_logged = self._check_tool(output, context)
            result.email_send_logged = email_logged
            if tool_failures:
                result.passed = False
                result.failures.extend(tool_failures)
                return result

        # Stage 5: Policy check (placeholder)
        result.stages_executed.append("policy")

        # All passed
        result.filtered_output = output
        return result

    def _check_schema(
        self, output: Any,
    ) -> list[ValidationFailure]:
        """Validate basic response schema (must be dict with 'status')."""
        failures: list[ValidationFailure] = []

        if not isinstance(output, dict):
            failures.append(ValidationFailure(
                stage="schema",
                message=f"Output must be a dict, got {type(output).__name__}",
            ))
            return failures

        if "status" not in output:
            failures.append(ValidationFailure(
                stage="schema",
                message="Output missing required 'status' field",
            ))

        return failures

    def _check_size(
        self,
        output: dict[str, Any],
        max_bytes: int,
    ) -> list[ValidationFailure]:
        """Check response size against limit."""
        failures: list[ValidationFailure] = []

        try:
            size = len(json.dumps(output))
        except (TypeError, ValueError):
            size = 0

        if size > max_bytes:
            failures.append(ValidationFailure(
                stage="size",
                message=f"Output size {size} bytes exceeds limit of {max_bytes} bytes",
            ))

        return failures

    def _check_content(
        self,
        output: dict[str, Any],
    ) -> list[ValidationFailure]:
        """Run content filter on all string values."""
        failures: list[ValidationFailure] = []

        filter_result = scan_output_recursive(output)
        if not filter_result.passed:
            for issue in filter_result.issues:
                failures.append(ValidationFailure(
                    stage="content_filter",
                    message=issue,
                ))

        return failures

    def _check_coding(
        self,
        output: dict[str, Any],
        context: ValidationContext,
    ) -> list[ValidationFailure]:
        """Run coding output checks."""
        failures: list[ValidationFailure] = []

        data = output.get("data", {})
        if not isinstance(data, dict):
            return failures

        coding_result = check_coding_output(
            data,
            workspace_root=context.workspace_root or "/",
            allowed_dependencies=context.allowed_dependencies,
        )
        if not coding_result.passed:
            for issue in coding_result.issues:
                failures.append(ValidationFailure(
                    stage="coding_check",
                    message=issue,
                ))

        return failures

    def _check_tool(
        self,
        output: dict[str, Any],
        context: ValidationContext,
    ) -> tuple[list[ValidationFailure], bool]:
        """Run tool output checks. Returns (failures, email_send_logged)."""
        failures: list[ValidationFailure] = []

        data = output.get("data", {})
        if not isinstance(data, dict):
            failures.append(ValidationFailure(
                stage="tool_check",
                message="Tool output 'data' must be a dict",
            ))
            return failures, False

        tool_result = check_tool_output(
            data,
            tool_name=context.tool_name or "unknown",
            tool_schema=context.tool_schema,
        )
        if not tool_result.passed:
            for issue in tool_result.issues:
                failures.append(ValidationFailure(
                    stage="tool_check",
                    message=issue,
                ))

        return failures, tool_result.email_send_logged
