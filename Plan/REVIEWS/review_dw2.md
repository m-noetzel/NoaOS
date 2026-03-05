# QA Review: DW2 — External Worker Skeleton

**Reviewer:** QA Agent
**Date:** 2026-03-04
**Phase:** DW2
**Spec refs:** SPEC.md §8.2, §6.2 (Domain B), §14.1, §14.2, §14.4

---

## Test Results

- **16 tests, 16 passed, 0 failed**
- All tests run deterministically (no flakes, no network, no randomness)

---

## Must-Haves

### M1: Spec Traceability — PASS

- [x] Test file has top-level docstring citing SPEC.md §8.2, §6.2, §14.1
- [x] Each test class has a docstring explaining what it validates
- [x] Each test method has a docstring citing the relevant spec section/rule
- [x] All spec requirements from the phase plan have corresponding tests:
  - §14.1/§14.2 Provider routing: default selection, user override, private mode rejection — tested
  - §14.4 User controls: temperature, top_p configurable per provider — tested
  - §6.2 Domain B tools: registry, dispatch, unregistered rejection — tested
  - §8.2 Structured outputs: FastAPI app, health endpoint, JSON-only responses — tested
  - Error handling: provider failure, timeout wrapping — tested
- [x] No orphan tests — all trace to spec requirements

### M2: Negative Tests — PASS

- [x] Multiple negative/error-path tests:
  - Private mode routing to external raises `ValueError` with "private" in message
  - Unregistered tool dispatch raises `KeyError` with tool name
  - Provider failure raises `ProviderError`
  - Timeout raises `ProviderError` with "timeout" in message
- [x] Error tests verify specific error types and match patterns (not bare `Exception`)

### M3: Security Boundaries — PASS

- [x] No hardcoded secrets in src/ — API keys are constructor parameters, not embedded
- [x] Test API keys are clearly fake (`"sk-test"`, `"sk-test-anthropic"`)
- [x] Privacy mode enforcement is a hard gate: `privacy_mode="private"` raises `ValueError` unconditionally in the router — this correctly implements §14.2 rule 1 ("If privacy_mode: private -> Ollama, mandatory, no exceptions")
- [x] Domain isolation respected — external worker has no imports from `noa.private_worker`
- [x] No direct access to private data in any external worker code

### M4: Determinism — PASS

- [x] No wall-clock time dependency
- [x] No network access — `_send_request` is mocked in all async tests
- [x] No random values
- [x] Tests pass consistently

### M5: Implementation Completeness — PASS

- [x] All files from phase plan created:
  - `src/noa/external_worker/__init__.py` — created
  - `src/noa/external_worker/app.py` — created (FastAPI app with health endpoint)
  - `src/noa/external_worker/llm/__init__.py` — created
  - `src/noa/external_worker/llm/anthropic.py` — created
  - `src/noa/external_worker/llm/openai.py` — created
  - `src/noa/external_worker/llm/router.py` — created
  - `src/noa/external_worker/tools/__init__.py` — created
  - `tests/unit/test_external_worker.py` — created
- [x] Extra file `src/noa/external_worker/exceptions.py` — created (not in plan, but good practice: centralizes error types)
- [x] No TODO/FIXME/HACK comments in any source file
- [x] `_send_request` in both clients raises `NotImplementedError` with `# pragma: no cover` — this is appropriate for a skeleton phase. The actual HTTP transport is a future concern (real API calls need httpx/aiohttp integration).

---

## Should-Haves

### S1: Error Handling & Boundaries — PASS

- [x] Error messages are specific ("Timeout calling Anthropic API", "private mode forbids routing to external providers")
- [x] `ProviderError` hierarchy: base `ProviderError`, specialized `ProviderTimeoutError`, `PrivacyViolationError`

### S2: Code Consistency — PASS

- [x] Follows existing naming conventions (matches private_worker patterns)
- [x] Consistent module structure with rest of codebase
- [x] No duplicate abstractions (ToolRegistry is new, doesn't overlap with existing code)

### S3: Migration & Rollback — N/A

No DB schema changes.

### S4: Documentation — PASS

- [x] All public functions have type annotations
- [x] Module-level docstrings reference spec sections
- [x] Docstrings on all classes and public methods

---

## Spec Compliance Deep-Dive

### Provider Routing (§14.1, §14.2) — Correct

| Rule | Spec Requirement | Implementation | Match |
|------|-----------------|----------------|-------|
| Rule 1 | privacy_mode: private -> Ollama only | `ValueError` raised if `privacy_mode="private"` | Yes |
| Rule 2 | User explicit selection overrides default | `user_selected` parameter takes priority | Yes |
| Rule 4 | Otherwise -> configured default | `self._default_provider` returned | Yes |
| Rule 3 | Private unavailable -> queue and wait | N/A for external worker (orchestrator concern) | N/A |

### Provider Clients (§14.1, §14.4) — Correct

- Anthropic client builds correct request shape: `model`, `messages`, `max_tokens`, optional `temperature`
- OpenAI client builds correct request shape: `model`, `messages`, `max_tokens`, optional `top_p`
- Both providers listed in §14.1 table (Anthropic, OpenAI) have client implementations
- Per-request parameter configuration (§14.4): temperature and top_p are per-request, not hardcoded

### Tool Registry (§6.2 Domain B) — Extensible

- Register/discover/dispatch pattern is clean and extensible
- `KeyError` on unregistered tools prevents unauthorized tool invocation
- `list_tools()` enables introspection (useful for tool allowlists per §2.1)

### External Worker App (§8.2) — Correct

- FastAPI app with `default_response_class=JSONResponse` enforces "structured outputs (JSON)" requirement
- Health endpoint returns JSON `{"status": "ok"}`
- Content-type header verified as `application/json`

### Error Handling — Correct

- `asyncio.TimeoutError` caught and wrapped as `ProviderError` with descriptive message
- Provider HTTP failures propagated as `ProviderError`
- Exception hierarchy allows callers to catch broadly (`ProviderError`) or specifically (`ProviderTimeoutError`)

---

## Issues

**None blocking.**

Minor observations:
1. The `ProviderRouter.select()` does not validate that `user_selected` is a known provider from the config. A user could select `"deepseek"` and get it returned without validation. This is low-risk for the skeleton phase but should be tightened when real routing is wired up.
2. The OpenAI client `complete()` catches `TimeoutError` but not `asyncio.TimeoutError` explicitly (Python 3.11+ `TimeoutError` is the base for `asyncio.TimeoutError`, so this works correctly, but an explicit import would be clearer).

---

## Scoring

- Must-haves: **5/5**
- Should-haves: **3/3** (S3 N/A)

## Verdict: **PASS**

All must-haves pass. Privacy mode enforcement is correctly a hard gate. Provider routing follows §14.2 rules. Both LLM clients format requests per §14.1/§14.4. Tool registry is extensible. The skeleton uses `NotImplementedError` for HTTP transport only, which is appropriate scope for this phase. All 16 tests pass.
