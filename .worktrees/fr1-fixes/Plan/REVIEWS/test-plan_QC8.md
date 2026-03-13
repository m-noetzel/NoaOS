# Test-Plan Review: Phase QC8 — Architecture & Robustness

**Date:** 2026-03-07
**Reviewer:** qa-review agent
**Phase:** QC8 (Architecture & Robustness)
**Type:** Pre-implementation test-plan review

---

## Summary

The phase addresses 10 findings (A1-cleanup, A2, A4-stub, A5, H8-simplified, M1, M5-simplified, M7, M10, M14) via ~17 planned tests in `tests/unit/test_qc8_architecture.py`. The plan is workable but has significant gaps in test coverage for several findings, two findings whose "simplified" scope leaves the core problem unresolved, and one finding (M5) where the backend deliverable is inconsistent with the SSE client reconnect logic already in the codebase.

Overall risk: **MEDIUM-HIGH**. The simplifications and defers are mostly reasonable, but the test plan as written will allow implementations that technically "pass" without actually fixing the underlying problem. Several critical behaviors have no planned test.

---

## Finding-by-Finding Analysis

### A1 — Global Mutable State (Cleanup Only)

**Planned change:** Add `reset_all()` to `app_state.py`, add type hints to getters.

**Test adequacy assessment: INSUFFICIENT**

The plan adds `reset_all()` for test isolation. This is useful but does not verify the getter/setter contracts are maintained correctly. The planned test likely just imports `app_state` and calls `reset_all()`.

**Gaps:**
1. No test verifying that after `reset_all()`, all getters return `None`. This matters because a future addition of a new global that isn't covered by `reset_all()` would silently leak state.
2. No test verifying that type hints are correct at runtime (e.g., `get_engine()` must return `AsyncEngine | None`, not `Any`). Type annotations are not enforced at runtime without additional tooling.
3. The bigger A1 problem (globals making parallel test execution impossible) remains. The `reset_all()` approach is a workaround, not a fix. This is acceptable as a defer, but the test should verify that the workaround actually enables test isolation — i.e., a test that sets a global, calls `reset_all()`, and confirms the global is cleared.

**Required test:** `test_reset_all_clears_all_globals` — set all 6 globals via set_*(), call reset_all(), assert all get_*() return None.

---

### A2 — ProviderRouter Is Both Router and Factory

**Planned change:** Extract `build_llm_clients()` factory function. `ProviderRouter` accepts an injected `dict[str, LLMClient]`. `from_settings()` kept as a backward-compat wrapper.

**Test adequacy assessment: INSUFFICIENT**

**Gaps:**
1. No test that `ProviderRouter.__init__()` accepts a `clients` dict and stores it — the core SRP fix.
2. No test that `build_llm_clients(settings)` returns the expected dict structure when API keys are present or absent.
3. No test that `from_settings()` still works (regression guard for backward compat).
4. No test that injecting `{}` (empty clients dict) still allows the router to be constructed and raises `ProviderError` on `complete()` — rather than crashing in `__init__`.
5. The existing `ProviderRouter` has a subtle bug: `from_settings()` calls `router._clients["anthropic"] = ...` directly on the private attribute rather than via a setter. After A2, if the constructor signature changes, this pattern must change too. No test guards this interaction.

**Required tests:**
- `test_provider_router_accepts_injected_clients` — construct with dict, verify `available_providers` reflects injected keys
- `test_build_llm_clients_with_no_keys` — empty settings, returns only ollama client
- `test_from_settings_backward_compat` — from_settings() with an Anthropic key still produces working router

---

### A4 — Checkpointer Is an Empty Stub

**Planned change:** Add `NoOpCheckpointer` with `NotImplementedError` and a startup warning. SPEC.md S10.1 remains unimplemented.

**Test adequacy assessment: ADEQUATE for the reduced scope**

The plan correctly identifies A4 as too large for this phase. A `NoOpCheckpointer` with a startup warning is the right interim step.

**Gaps:**
1. The planned test presumably checks that `NoOpCheckpointer` raises `NotImplementedError`. It should also verify the startup warning is emitted (test with `caplog`).
2. Note: **SPEC.md S10.1 compliance is explicitly deferred.** This is acceptable given the complexity, but should be flagged in FINDINGS.md as still open with a note that A4 is only partially addressed by QC8.

**Required tests:**
- `test_noop_checkpointer_raises_not_implemented` — call each method, verify NotImplementedError
- `test_noop_checkpointer_emits_warning` — verify startup logging produces a warning (use `caplog`)

**Scope decision assessment:** Appropriate. Full Postgres checkpointer needs a new table + LangGraph integration and belongs in a dedicated phase.

---

### A5 — No Transaction Abstraction

**Planned change:** Create `src/noa/db/transaction.py` with async `@transactional` context manager.

**Test adequacy assessment: INSUFFICIENT**

This is one of the higher-value fixes in the phase and needs rigorous testing.

**Gaps:**
1. No test for the commit path (transaction completes, commit is called).
2. No test for the rollback path (exception raised inside the block, rollback is called, exception propagates).
3. No test for the no-commit-on-exception path (verifying the session commit is NOT called when an error occurs).
4. No test for nested transaction behavior — what happens if a transactional block is called inside another? The spec doesn't define this, but the implementation choice matters.
5. No integration test that uses `@transactional` with a real (in-memory) session to verify commit/rollback behave correctly at the SQLAlchemy level — not just with AsyncMock.

**Required tests:**
- `test_transactional_commits_on_success` — verify `session.commit()` called once
- `test_transactional_rolls_back_on_exception` — verify `session.rollback()` called, exception propagates
- `test_transactional_does_not_commit_on_exception` — negative test: commit must NOT be called when exception raised
- `test_transactional_can_be_used_as_context_manager` — `async with transactional(session): ...` syntax works

---

### H8 — Rate Limiting Per-User (Simplified: in-memory, not DB-backed)

**Planned change:** Key rate limiter by `(user_id, action)` tuple. Pass `user_id` from gateway. Still in-memory (process-local), not DB-backed.

**Test adequacy assessment: INSUFFICIENT**

The simplification (per-user key, but still in-memory) is reasonable for this phase. However, the test plan has important gaps.

**Current code problem:** `RateLimiter.check(action)` takes only `action` — no `user_id`. The `ToolGateway._rate_limits` dict is keyed by `tool_name`, not `(user_id, action)`. Both need modification.

**Gaps:**
1. No test that user A hitting a rate limit does NOT block user B for the same action (the core bug fix). This is the primary behavioral test.
2. No test that the rate limit state is properly keyed — passing `user_id=None` should fall back gracefully (not crash).
3. No negative test: user A making 10 `send_email` calls, then verifying call 11 is blocked — but user B's first call still succeeds.
4. No test that `ToolGateway.dispatch()` passes `request.user_id` to the rate limiter.

**Required tests:**
- `test_rate_limit_per_user_isolation` — user A hits limit, user B's first call succeeds
- `test_rate_limit_without_user_id_falls_back` — `user_id=None` doesn't crash, applies global limit
- `test_gateway_passes_user_id_to_rate_limiter` — dispatch propagates user_id correctly

---

### M1 — Idempotency Is Dead Code

**Planned change:** Wire `extract_idempotency_key()` via ContextVar, LRU cache for duplicate detection in chat endpoint.

**Test adequacy assessment: INSUFFICIENT**

This is the highest-complexity fix in QC8. The plan is vague about the LRU cache location and semantics.

**Critical ambiguity in plan:**
- The plan says "LRU cache for duplicate detection" but doesn't specify: LRU on what? The `IdempotencyStore` class in `src/noa/tools/idempotency.py` already has a `get/set` interface with TTL. Will QC8 use this, or create a new one? If the new one is incompatible with the existing `ToolGateway` idempotency cache (`self._idempotency_cache`), there will be two independent duplicate-detection mechanisms.
- The plan says the key is wired "via ContextVar" — this means a middleware sets the ContextVar, and the chat endpoint reads it. But the ContextVar approach means the idempotency key must be extracted from the *request* headers by the middleware and stored somewhere accessible. If the middleware only sets a trace_id ContextVar currently, adding idempotency means a second ContextVar. This needs to be explicit.

**Gaps:**
1. No test that a POST to `/api/v1/chat` with `Idempotency-Key: abc` header actually gets deduplicated — the duplicate returns the cached response without re-running.
2. No test that a different `Idempotency-Key` gets processed normally (not false-positive cached).
3. No test that missing `Idempotency-Key` header is handled gracefully (no ContextVar pollution).
4. No test for LRU eviction behavior — what happens when the cache is full?
5. No test that the idempotency check fires BEFORE the LLM call (the whole point of deduplication).

**Required tests:**
- `test_idempotency_key_extracted_from_header` — verify middleware/endpoint sees the key
- `test_duplicate_request_returns_cached_response` — same key twice, second call returns cached (no re-processing)
- `test_different_keys_processed_independently` — different keys, both processed
- `test_missing_key_processed_normally` — no key header, request proceeds as normal

---

### M5 — SSE Reconnection Loses Events (Simplified: Last-Event-ID + replay endpoint)

**Planned change:** Frontend sends `Last-Event-ID` on reconnect. Backend adds event replay endpoint.

**Test adequacy assessment: PARTIALLY ADEQUATE, with a critical observation**

**Critical observation — the frontend already reconnects without Last-Event-ID:**

Reading `sse.ts`, the `tryReconnect()` method reconnects to `/api/v1/runs/{run_id}/events` — the **streaming** endpoint — not a replay endpoint. It captures `runId` from the first event but never sends `Last-Event-ID`. The M5 fix must add `Last-Event-ID` header to the reconnect request. But the backend's `stream_run_events` endpoint would need to handle this header and replay events from the indicated position — which is a significant backend change.

The plan says "add event replay endpoint" — this should be a separate `GET /api/v1/runs/{run_id}/events/replay?after_event_id={id}` or equivalent. If it's just the same streaming endpoint with `Last-Event-ID` support, the endpoint needs to query the `run_events` DB table, which it currently doesn't (the endpoint is a placeholder that yields keepalives).

**Gaps:**
1. No test that the `stream_run_events` endpoint actually queries `run_events` from the DB (currently a stub returning keepalives only). Without this, M5 fix is theoretical.
2. No test for the replay endpoint returning events that occurred after a given event ID.
3. No test that the frontend includes `Last-Event-ID` in the reconnect request — this is a frontend behavior that's hard to unit test but must be verified via integration or manual check.
4. No test for the case where `Last-Event-ID` is older than the available event window (events were pruned).

**Required tests:**
- `test_replay_endpoint_returns_events_after_id` — given a run with 3 events, replay after event 1 returns events 2 and 3
- `test_replay_endpoint_returns_empty_for_unknown_event_id` — graceful behavior when event ID not found
- `test_stream_endpoint_sends_event_id_field` — SSE events include `id:` field so browser/client can track Last-Event-ID

**Scope decision assessment:** The simplification is reasonable, but the plan glosses over that the streaming endpoint is currently a placeholder. The replay endpoint cannot be fully functional until the streaming endpoint itself is backed by real DB data.

---

### M7 — Step-Up Auth Defined But Not Enforced

**Planned change:** Enforce step-up gate in `gateway.dispatch()`. Default to allow if no `PolicyEngine` injected.

**Test adequacy assessment: INSUFFICIENT — and the fallback default is a security regression risk**

**Critical concern on the risk note:**

The phase plan states: "M7 step-up defaults to allow if no PolicyEngine injected." This means the behavior when `PolicyEngine` is not configured is **identical to the current broken behavior** (no enforcement). The only meaningful scenario is when `PolicyEngine` IS injected. The test plan must verify:

1. When `PolicyEngine` is injected and action is high-risk, dispatch BLOCKS (or triggers step-up flow).
2. When `PolicyEngine` is not injected, dispatch proceeds (the allowed fallback).
3. There must be a test for what "step-up enforcement" actually means at the gateway level: does it return a `ToolResponse(error="step_up_required")`, raise an exception, or call a callback? This is unspecified in the plan.

**Additional gap:** `PolicyEngine.requires_step_up_auth()` returns `True` for "high" risk tier. But how does the gateway know what the risk tier of a given tool action is? The gateway has `ToolRequest.function` (e.g., "delete_data") but no direct link to `PolicyEngine`. The plan must wire this: either inject `PolicyEngine` into `ToolGateway`, or have the gateway call `engine.classify(request.function, request.args)` and then `engine.requires_step_up_auth(tier)`.

**Required tests:**
- `test_gateway_blocks_high_risk_without_step_up` — inject PolicyEngine, dispatch high-risk action, verify error response
- `test_gateway_allows_low_risk_without_step_up` — inject PolicyEngine, dispatch low-risk action, proceeds
- `test_gateway_allows_without_policy_engine` — no PolicyEngine injected, high-risk action proceeds (fallback)
- `test_gateway_step_up_error_response_format` — verify the error response has the right code/message for callers to handle

---

### M10 — Google Refresh Tokens Not Persisted

**Planned change:** Persistence callback for refresh token, load from DB at startup.

**Test adequacy assessment: INSUFFICIENT**

**Critical architectural gap:** `GoogleAuthClient` is a stateless HTTP client — it doesn't know about the DB. The plan says "persistence callback" which implies `GoogleAuthClient` gets a callback it calls after token exchange/refresh. But who holds this callback? The `registration.py` startup code would need to wire the callback to a DB write function.

More critically: "load from DB at startup" — this means at app startup, for each user who has authenticated with Google, their refresh token is loaded from DB and injected into `GoogleAuthClient`. But `GoogleAuthClient` is currently a singleton-per-tool (created once in registration). If there are multiple users, there should be one `GoogleAuthClient` per user — which doesn't match the current architecture.

**Gaps:**
1. No test for the callback-on-token-change mechanism — that `set_tokens()` calls the persistence callback.
2. No test that `refresh_access_token()` also calls the persistence callback when a new refresh token is received (§11.3 rotation).
3. No test for startup DB load — that stored tokens are restored correctly.
4. No test for the multi-user scenario — if user A and user B both have Google tokens, are they kept separate?
5. No test for the failure path: DB write for token persistence fails — does `GoogleAuthClient` still function with in-memory tokens?

**Required tests:**
- `test_set_tokens_triggers_persistence_callback` — callback is called with token data when set_tokens() is called
- `test_refresh_triggers_persistence_callback` — callback called when refresh returns new token
- `test_token_loaded_from_db_on_init` — if DB has stored token for user, it's loaded on startup
- `test_persistence_failure_does_not_break_client` — callback raises exception, client still has tokens in memory

---

### M14 — No Frontend Request Timeouts

**Planned change:** `AbortController` with 30s timeout on `fetch()` calls in `client.ts`.

**Test adequacy assessment: LIMITED — frontend unit testing applies**

M14 is a frontend change. The existing test setup for frontend code is not clear from the project structure, but unit tests for TypeScript are typically via Jest/Vitest.

**Gaps:**
1. The plan says "~17 tests in `tests/unit/test_qc8_architecture.py`" — this is a Python file. M14 is a TypeScript change. Frontend tests belong in `web/src/` with a TypeScript test runner (Jest/Vitest). If the plan intends to test M14 via the Python test file, it cannot — Python tests cannot verify TypeScript `fetch()` behavior.
2. No frontend test file mentioned in the plan for M14. This means M14 may pass "all tests" but have zero automated test coverage.
3. The 30s timeout value is a magic number — no test verifies what happens when the timeout fires (AbortError propagated, user sees an error, not a frozen UI).

**Recommendation:** Either add a Vitest test for `apiRequest()` verifying `AbortController` is created and the timeout signal is passed, or explicitly note M14 has no automated test (manual verification only). Do NOT claim test coverage in `test_qc8_architecture.py` for a frontend change.

---

## Cross-Cutting Issues

### Issue 1: 17 tests for 10 findings is under-budgeted

At ~1.7 tests per finding, the plan cannot adequately cover the behavioral requirements identified above. A conservative minimum:

| Finding | Minimum tests needed |
|---------|---------------------|
| A1 | 2 |
| A2 | 3 |
| A4 | 2 |
| A5 | 4 |
| H8 | 3 |
| M1 | 4 |
| M5 | 3 |
| M7 | 4 |
| M10 | 4 |
| M14 | 1 (or 0 with explicit note) |
| **Total** | **30** |

Targeting 17 tests means half the behaviors above won't be covered. The write-tests agent should aim for 25-30 tests.

### Issue 2: No integration test planned

CLAUDE.md and QA_CHECKLIST.md S5 require at least one non-mocked integration test per phase. The plan is silent on this. For QC8, the natural integration tests are:

- `test_transaction_rollback_real_session` — A5 with real SQLAlchemy `AsyncSession` (in-memory SQLite).
- `test_provider_router_dispatch_with_injected_clients` — A2 with real (mocked-at-HTTP) clients.

The write-tests agent must include at least one.

### Issue 3: Spec traceability must be explicit

Each test method docstring must cite a SPEC.md section or `PHASE_DETAILS.md Phase QC8`. Looking at prior QC test files (e.g., `test_qc5_database_integrity.py`), they include a header block with spec refs. QC8 tests must follow this pattern.

### Issue 4: M5 backend stub problem

The `stream_run_events` endpoint currently only yields keepalives. The M5 replay endpoint requires the ability to query past events from `run_events` table. If QC8 implements a replay endpoint but the streaming endpoint still doesn't persist events to `run_events`, the replay endpoint will always return empty. The plan doesn't address this dependency. The write-tests agent must test that the streaming endpoint (or the chat pipeline) writes events to `run_events` before testing that replay returns them.

### Issue 5: H8 simplification consequence for multi-process

The phase plan correctly notes H8 is simplified to per-user in-memory (not DB-backed). This means the finding's multi-process problem remains. The test plan should explicitly test what the simplification covers (per-user isolation) but not claim it covers what it doesn't (cross-process). The FINDINGS.md row for H8 should remain Open or be changed to "Partially Resolved" — not Resolved.

---

## Defer/Simplify Decision Assessment

| Decision | Assessment |
|----------|------------|
| A1 defer (full DI) | **Appropriate.** Full DI migration touches every endpoint and worker. Too large for QC8. |
| A4 defer (full Postgres checkpointer) | **Appropriate.** Needs new Alembic table + LangGraph integration. Not a one-phase job. |
| H8 simplify (in-memory per-user) | **Appropriate** as interim fix, but FINDINGS.md should not mark H8 Resolved — mark as "Partially Resolved: per-user keying done, DB-backed deferred." |
| M5 simplify (Last-Event-ID + replay endpoint) | **Questionable.** The replay endpoint requires the streaming endpoint to actually write events to DB, which it currently doesn't. The plan doesn't acknowledge this dependency. Risk: M5 gets "fixed" but events still aren't replayed because the DB has no events. |

---

## Regression Risk Analysis

The A2 refactor (`ProviderRouter` accepting injected clients) is the highest regression risk in this phase. Every code path that calls `ProviderRouter.from_settings()` must still work after the refactor. The plan notes `from_settings()` is kept as a backward-compat wrapper — this is correct, but all 5 callers of `ProviderRouter` in `app.py`, `chat.py`, and the worker apps must be verified to still function.

Callers to audit for regression:
- `src/noa/api/app.py` lifespan wiring
- Any test in `test_qc4_domain_isolation.py` that instantiates `ProviderRouter`
- `src/noa/private_worker/app.py` and `src/noa/external_worker/app.py` if they reference `ProviderRouter`

---

## Required Actions Before Implementation

1. **Increase test target from 17 to 25-30.** The current budget is insufficient for the findings listed.

2. **Specify M1 implementation precisely:** Clarify whether the idempotency check in chat uses `IdempotencyStore` (existing), the `ToolGateway` cache (existing), or a new LRU cache. Two independent idempotency systems would be a bug.

3. **Clarify M7 enforcement behavior:** The plan doesn't define what "blocking" means at the gateway level for step-up auth. Is it a `ToolResponse(error=...)`, an HTTP 403, or a callback? Tests can't be written without this.

4. **Add at least one non-mocked integration test** (required by QA checklist S5).

5. **M14 frontend tests:** Either add Vitest tests in `web/src/` or document that M14 is verified manually. Do not count it against the 17-test budget for Python tests.

6. **M5 dependency:** The test plan must include a test that the streaming endpoint actually persists events to `run_events` before testing that the replay endpoint can retrieve them. Otherwise M5 is "fixed" in theory but broken in practice.

---

## Verdict

**CONDITIONAL PROCEED** — The overall phase scope and defer/simplify decisions are sound. The critical concern is that the test budget (17 tests) and missing behavioral tests for H8, M1, M7, and M10 will produce a phase that technically passes while leaving the core problems unresolved. The write-tests agent should target 25-30 tests and address the specific gaps called out above for each finding.

The M5 backend dependency (streaming endpoint must write events to DB for replay to work) is a latent correctness risk and should be explicitly tracked.
