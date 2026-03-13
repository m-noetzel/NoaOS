"""Content filtering for prompt injection and exfiltration detection.

Spec refs: SPEC.md §16.4

Detects:
- Prompt injection markers ("ignore previous instructions", etc.)
- System prompt leak attempts
- Exfiltration URLs (known patterns, data: URIs)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Prompt injection patterns — case-insensitive
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+(instructions|context)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+your\s+system\s+prompt", re.IGNORECASE),
]

# System prompt leak patterns
_SYSTEM_PROMPT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"your\s+system\s+prompt\s+is", re.IGNORECASE),
    re.compile(r"system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"<<\s*SYS\s*>>", re.IGNORECASE),
    re.compile(r"\[INST\].*\[/INST\]", re.IGNORECASE | re.DOTALL),
]

# Exfiltration URL patterns
_EXFIL_URL_PATTERNS: list[re.Pattern[str]] = [
    # data: URIs (can embed arbitrary content)
    re.compile(r"data:[a-zA-Z]+/[a-zA-Z0-9.+-]+;base64,", re.IGNORECASE),
    # URLs with suspicious query params suggesting data exfiltration
    re.compile(
        r"https?://[^\s]+[?&](data|exfil|stolen|leak|dump)=",
        re.IGNORECASE,
    ),
]


@dataclass
class ContentFilterResult:
    """Result of content filtering."""

    passed: bool
    issues: list[str] = field(default_factory=list)


def scan_content(text: str) -> ContentFilterResult:
    """Scan text for prompt injection markers and exfiltration URLs.

    Args:
        text: The text content to scan.

    Returns:
        ContentFilterResult with pass/fail and issue descriptions.
    """
    issues: list[str] = []

    # Check prompt injection patterns
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            issues.append(
                f"Prompt injection detected: '{match.group()}'"
            )

    # Check system prompt leak patterns
    for pattern in _SYSTEM_PROMPT_PATTERNS:
        match = pattern.search(text)
        if match:
            issues.append(
                f"System prompt leak detected: '{match.group()}'"
            )

    # Check exfiltration URL patterns
    for pattern in _EXFIL_URL_PATTERNS:
        match = pattern.search(text)
        if match:
            issues.append(
                f"Exfiltration URL detected: '{match.group()}'"
            )

    return ContentFilterResult(
        passed=len(issues) == 0,
        issues=issues,
    )


def scan_output_recursive(obj: object) -> ContentFilterResult:
    """Recursively scan all string values in a nested structure.

    Args:
        obj: Any JSON-like structure (dict, list, str, etc.).

    Returns:
        Aggregated ContentFilterResult.
    """
    all_issues: list[str] = []

    if isinstance(obj, str):
        result = scan_content(obj)
        all_issues.extend(result.issues)
    elif isinstance(obj, dict):
        for value in obj.values():
            result = scan_output_recursive(value)
            all_issues.extend(result.issues)
    elif isinstance(obj, list):
        for item in obj:
            result = scan_output_recursive(item)
            all_issues.extend(result.issues)

    return ContentFilterResult(
        passed=len(all_issues) == 0,
        issues=all_issues,
    )
