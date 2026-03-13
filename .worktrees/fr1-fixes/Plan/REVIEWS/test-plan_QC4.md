# Test Plan: Phase QC4 — Domain Isolation & Worker Wiring

**Date:** 2026-03-07
**Phase:** QC4
**Reviewer:** qa-review agent
**Phase type:** Pre-implementation (test plan)

---

## Executive Summary

QC4 fixes three tracked findings: C2 (domain isolation violation via cross-domain imports), H1 (worker apps are skeleton-only with no functional endpoints), and H9 (Google AI tool call parser missing `"id"` field). The changes are architectural — they introduce two new shared modules (`noa.llm.providers`, `noa.constants`), wire two new FastAPI endpoints into both worker apps, and fix a data contract bug in the Google AI parser.

This test plan specifies the tests the `/write-tests` agent must write, organized by finding, with spec traceability, negative test requirements, and integration smoke test obligations.

---

## Phase Deliverables Under Test

| Deliverable | Finding | What Must Be Tested |
|---|---|---|
| `noa/llm/providers/__init__.py` — OllamaClient moved here | C2 | Import resolves; no private_worker import required |
| `noa/constants.py` — MAX_N_RESULTS moved here | C2 | Import resolves; correct value |
| `noa/external_worker/llm/router.py` — import from shared module | C2 | M8 import boundary clean after fix |
| `noa/tools/memory.py` — import from constants | C2 | M8 import boundary clean after fix |
| `noa/external_worker/app.py` — POST /v1/complete | H1 | Endpoint reachable, request validated, errors handled |
| `noa/private_worker/app.py` — POST /rpc | H1 | Endpoint reachable, RPC contract enforced, handlers dispatched |
| `noa/external_worker/llm/google_ai.py` — synthetic `id` field | H9 | id present in all tool_calls; downstream code can match |

---

## Test File

Create: `tests/unit/test_qc4_domain_isolation.py`

All test classes must have docstrings citing `FINDINGS.md C2 / H1 / H9` and relevant ARCH_INVARIANTS.md rule (M8 → L3, H1 → L10, H9 → §14.4).

---

## Test Classes and Requirements

### Class 1: `TestSharedModuleImports`

**Covers:** C2, ARCH_INVARIANTS.md L3 (Domain Isolation)

**Rationale:** After the fix, `noa.llm.providers` must exist as a standalone importable module that does not pull in `noa.private_worker`. Tests verify the module boundary is clean at import time.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_ollama_client_importable_from_shared_module` | Positive | `from noa.llm.providers import OllamaClient` succeeds |
| `test_max_n_results_importable_from_constants` | Positive | `from noa.constants import MAX_N_RESULTS` succeeds; `MAX_N_RESULTS == 20` |
| `test_shared_module_has_no_private_worker_import` | Negative / Security | Inspect `noa.llm.providers.__file__` source; confirm `noa.private_worker` does not appear in it |
| `test_constants_module_has_no_private_worker_import` | Negative / Security | Inspect `noa.constants.__file__` source; confirm `noa.private_worker` not imported |
| `test_external_worker_router_no_longer_imports_private_worker` | Negative / Security | Import `noa.external_worker.llm.router`; verify `noa.private_worker` is NOT in `sys.modules` after import (use `sys.modules` snapshot) |
| `test_tools_memory_no_longer_imports_private_worker` | Negative / Security | Import `noa.tools.memory`; verify `noa.private_worker` is NOT in `sys.modules` after import |

**Critical note on the last two tests:** The current violation at `router.py:114` is a lazy import inside `from_settings()` — it only fires when the method is called, not on module import. The test for `test_external_worker_router_no_longer_imports_private_worker` must ALSO call `ProviderRouter.from_settings(mock_settings)` with a mock settings object to trigger the lazy import path and confirm no `noa.private_worker` module is imported. Checking just module-level import is insufficient.

Example approach:
```python
import sys
# Snapshot before
before = set(sys.modules.keys())
from noa.external_worker.llm.router import ProviderRouter
settings = MagicMock(...)
ProviderRouter.from_settings(settings)  # triggers lazy import
after = set(sys.modules.keys())
new_modules = after - before
private_modules = {m for m in new_modules if "private_worker" in m}
assert not private_modules, f"M8 violation: {private_modules}"
```

---

### Class 2: `TestOllamaClientSharedBehavior`

**Covers:** C2, SPEC.md §8.1 (local inference contract), ARCH_INVARIANTS.md L3

**Rationale:** After moving `OllamaClient` to `noa.llm.providers`, its behavior must be identical to the current implementation. These tests act as a regression guard.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_ollama_client_build_request` | Positive | `build_request()` returns dict with `model`, `messages`, `stream: False`, `options.num_predict` |
| `test_ollama_client_unapproved_model_rejected` | Negative | `complete()` with model not in manifest raises `ProviderError` |
| `test_ollama_client_connect_error_raises_provider_error` | Negative | `httpx.ConnectError` wrapped as `ProviderError("Ollama unavailable")` |
| `test_ollama_client_timeout_raises_provider_error` | Negative | `httpx.TimeoutException` wrapped as `ProviderError` containing "Timeout" |
| `test_ollama_client_non_200_raises_provider_error` | Negative | HTTP 500 response → `ProviderError` with status code |
| `test_ollama_client_normalized_response_format` | Positive | Successful response includes `content`, `tool_calls`, `usage.input_tokens`, `usage.output_tokens`, `provider == "ollama"` |

**Note:** `ProviderError` must be imported from `noa.external_worker.exceptions` (or wherever it lives post-refactor). Tests must NOT import it from `noa.private_worker`.

---

### Class 3: `TestExternalWorkerCompleteEndpoint`

**Covers:** H1, ARCH_INVARIANTS.md L10 (Wiring Completeness), SPEC.md §8.2, §14.1

**Rationale:** The external worker app currently has no `/v1/complete` endpoint. After H1 is fixed, the endpoint must be reachable, validate input, and return normalized LLM responses.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_complete_endpoint_exists` | Positive / Smoke | `POST /v1/complete` returns non-404 response |
| `test_complete_endpoint_returns_200_with_valid_payload` | Positive | Valid `{messages, max_tokens}` → HTTP 200, JSON body with `content` field |
| `test_complete_endpoint_provider_dispatches_via_router` | Positive / Integration | With mocked `ProviderRouter.complete`, verifies the router is actually called with correct args |
| `test_complete_endpoint_rejects_missing_messages` | Negative | Missing `messages` field → HTTP 422 (Pydantic validation error) |
| `test_complete_endpoint_rejects_missing_max_tokens` | Negative | Missing `max_tokens` → HTTP 422 |
| `test_complete_endpoint_rejects_empty_messages_list` | Negative / Boundary | Empty `messages: []` → HTTP 422 or 400 with error body |
| `test_complete_endpoint_provider_error_returns_502` | Negative | `ProviderRouter.complete` raises `ProviderError` → HTTP 502 or 500, NOT 200 |
| `test_complete_endpoint_privacy_violation_returns_403` | Negative / Security | `ProviderRouter.complete` raises `PrivacyViolationError` → HTTP 403, NOT 500 |
| `test_complete_endpoint_response_includes_provider_and_model` | Positive | Response JSON includes `provider` and `model` fields |

**All tests use `httpx.AsyncClient` with `ASGITransport` — no real network calls.**

**Request schema to assume (derive from deliverable description):**
```json
{
  "messages": [{"role": "user", "content": "..."}],
  "max_tokens": 1024,
  "privacy_mode": "external",
  "provider": null,
  "model": null
}
```

---

### Class 4: `TestPrivateWorkerRPCEndpoint`

**Covers:** H1, ARCH_INVARIANTS.md L10, SPEC.md §9.1, §9.2

**Rationale:** The private worker app currently has no `/rpc` endpoint. After H1 is fixed, the endpoint must validate RPC contract fields, dispatch to the correct handler, and return a valid RPC response.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_rpc_endpoint_exists` | Positive / Smoke | `POST /rpc` returns non-404 response |
| `test_rpc_remember_dispatches_to_handler` | Positive | `task_type: "remember"` with valid payload → HTTP 200, response includes `status` field |
| `test_rpc_recall_dispatches_to_handler` | Positive | `task_type: "recall"` with valid query → HTTP 200, response includes `facts` list |
| `test_rpc_missing_idempotency_key_rejected` | Negative | Request without `idempotency_key` → HTTP 422 or 400 |
| `test_rpc_invalid_task_type_rejected` | Negative | `task_type: "INVALID"` → HTTP 400 or 422, NOT 200 |
| `test_rpc_response_has_sensitivity_label` | Positive / Contract | Every valid response includes `sensitivity_label` field per §9.2 |
| `test_rpc_response_has_request_id` | Positive / Contract | Response includes `request_id` field per §9.2 |
| `test_rpc_fact_too_long_rejected` | Negative / Boundary | `fact` > 2048 chars → HTTP 400 or 422 per §9.1 limits |
| `test_rpc_n_results_capped_at_max` | Boundary | `n_results: 999` → capped at 20 (MAX_N_RESULTS) in response |
| `test_rpc_unknown_task_type_does_not_return_500` | Negative | Unknown but well-formed request → structured error, never unhandled 500 |
| `test_rpc_dlp_runs_on_response` | Positive | Response text with PII (SSN pattern) gets redacted before returning |

**All tests use `httpx.AsyncClient` with `ASGITransport`.**

**Integration note (S5):** At least one test in this class must NOT mock the handler — it must use the real `_handle_remember` / `_handle_recall` dispatch path (with `MemoryStore` backed by `tmp_path` fixture) to confirm the endpoint is actually wired to real handlers, not just stubs.

---

### Class 5: `TestGoogleAIToolCallId`

**Covers:** H9, SPEC.md §14.4 (normalized tool_calls format)

**Rationale:** Downstream orchestrator code (tools node) needs a stable `id` on each tool call to match results. Google AI's `functionCall` API returns no ID; the parser must synthesize one.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_function_call_response_includes_id` | Positive | `_parse_response()` with a `functionCall` part → `tool_calls[0]` has `"id"` key |
| `test_tool_call_id_is_hex_string` | Positive | `tool_calls[0]["id"]` is a non-empty string matching `[0-9a-f]{32}` (uuid.hex format) |
| `test_multiple_function_calls_each_have_unique_id` | Positive | Two `functionCall` parts → each `tool_calls[i]["id"]` is distinct |
| `test_text_only_response_has_empty_tool_calls` | Positive | Text-only response → `tool_calls == []`, no `id` key issues |
| `test_tool_call_preserves_name_and_input` | Regression | After adding `id`, existing `name` and `input` fields still present |
| `test_id_absent_before_fix_confirmed_by_existing_test` | Regression guard | The existing `test_function_call_returned` in `test_llm_google_ai.py` did NOT assert `"id"` — new tests fill this gap |

**Note:** The existing test `test_function_call_returned` in `tests/unit/test_llm_google_ai.py` (line 189) asserts `tc["name"]` and `tc["input"]` but does NOT assert `tc["id"]`. This is the gap H9 addresses. New tests must assert the `id` field explicitly.

---

### Class 6: `TestDomainIsolationIntegration` (S5 integration smoke)

**Covers:** C2, H1, ARCH_INVARIANTS.md L3 + L10

**Rationale:** Per ARCH_INVARIANTS.md L10 rule 4: "No orphaned code." After QC4, the refactored `OllamaClient` in `noa.llm.providers` must actually be wired into `ProviderRouter.from_settings()` — not left as an unreachable import. This is the non-mocked integration test required by QA criterion S5.

#### Tests Required

| Test | Type | Assertion |
|---|---|---|
| `test_provider_router_uses_shared_ollama_client` | Integration | `ProviderRouter.from_settings(settings)._clients["ollama"]` is an instance of `noa.llm.providers.OllamaClient` (NOT `noa.private_worker.ollama_client.OllamaClient`) |
| `test_memory_tool_uses_shared_max_n_results` | Integration | Create `MemoryTool(rpc_client=mock_rpc)`, call `recall(query="test", n_results=999)` — verify the RPC payload has `n_results == 20` (capped via `noa.constants.MAX_N_RESULTS`) |
| `test_external_worker_app_routes_include_complete` | Smoke | `create_external_app()` returns app whose routes include `POST /v1/complete` |
| `test_private_worker_app_routes_include_rpc` | Smoke | `create_private_app()` returns app whose routes include `POST /rpc` |

---

## Coverage Matrix

| QA Criterion | Tests Covering It |
|---|---|
| M1 (Spec Traceability) | All 6 classes have docstrings with finding IDs and SPEC/ARCH refs |
| M2 (Negative Tests) | Classes 1, 2, 3, 4, 5 all have multiple negative paths |
| M3 (Security Boundaries) | Class 1 (no private_worker leakage), Class 3 (PrivacyViolationError → 403 not 500) |
| M4 (Determinism) | No wall-clock time; all HTTP via ASGI transport (no network); uuid mocking not needed (uuid.hex is deterministic enough to test format, not value) |
| M5 (Implementation Completeness) | Classes 3+4 verify endpoint wiring; Class 1+6 verify shared module existence |
| M6 (No Silent Error Swallowing) | Class 3 `test_complete_endpoint_provider_error_returns_502` and Class 4 `test_rpc_unknown_task_type_does_not_return_500` |
| M7 (Wiring Completeness) | Class 6 `test_external_worker_app_routes_include_complete` + `test_private_worker_app_routes_include_rpc` |
| M8 (Domain Isolation) | Class 1 (full suite), Class 6 `test_provider_router_uses_shared_ollama_client` |
| S5 (Integration Smoke) | Class 6 (non-mocked `ProviderRouter.from_settings()`, real `MemoryStore` for RPC endpoint) |

---

## Pre-Existing Test Gaps to Watch

1. **`test_llm_router.py` uses wrong attribute name:** `_mock_settings` sets `google_api_key` but `ProviderRouter.from_settings()` reads `google_ai_api_key` (line 103 in `router.py`). The existing test `test_creates_google_ai_client_when_key_present` passes only because `getattr(settings, "google_ai_api_key", None)` returns a `MagicMock()` truthy value, not because the mock is correctly set up. After refactoring, ensure this test is not silently broken.

2. **`test_llm_router.py::TestFromSettings` instantiates `ProviderRouter.from_settings()` which currently imports `OllamaClient` from `noa.private_worker`.** After QC4, these tests should continue to pass but now source `OllamaClient` from `noa.llm.providers`. The write-code agent must not break these 9 existing tests.

3. **The existing test `test_llm_google_ai.py::TestGoogleAIResponseParsing::test_function_call_returned` (line 189) does not assert `"id"`.** The new H9 tests are additive — they must not modify the existing test file, only add new assertions in the new test file.

---

## Edge Cases and Tricky Behaviors

### C2: Lazy Import at `router.py:114`

The violation is inside `from_settings()` as a lazy import (`from noa.private_worker.ollama_client import OllamaClient`). After the fix, this line must become `from noa.llm.providers import OllamaClient`. Any test that only checks module-level imports will miss a regression where the lazy import is partially fixed.

**Required:** The domain isolation test must call `from_settings()` to trigger the lazy path.

### H1: External Worker `/v1/complete` — Router Initialization

The external worker app currently has no state (no `ProviderRouter` instance). The H1 fix must wire the router into the app — likely via an app-level dependency or a lifespan-initialized state variable. Tests must verify:
- The router is initialized during app startup (not per-request)
- If the router is not configured (no API keys), the endpoint must still return a usable error, not crash

**Required test:** `test_complete_endpoint_provider_error_returns_502` covers the "unconfigured provider" case indirectly. Consider also: `test_complete_endpoint_with_unconfigured_provider_returns_error` if the implementation creates the router lazily.

### H1: Private Worker `/rpc` — MemoryStore at `/data/memory`

The existing `handlers.py` initializes `_memory_store = MemoryStore(data_dir=Path("/data/memory"))` at module import time. This path does not exist in tests. Tests must either:
1. Patch `_memory_store` with a `MemoryStore` backed by `tmp_path`, OR
2. Ensure the RPC endpoint's handler dispatch uses a dependency-injected store

The test plan recommends option 1 (patch) for unit tests and option 2 (real path via tmp_path fixture) for the S5 integration test in Class 6.

### H9: Multiple Tool Calls

Google AI can return multiple `functionCall` parts in a single response. Each must get a unique `id`. Tests must verify this — a single shared ID would fail downstream deduplication.

---

## Anti-Pattern Warnings for the Write-Code Agent

1. **Do NOT verify domain isolation using `inspect.getsource()`** — this is a weak check (see MEMORY.md pattern on "source inspection tests"). Use `sys.modules` snapshot after calling the actual method.

2. **Do NOT mock `ProviderRouter.complete` in the domain isolation smoke test** (Class 6 `test_provider_router_uses_shared_ollama_client`) — the point of that test is to verify the wiring, which requires a real instantiation.

3. **Do NOT skip testing `/v1/complete` error paths** — the previous QC cycle had a recurring problem with tests that only cover the happy path. Every new endpoint needs at least 2 negative tests.

4. **The `/rpc` endpoint test must verify `sensitivity_label` is in the response** — this is a §9.2 contract requirement and is not tested anywhere today. Missing it would leave a spec hole.

---

## Minimum Test Count

| Class | Min Tests |
|---|---|
| TestSharedModuleImports | 6 |
| TestOllamaClientSharedBehavior | 6 |
| TestExternalWorkerCompleteEndpoint | 9 |
| TestPrivateWorkerRPCEndpoint | 11 |
| TestGoogleAIToolCallId | 6 |
| TestDomainIsolationIntegration | 4 |
| **Total** | **42** |

This is the floor. The write-tests agent may add more but must not go below this count.

---

## Spec References

| Finding | SPEC.md Section | ARCH_INVARIANTS.md Rule |
|---|---|---|
| C2 | §6.2 (dual-domain), §8.3 (inter-domain communication) | L3 (Domain Isolation), M8 checklist |
| H1 | §8.1 (private container must run RPC handler), §8.2 (external container structured outputs), §9.1-§9.2 (RPC contract) | L10 (Wiring Completeness) |
| H9 | §14.4 (normalized LLM response format) | L5 (Error Schema — consistent data shapes) |
