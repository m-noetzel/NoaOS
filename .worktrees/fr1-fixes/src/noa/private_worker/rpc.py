"""RPC contract validation and violation tracking per SPEC.md §9.1-§9.4."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from noa.constants import MAX_N_RESULTS

logger = logging.getLogger(__name__)

VALID_TASK_TYPES = frozenset({
    "remember", "recall", "rag_query",
    "rag_ingest", "summarize", "search",
})

VALID_SENSITIVITY_LABELS = frozenset({"none", "low", "medium", "high"})

# Limits per §9.1 / §9.2
MAX_QUERY_LEN = 4096
MAX_FACT_LEN = 2048
MAX_MAX_TOKENS = 4096
MAX_PAYLOAD_BYTES = 16 * 1024  # 16 KB
MAX_ANSWER_LEN = 8192
MAX_FACTS_COUNT = 20
MAX_ERROR_MSG_LEN = 512
MAX_RESPONSE_BYTES = 64 * 1024  # 64 KB

# Expected response schema fields
EXPECTED_TOP_LEVEL = frozenset({
    "request_id", "status", "result", "sensitivity_label", "error",
})
EXPECTED_RESULT = frozenset({
    "answer", "facts", "doc_ids", "metadata",
})


@dataclass
class ValidationResult:
    """Result of validating an RPC request or response."""

    is_valid: bool
    error: str = ""


def _contains_non_text_char(text: str) -> bool:
    """Check if a string contains non-text (control) characters."""
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in ("\n", "\r", "\t"):
            return True
    return False


def _scan_for_binary(obj: Any) -> bool:
    """Recursively scan a dict/list/str structure for non-text content."""
    if isinstance(obj, str):
        return _contains_non_text_char(obj)
    if isinstance(obj, dict):
        return any(_scan_for_binary(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_scan_for_binary(v) for v in obj)
    return False


def validate_request(req: dict[str, Any]) -> ValidationResult:
    """Validate an RPC request dict against §9.1 limits.

    Returns a ValidationResult indicating whether the request is valid.
    """
    # idempotency_key required
    if "idempotency_key" not in req:
        return ValidationResult(is_valid=False, error="idempotency_key is required")

    # task_type validation
    task_type = req.get("task_type", "")
    if task_type not in VALID_TASK_TYPES:
        return ValidationResult(
            is_valid=False,
            error=(
                f"Invalid task_type: '{task_type}'. "
                f"Must be one of {sorted(VALID_TASK_TYPES)}"
            ),
        )

    payload = req.get("payload", {})

    # Query length
    query = payload.get("query", "")
    if len(query) > MAX_QUERY_LEN:
        return ValidationResult(
            is_valid=False,
            error=f"query exceeds maximum length of {MAX_QUERY_LEN} characters",
        )

    # Fact length
    fact = payload.get("fact")
    if fact is not None and len(fact) > MAX_FACT_LEN:
        return ValidationResult(
            is_valid=False,
            error=f"fact exceeds maximum length of {MAX_FACT_LEN} characters",
        )

    # n_results limit
    n_results = payload.get("n_results", 5)
    if n_results > MAX_N_RESULTS:
        return ValidationResult(
            is_valid=False,
            error=f"n_results exceeds maximum of {MAX_N_RESULTS}",
        )

    # max_tokens limit
    options = payload.get("options", {})
    max_tokens = options.get("max_tokens", 1024)
    if max_tokens > MAX_MAX_TOKENS:
        return ValidationResult(
            is_valid=False,
            error=f"max_tokens exceeds maximum of {MAX_MAX_TOKENS}",
        )

    # Total payload size check (16 KB)
    payload_json = json.dumps(req).encode("utf-8")
    if len(payload_json) > MAX_PAYLOAD_BYTES:
        return ValidationResult(
            is_valid=False,
            error=f"Total payload size exceeds {MAX_PAYLOAD_BYTES} bytes",
        )

    # No binary / non-text data (scan raw values, not JSON-escaped)
    if _scan_for_binary(req):
        return ValidationResult(
            is_valid=False,
            error="Payload contains non-text (binary) data",
        )

    return ValidationResult(is_valid=True)


def validate_response(resp: dict[str, Any]) -> ValidationResult:
    """Validate an RPC response dict against §9.2 limits.

    Returns a ValidationResult indicating whether the response is valid.
    """
    # sensitivity_label required
    if "sensitivity_label" not in resp:
        return ValidationResult(
            is_valid=False,
            error="sensitivity_label is required in every response",
        )

    label = resp.get("sensitivity_label", "")
    if label not in VALID_SENSITIVITY_LABELS:
        return ValidationResult(
            is_valid=False,
            error=(
                f"Invalid sensitivity_label: '{label}'. "
                f"Must be one of {sorted(VALID_SENSITIVITY_LABELS)}"
            ),
        )

    result = resp.get("result", {})

    # Answer length
    answer = result.get("answer", "")
    if len(answer) > MAX_ANSWER_LEN:
        return ValidationResult(
            is_valid=False,
            error=f"answer exceeds maximum length of {MAX_ANSWER_LEN} characters",
        )

    # Facts count
    facts = result.get("facts", [])
    if len(facts) > MAX_FACTS_COUNT:
        return ValidationResult(
            is_valid=False,
            error=f"facts array exceeds maximum of {MAX_FACTS_COUNT} items",
        )

    # Error message length
    error = resp.get("error")
    if error is not None:
        msg = error.get("message", "")
        if len(msg) > MAX_ERROR_MSG_LEN:
            return ValidationResult(
                is_valid=False,
                error=(
                    f"error message exceeds maximum of "
                    f"{MAX_ERROR_MSG_LEN} characters"
                ),
            )

    # Total response size (64 KB)
    resp_json = json.dumps(resp).encode("utf-8")
    if len(resp_json) > MAX_RESPONSE_BYTES:
        return ValidationResult(
            is_valid=False,
            error=f"Total response size exceeds {MAX_RESPONSE_BYTES} bytes",
        )

    return ValidationResult(is_valid=True)


@dataclass
class ContractViolationTracker:
    """Tracks contract violations and triggers alerts per §9.4.

    After 3 violations within 24 hours, alerts are triggered and the
    worker should be paused.
    """

    _violations: list[dict[str, Any]] = field(default_factory=list)
    _alert_threshold: int = 3
    _window_seconds: float = 24 * 60 * 60  # 24 hours

    def record_violation(
        self,
        violation_type: str,
        details: str,
    ) -> None:
        """Record a contract violation."""
        self._violations.append({
            "type": violation_type,
            "details": details,
            "timestamp": time.monotonic(),
        })
        logger.warning(
            "contract_violation_recorded: type=%s details=%s total=%d",
            violation_type,
            details,
            self.violation_count,
        )

    @property
    def violation_count(self) -> int:
        """Number of violations in the current 24-hour window."""
        cutoff = time.monotonic() - self._window_seconds
        return sum(
            1 for v in self._violations if v["timestamp"] >= cutoff
        )

    @property
    def should_alert(self) -> bool:
        """Whether the violation count has reached the alert threshold."""
        return self.violation_count >= self._alert_threshold

    @property
    def should_pause_worker(self) -> bool:
        """Whether the worker should be paused (same as alert threshold)."""
        return self.should_alert


def strip_unexpected_fields(resp: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Remove fields not in the RPC response schema per §9.4.

    Returns a tuple of (cleaned response dict, list of stripped field names).
    """
    stripped: list[str] = []
    cleaned: dict[str, Any] = {}

    for key, value in resp.items():
        if key in EXPECTED_TOP_LEVEL:
            cleaned[key] = value
        else:
            stripped.append(key)
            logger.warning("unexpected_field_stripped: %s", key)

    # Also clean the result sub-dict
    if "result" in cleaned and isinstance(cleaned["result"], dict):
        clean_result: dict[str, Any] = {}
        for key, value in cleaned["result"].items():
            if key in EXPECTED_RESULT:
                clean_result[key] = value
            else:
                stripped.append(key)
                logger.warning("unexpected_result_field_stripped: %s", key)
        cleaned["result"] = clean_result

    return cleaned, stripped
