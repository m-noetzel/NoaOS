"""Tests for Private Worker with Ollama & RPC Contract — Phase DW1.

Spec refs: SPEC.md §8.1, §9.1, §9.2, §9.3, §9.4, §13.1, §13.2
Phase plan: MASTER_PLAN.md Phase DW1

Tests cover: RPC request/response validation with hard limits, DLP/redaction
pipeline (PII patterns), sensitivity labeling, contract violation detection,
Ollama integration basics, and task handler dispatch.

All external calls (Ollama, DB) are mocked. No network access.
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.dw1


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_rpc_request(
    *,
    task_type: str = "recall",
    query: str = "What did I say yesterday?",
    fact: str | None = None,
    n_results: int = 5,
    max_tokens: int = 1024,
    model: str = "llama3:8b",
    temperature: float = 0.7,
    timeout_ms: int = 30000,
    idempotency_key: str | None = None,
    document_id: str | None = None,
) -> dict:
    """Build a minimal RPC request dict per §9.1."""
    payload: dict = {
        "query": query,
        "n_results": n_results,
        "options": {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    }
    if fact is not None:
        payload["fact"] = fact
    if document_id is not None:
        payload["document_id"] = document_id
    return {
        "request_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "task_type": task_type,
        "payload": payload,
        "timeout_ms": timeout_ms,
    }


def _make_rpc_response(
    *,
    request_id: str | None = None,
    status: str = "success",
    answer: str = "Here is the answer.",
    facts: list | None = None,
    sensitivity_label: str = "none",
    error: dict | None = None,
) -> dict:
    """Build a minimal RPC response dict per §9.2."""
    resp: dict = {
        "request_id": request_id or str(uuid.uuid4()),
        "status": status,
        "result": {
            "answer": answer,
            "facts": facts or [],
            "doc_ids": [],
            "metadata": {
                "model_used": "llama3:8b",
                "tokens_in": 100,
                "tokens_out": 50,
                "processing_ms": 320,
            },
        },
        "sensitivity_label": sensitivity_label,
    }
    if error is not None:
        resp["error"] = error
    return resp


# ===========================================================================
# 1. RPC Request Validation (§9.1)
# ===========================================================================

class TestRPCRequestValidation:
    """RPC requests are validated against the schema in §9.1."""

    def test_valid_task_types_accepted(self):
        """All 6 task types from §9.1 are accepted."""
        from noa.private_worker.rpc import validate_request

        valid_types = [
            "remember", "recall", "rag_query",
            "rag_ingest", "summarize", "search",
        ]
        for task_type in valid_types:
            req = _make_rpc_request(task_type=task_type)
            result = validate_request(req)
            assert result.is_valid, f"Task type '{task_type}' should be valid"

    def test_invalid_task_type_rejected(self):
        """Unknown task types are rejected."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(task_type="execute_shell")
        result = validate_request(req)
        assert not result.is_valid
        assert "task_type" in result.error.lower()

    def test_query_max_4096_chars(self):
        """Query exceeding 4096 characters is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(query="x" * 4097)
        result = validate_request(req)
        assert not result.is_valid
        assert "query" in result.error.lower()

    def test_query_at_limit_accepted(self):
        """Query at exactly 4096 characters is accepted."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(query="x" * 4096)
        result = validate_request(req)
        assert result.is_valid

    def test_fact_max_2048_chars(self):
        """Fact exceeding 2048 characters is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(
            task_type="remember", fact="f" * 2049,
        )
        result = validate_request(req)
        assert not result.is_valid
        assert "fact" in result.error.lower()

    def test_n_results_max_20(self):
        """n_results exceeding 20 is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(n_results=21)
        result = validate_request(req)
        assert not result.is_valid
        assert "n_results" in result.error.lower()

    def test_max_tokens_max_4096(self):
        """max_tokens exceeding 4096 is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request(max_tokens=4097)
        result = validate_request(req)
        assert not result.is_valid
        assert "max_tokens" in result.error.lower()

    def test_payload_total_max_16kb(self):
        """Payload total exceeding 16 KB is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        # Build a payload that exceeds 16 KB (16384 bytes) via query
        # Max query is 4096 chars, so we use the max query plus padding
        # in other fields to push over the 16 KB total
        req = _make_rpc_request(query="x" * 4096)
        # Manually inflate payload to exceed limit
        req["payload"]["extra_padding"] = "y" * 16000
        result = validate_request(req)
        assert not result.is_valid
        assert "payload" in result.error.lower() or "size" in result.error.lower()

    def test_idempotency_key_required(self):
        """Requests must have an idempotency_key field per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request()
        del req["idempotency_key"]
        result = validate_request(req)
        assert not result.is_valid
        assert "idempotency_key" in result.error.lower()

    def test_timeout_ms_defaults_to_30000(self):
        """timeout_ms defaults to 30000 if not provided per §9.1."""
        from noa.private_worker.schemas import RPCRequest

        req_data = _make_rpc_request()
        del req_data["timeout_ms"]
        parsed = RPCRequest.from_dict(req_data)
        assert parsed.timeout_ms == 30000

    def test_no_binary_data_allowed(self):
        """Binary data in request payload is rejected per §9.1."""
        from noa.private_worker.rpc import validate_request

        req = _make_rpc_request()
        req["payload"]["binary_blob"] = b"\x00\x01\x02".decode("latin-1")
        # The validator should detect non-text content
        result = validate_request(req)
        # Binary / non-UTF8 payloads are rejected
        assert not result.is_valid


# ===========================================================================
# 2. RPC Response Validation (§9.2)
# ===========================================================================

class TestRPCResponseValidation:
    """RPC responses are validated against the schema in §9.2."""

    def test_answer_max_8192_chars_rejected(self):
        """Answer exceeding 8192 characters is rejected (not truncated)
        per §9.2."""
        from noa.private_worker.rpc import validate_response

        resp = _make_rpc_response(answer="a" * 8193)
        result = validate_response(resp)
        assert not result.is_valid
        assert "answer" in result.error.lower()

    def test_facts_array_max_20_items(self):
        """Facts array exceeding 20 items is rejected per §9.2."""
        from noa.private_worker.rpc import validate_response

        facts = [
            {
                "id": str(uuid.uuid4()),
                "fact": f"fact {i}",
                "category": "test",
                "confidence": 0.9,
            }
            for i in range(21)
        ]
        resp = _make_rpc_response(facts=facts)
        result = validate_response(resp)
        assert not result.is_valid
        assert "facts" in result.error.lower()

    def test_error_message_max_512_chars(self):
        """Error message exceeding 512 characters is rejected per §9.2."""
        from noa.private_worker.rpc import validate_response

        resp = _make_rpc_response(
            status="error",
            error={"code": "INTERNAL", "message": "e" * 513},
        )
        result = validate_response(resp)
        assert not result.is_valid
        assert "message" in result.error.lower() or "error" in result.error.lower()

    def test_response_total_max_64kb(self):
        """Response total exceeding 64 KB is rejected per §9.2."""
        from noa.private_worker.rpc import validate_response

        # 8192-char answer is about 8 KB, so we need extra bulk
        resp = _make_rpc_response(answer="a" * 8192)
        # Inflate with many facts to push over 64 KB
        resp["result"]["facts"] = [
            {
                "id": str(uuid.uuid4()),
                "fact": "f" * 2048,
                "category": "test",
                "confidence": 0.9,
            }
            for _ in range(20)
        ]
        # Check if it exceeds 64 KB
        serialized = json.dumps(resp).encode("utf-8")
        if len(serialized) <= 65536:
            # Force it over the limit
            resp["result"]["extra_padding"] = "z" * 65536
        result = validate_response(resp)
        assert not result.is_valid

    def test_sensitivity_label_required(self):
        """Every response must include a sensitivity_label per §9.3."""
        from noa.private_worker.rpc import validate_response

        resp = _make_rpc_response()
        del resp["sensitivity_label"]
        result = validate_response(resp)
        assert not result.is_valid
        assert "sensitivity_label" in result.error.lower()

    def test_sensitivity_label_valid_values(self):
        """Sensitivity label must be one of: none, low, medium, high."""
        from noa.private_worker.rpc import validate_response

        for label in ("none", "low", "medium", "high"):
            resp = _make_rpc_response(sensitivity_label=label)
            result = validate_response(resp)
            assert result.is_valid, f"Label '{label}' should be valid"

    def test_sensitivity_label_invalid_rejected(self):
        """Invalid sensitivity label values are rejected."""
        from noa.private_worker.rpc import validate_response

        resp = _make_rpc_response(sensitivity_label="critical")
        result = validate_response(resp)
        assert not result.is_valid


# ===========================================================================
# 3. DLP / Redaction (§9.3)
# ===========================================================================

class TestDLPRedaction:
    """PII patterns are redacted before responses leave the private domain
    per §9.3."""

    def test_email_redacted(self):
        """Email addresses are redacted with [REDACTED]."""
        from noa.private_worker.dlp import redact_pii

        text = "Contact john.doe@example.com for details."
        result = redact_pii(text)
        assert "[REDACTED]" in result.text
        assert "john.doe@example.com" not in result.text

    def test_phone_redacted(self):
        """Phone numbers are redacted with [REDACTED]."""
        from noa.private_worker.dlp import redact_pii

        text = "Call me at 555-123-4567 tomorrow."
        result = redact_pii(text)
        assert "[REDACTED]" in result.text
        assert "555-123-4567" not in result.text

    def test_ssn_redacted(self):
        """SSN patterns are redacted with [REDACTED]."""
        from noa.private_worker.dlp import redact_pii

        text = "My SSN is 123-45-6789."
        result = redact_pii(text)
        assert "[REDACTED]" in result.text
        assert "123-45-6789" not in result.text

    def test_credit_card_redacted(self):
        """Credit card numbers are redacted with [REDACTED]."""
        from noa.private_worker.dlp import redact_pii

        text = "Card number is 4111-1111-1111-1111."
        result = redact_pii(text)
        assert "[REDACTED]" in result.text
        assert "4111-1111-1111-1111" not in result.text

    def test_warning_flag_on_redaction(self):
        """A warning flag is set when redaction occurs per §9.3."""
        from noa.private_worker.dlp import redact_pii

        text = "Email: user@test.com"
        result = redact_pii(text)
        assert result.redaction_occurred is True

    def test_no_warning_when_clean(self):
        """No warning flag when text has no PII."""
        from noa.private_worker.dlp import redact_pii

        text = "The weather is sunny today."
        result = redact_pii(text)
        assert result.redaction_occurred is False

    def test_no_passthrough_query_echo(self):
        """The private worker never echoes back the original query per §9.3."""
        from noa.private_worker.dlp import check_no_passthrough

        original_query = "What is my social security number?"
        response_text = "What is my social security number? Your SSN is [REDACTED]."
        # Should detect the echo and flag it
        result = check_no_passthrough(original_query, response_text)
        assert result.has_passthrough is True


# ===========================================================================
# 4. Contract Violations (§9.4)
# ===========================================================================

class TestContractViolations:
    """Contract violation detection and alerting per §9.4."""

    def test_oversized_response_logged(self):
        """Oversized responses are rejected and logged as violations."""
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()
        tracker.record_violation(
            violation_type="oversized_response",
            details="Answer exceeded 8192 chars",
        )
        assert tracker.violation_count == 1

    def test_unexpected_fields_stripped_and_logged(self):
        """Unexpected fields are stripped to schema and logged per §9.4."""
        from noa.private_worker.rpc import strip_unexpected_fields

        resp = _make_rpc_response()
        resp["rogue_field"] = "should not be here"
        resp["result"]["secret"] = "also not in schema"  # noqa: S105

        cleaned, stripped = strip_unexpected_fields(resp)
        assert "rogue_field" not in cleaned
        assert "secret" not in cleaned.get("result", {})
        assert len(stripped) >= 2  # at least two fields were stripped

    def test_three_violations_triggers_alert(self):
        """3 violations in 24h triggers alert + pauses worker per §9.4."""
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()
        tracker.record_violation("oversized", "test 1")
        tracker.record_violation("unexpected_field", "test 2")
        tracker.record_violation("oversized", "test 3")

        assert tracker.violation_count == 3
        assert tracker.should_alert is True
        assert tracker.should_pause_worker is True

    def test_two_violations_no_alert(self):
        """Fewer than 3 violations does not trigger alert."""
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()
        tracker.record_violation("oversized", "test 1")
        tracker.record_violation("unexpected_field", "test 2")

        assert tracker.violation_count == 2
        assert tracker.should_alert is False


# ===========================================================================
# 5. Ollama Integration (§8.1)
# ===========================================================================

class TestOllamaIntegration:
    """Ollama client formats inference calls correctly per §8.1."""

    def test_inference_call_formatted(self):
        """Inference calls include model, messages, and options."""
        from noa.private_worker.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://ollama:11434")
        request_body = client.build_request(
            model="llama3:8b",
            messages=[{"role": "user", "content": "Summarize this text."}],
            max_tokens=1024,
            temperature=0.7,
        )
        assert request_body["model"] == "llama3:8b"
        assert "messages" in request_body
        assert request_body["options"]["num_predict"] == 1024

    def test_model_validated_against_manifest(self):
        """Model name must match an entry in the approved manifest per §8.1."""
        from noa.private_worker.ollama_client import OllamaClient

        manifest = {"llama3:8b": "sha256:abc123", "mistral:7b": "sha256:def456"}
        client = OllamaClient(
            base_url="http://ollama:11434",
            model_manifest=manifest,
        )
        assert client.is_model_approved("llama3:8b") is True
        assert client.is_model_approved("gpt-4") is False


# ===========================================================================
# 6. Task Handlers (§9.1 task types)
# ===========================================================================

class TestTaskHandlers:
    """All 6 task types from §9.1 are handled by dispatch."""

    def test_remember_handler_exists(self):
        """Remember task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("remember")
        assert handler is not None
        assert callable(handler)

    def test_recall_handler_exists(self):
        """Recall task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("recall")
        assert handler is not None
        assert callable(handler)

    def test_rag_query_handler_exists(self):
        """rag_query task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("rag_query")
        assert handler is not None
        assert callable(handler)

    def test_rag_ingest_handler_exists(self):
        """rag_ingest task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("rag_ingest")
        assert handler is not None
        assert callable(handler)

    def test_summarize_handler_exists(self):
        """Summarize task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("summarize")
        assert handler is not None
        assert callable(handler)

    def test_search_handler_exists(self):
        """Search task type has a handler."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("search")
        assert handler is not None
        assert callable(handler)

    def test_unknown_handler_returns_none(self):
        """Unknown task types return None from dispatcher."""
        from noa.private_worker.handlers import get_handler

        handler = get_handler("execute_shell")
        assert handler is None
