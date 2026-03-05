"""Coding output validation per SPEC.md §16.2.

Checks:
- Diffs only touch files within the scoped workspace
- No new dependencies added without explicit authorization
- No modifications to security-sensitive files unless task requires it
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# Files that are security-sensitive and require explicit task authorization
_SECURITY_SENSITIVE_PATTERNS: frozenset[str] = frozenset({
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".env",
    ".env.production",
    "Makefile",
})


@dataclass
class CodingCheckResult:
    """Result of coding output validation."""

    passed: bool
    issues: list[str] = field(default_factory=list)


def check_coding_output(
    data: dict[str, Any],
    *,
    workspace_root: str,
    allowed_dependencies: frozenset[str] | None = None,
) -> CodingCheckResult:
    """Validate coding output per §16.2.

    Args:
        data: The 'data' field from worker response, expected to contain 'diffs'.
        workspace_root: Absolute path to the scoped workspace root.
        allowed_dependencies: Set of authorized dependency names.

    Returns:
        CodingCheckResult with pass/fail and issue descriptions.
    """
    issues: list[str] = []

    diffs = data.get("diffs", [])
    if not isinstance(diffs, list):
        issues.append("'diffs' field must be a list")
        return CodingCheckResult(passed=False, issues=issues)

    # Normalize workspace root
    ws_root = os.path.normpath(workspace_root)

    for diff in diffs:
        if not isinstance(diff, dict):
            issues.append(f"Diff entry must be a dict, got {type(diff).__name__}")
            continue

        path = diff.get("path", "")
        if not isinstance(path, str):
            issues.append(f"Diff path must be a string, got {type(path).__name__}")
            continue

        # Check diff is within workspace
        norm_path = os.path.normpath(path)
        if not norm_path.startswith(ws_root):
            issues.append(
                f"Diff touches file outside workspace: {path}"
            )

        # Check security-sensitive files
        rel_path = os.path.relpath(norm_path, ws_root)
        basename = os.path.basename(norm_path)
        if basename in _SECURITY_SENSITIVE_PATTERNS or any(
            rel_path.startswith(p) for p in _SECURITY_SENSITIVE_PATTERNS
        ):
            issues.append(
                f"Diff modifies security-sensitive file: {path}"
            )

    # Check unauthorized dependencies
    new_deps = data.get("new_dependencies", [])
    if new_deps and isinstance(new_deps, list):
        allowed = allowed_dependencies or frozenset()
        for dep in new_deps:
            if dep not in allowed:
                issues.append(
                    f"Unauthorized dependency: {dep}"
                )

    return CodingCheckResult(
        passed=len(issues) == 0,
        issues=issues,
    )
