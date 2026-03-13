# QA Review: Phase QC8

**Date:** 2026-03-07
**Verdict:** FAIL
**Reviewer:** qa-review agent

## Checklist Score
**Must-haves:** 5/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Tests cite SPEC.md sections and Phase QC8 throughout |
| M2 | Negative Tests | PASS | Error-path tests exist: ProviderError on empty clients, rollback on exception, rate-limit blocking, step-up blocking, empty code raises GoogleAuthError |
| M3 | Security Boundaries | PASS | No hardcoded secrets; CORS not wildcard; no localStorage usage introduced |
| M4 | Determinism | PASS | No wall-clock time in test assertions; time.monotonic() used in production only; all network calls mocked |
| M5 | Implementation Completeness | FAIL | M5 Last-Event-ID not sent on SSE reconnect; M7 PolicyEngine not wired at startup; M10 on_token_change not wired in registration.py |
| M6 | No Silent Error Swallowing | PASS | All `except Exception` blocks log or re-raise; `# noqa: BLE001` comments include re-raise justification |
| M7 | Wiring Completeness | FAIL | NoOpCheckpointer (A4) never instantiated anywhere; transactional() (A5) never imported in production; PolicyEngine never assigned to gateway.policy_engine in app.py; on_token_change never passed to GoogleAuthClient in registration.py |
| M8 | Domain Isolation | PASS | No private_worker→external_worker imports; no external_worker→private_worker imports; OllamaClient now in noa.llm.providers |
| S1 | Error Handling & Boundaries | PASS | Boundary errors covered; GoogleAuthError on empty code, ProviderError on missing client |
| S2 | Code Consistency | PASS | Consistent naming, layering respected, no duplicate abstractions |
| S3 | Migration & Rollback | N/A | No DB schema changes in this phase |
| S4 | Documentation | PASS | Type annotations present; non-obvious logic has inline comments |
| S5 | Integration Smoke Test | OPEN | replay_run_events test exists but asserts only `result is not None`; stream test is the closest to integration but uses mock user; no test exercises the full middleware→endpoint→ContextVar chain for idempotency |

---

## Spec Compliance

### A1 (Global Mutable State — cleanup)
PASS. `reset_all()` is implemented and tested. All 6 globals cleared on call.

### A2 (ProviderRouter refactor — injected clients)
PASS. `ProviderRouter.__init__` accepts `clients` dict. `build_llm_clients()` is a standalone factory. `from_settings()` delegates to it. Domain isolation is fixed: `OllamaClient` now comes from `noa.llm.providers`, not `noa.private_worker.ollama_client`.

### A4 (Checkpointer stub — NoOpCheckpointer)
PARTIAL — WIRING MISSING. `NoOpCheckpointer` is defined with correct `NotImplementedError` raises and startup warning. But it is never instantiated or referenced anywhere in `src/noa/orchestrator/`. The runner continues to have no checkpointer whatsoever. This violates L10 (wiring completeness): the class exists in `src/` but is not reachable from any running application entry point.

### A5 (Transaction abstraction)
PARTIAL — WIRING MISSING. `transactional()` context manager is correctly implemented: commits on success, rolls back on exception, re-raises. However, it is never imported or used anywhere in the production codebase (`grep` returns no hits in `src/noa/` outside the module itself). The finding (A5) required standardising how transactions are handled; delivering a utility function nobody calls does not fix the pattern.

### H8 (Per-user rate limiting)
PASS. `RateLimiter.check()` now accepts `user_id` and keys by `(user_id, action)`. `ToolGateway.dispatch()` uses a `user_key = f"{request.user_id or '__global__'}:{tool}"` pattern for its internal `_per_user_rate_calls` dict. Tests confirm user A hitting limit does not block user B.

### M1 (Idempotency wiring)
PARTIAL — ENDPOINT NOT WIRED. The `idempotency_key_ctx` ContextVar exists and is populated by middleware. The `IdempotencyStore` class is implemented and tested. However, `chat.py` never reads `idempotency_key_ctx` and never calls `IdempotencyStore`. The PHASE_DETAILS plan explicitly states: "Wire idempotency key via ContextVar, LRU cache for duplicate detection" in `chat.py`. This wiring is absent. The middleware sets the ContextVar, but no endpoint reads it or deduplicates chat requests. The finding (M1: Idempotency Implementation Is Dead Code) remains dead code.

### M5 (SSE reconnection — Last-Event-ID)
PARTIAL — CRITICAL GAP. The backend `stream_run_events` correctly emits `id:` fields. The backend `replay_run_events` stub endpoint exists. However, the frontend `sse.ts` `tryReconnect()` method reconnects to the events URL without sending `Last-Event-ID`. The `startStream()` method builds headers that include Authorization and Content-Type, but no `Last-Event-ID` header is ever added. The client tracks `this.runId` for reconnect URL but never tracks `lastEventId`. The PHASE_DETAILS plan states "Send Last-Event-ID on reconnect" in sse.ts. This is not implemented.

### M7 (Step-up auth enforcement)
PARTIAL — NOT WIRED IN PRODUCTION. `ToolGateway.dispatch()` checks `self.policy_engine` and enforces step-up when injected. Tests pass by manually setting `gw.policy_engine = PolicyEngine()`. However, in `app.py`'s `wire_llm_pipeline()`, the ToolGateway is constructed and registered without ever assigning a `PolicyEngine`. The attribute defaults to `None` (line 104 of gateway.py: `self.policy_engine: Any | None = None`). In production, `policy_engine is None` → step-up check is skipped → high-risk actions proceed without re-authentication. The finding (M7: Step-Up Auth Defined But Not Enforced) remains unfixed in the running application.

### M10 (Google refresh token persistence)
PARTIAL — CALLBACK NOT WIRED. `GoogleAuthClient` correctly accepts `on_token_change` and calls it on token changes. `_notify_token_change()` handles async-callback detection and callback errors. However, `registration.py` constructs `GoogleAuthClient` without passing `on_token_change` (line 66-73). The persistence callback the phase plan describes ("Persistence callback for refresh token, load from DB at startup") is never connected to actual storage. Tokens still only persist in memory for the process lifetime.

### M14 (Frontend request timeouts)
PASS. `AbortController` with 30s timeout is implemented in `client.ts`. Both frontend tests confirm the signal is passed to fetch and is not already aborted.

---

## Test Coverage

### Spec traceability
All 31 backend tests include docstrings referencing SPEC.md sections and Phase QC8. No orphan tests observed.

### Negative/error-path tests
Present for all major behaviors:
- `test_empty_clients_raises_on_complete` — ProviderError
- `test_transactional_rolls_back_on_exception` — exception propagates
- `test_transactional_does_not_commit_on_exception` — commit not called
- `test_rate_limit_per_user_isolation` — blocked after limit
- `test_gateway_blocks_high_risk_without_step_up` — error returned
- `test_persistence_failure_does_not_break_client` — callback failure isolated

### Critical gaps
1. No test verifies that `chat.py` reads `idempotency_key_ctx` or deduplicates chat requests. Tests only verify the ContextVar exists and IdempotencyStore works in isolation.
2. No test verifies that `gateway.policy_engine` is set to a `PolicyEngine` instance during app startup (M7 wiring gap is untested).
3. No test verifies that `registration.py` passes `on_token_change` to `GoogleAuthClient` (M10 wiring gap is untested).
4. No test verifies that SSE client sends `Last-Event-ID` on reconnection (M5 frontend gap is untested).
5. The M5 `test_replay_endpoint_returns_events_after_id` test passes with `assert result is not None` — this is a near-vacuous assertion since the stub always returns a valid response regardless of `after_event_id`. It does not verify the spec requirement that events after the given ID are returned.

### S5 (Integration smoke test)
Tests are largely unit tests with mocks. The `test_stream_endpoint_sends_event_id_field` test does call the real endpoint function and consume its iterator — this is the strongest integration test present. The idempotency, M7, and M10 tests are fully isolated from the wiring in `app.py`.

---

## Anti-Pattern Scan Results

```
# M6: Bare except blocks
grep -rn "except:" src/noa/ → No matches (PASS)
grep -rn "except Exception: pass" src/noa/ → No matches (PASS)

# All except Exception blocks use # noqa: BLE001 and either:
# - log via logger.exception() or logger.warning(exc_info=True)
# - re-raise
# Note: maintenance/retention.py:71,78,96,103 have bare `except Exception:`
# without noqa but use logger.exception() — acceptable per L9

# M7: Wiring — routers registered
grep -rn "include_router" src/noa/api/app.py:
  runs_router → registered (line 304) ✓

# M7: NoOpCheckpointer — NOT wired
grep -rn "NoOpCheckpointer" src/ → only in checkpointer.py definition (FAIL)

# M7: transactional — NOT wired
grep -rn "from noa.db.transaction" src/ → No matches (FAIL)

# M7: policy_engine — NOT assigned in app.py
grep -rn "policy_engine" src/noa/api/app.py → No matches (FAIL)

# M7: on_token_change — NOT passed in registration.py
grep -rn "on_token_change" src/noa/tools/registration.py → No matches (FAIL)

# M8: Domain isolation
grep -rn "from noa.private_worker" src/noa/external_worker/ → No matches (PASS)
grep -rn "from noa.external_worker" src/noa/private_worker/ → No matches (PASS)

# M5: Last-Event-ID in sse.ts
grep -rn "Last-Event-ID" web/src/api/sse.ts → No matches (FAIL)
```

---

## Smoke Test Results

Imports were verified by reading the module sources. Key findings:

```
# app_state.py — reset_all() exists, all 6 globals declared: PASS
# router.py — build_llm_clients() exists, no private_worker import: PASS
# checkpointer.py — NoOpCheckpointer exists: PASS (class only)
# transaction.py — transactional() exists: PASS (function only)
# rate_limiter.py — RateLimiter.check() accepts user_id: PASS
# gateway.py — step-up check present, policy_engine=None default: PASS (code)
# middleware.py — idempotency_key_ctx ContextVar set in dispatch: PASS
# runs.py — replay_run_events exists, has TODO comment: PASS (stub)
# google_auth.py — on_token_change accepted and called: PASS
# client.ts — AbortController with 30s timeout: PASS
# sse.ts — no Last-Event-ID sent on reconnect: FAIL

# Production wiring gaps (not catchable by import test):
# - gateway.policy_engine never set in app.py → M7 dead in prod
# - on_token_change never passed in registration.py → M10 dead in prod
# - idempotency_key_ctx never read in chat.py → M1 still dead in prod
# - NoOpCheckpointer never instantiated → A4 stub not surfacing warning at startup
# - transactional() never called in prod → A5 delivers utility, not fix
```

---

## Security

No new security vulnerabilities introduced. All `except Exception` blocks log before continuing or re-raise. No hardcoded secrets. The CORS wildcard filter is preserved (`o.strip() != "*"`). The `idempotency_key_ctx` ContextVar contains no sensitive data. The `on_token_change` callback receives tokens but `_notify_token_change()` does not log them (L6 compliant).

One concern: `registration.py` calls `auth.set_tokens(access_token="", refresh_token=refresh_token)` with an empty access_token (line 75). This is by design (access tokens are obtained on first use via refresh), but it does invoke `_notify_token_change()` at startup with an empty `access_token`, which would be a no-op since `on_token_change` is `None` there. If this were ever wired with a callback, the callback would receive `access_token=""` which could be stored to the DB as a valid (but empty) token. Low risk given current state, but worth noting.

---

## Code Quality

**gateway.py:** The internal `_RateLimit._check()` dataclass (lines 59-72) is now dead code — it is defined but never used since the per-user rate limiting was implemented inline in `dispatch()` using `_per_user_rate_calls`. This is a confusing dual-implementation pattern: `_RateLimit` exists as a dataclass with `check()` method, but `dispatch()` reimplements the same sliding-window logic inline. The `_RateLimit.check()` method is never called.

**runs.py replay endpoint:** The `TODO` comment on line 94 is a deferred-required-work TODO, which M5 of the QA checklist flags as a potential FAIL. The phase plan explicitly scoped M5 as "simplified" and states the stub is intentional. However, calling it "simplified" does not change that the endpoint always returns `events: []` regardless of `after_event_id`. A client using `Last-Event-ID` will always get an empty response, making the reconnection replay functionally useless until the TODO is implemented.

**sse.ts reconnect:** `tryReconnect()` guards on `if (!this.closed && !this.runId)`. If the stream is disconnected before the first `run_id` is captured in `parsed.run_id`, reconnection is silently skipped. This means a disconnect during initial connection setup permanently loses the stream with no error surfaced.

**google_auth.py:** `exchange_code()` directly accesses `body["access_token"]` and `body["refresh_token"]` without checking if these keys exist (lines 178-179). If the Google API returns a success response missing `refresh_token` (which can happen when `access_type` is not `offline` or on subsequent exchanges), this will raise an uncaught `KeyError` that propagates as an unhandled exception rather than a `GoogleAuthError`.

---

## Blocking Issues (FAIL)

1. **M7 wiring gap — M5 Implementation Completeness (FAIL):** `gateway.policy_engine` is never assigned a `PolicyEngine` instance in `app.py`'s `wire_llm_pipeline()`. In production, `policy_engine is None` so the step-up auth check (lines 157-165 of gateway.py) is always skipped. High-risk actions proceed without re-authentication. Finding M7 is claimed fixed but remains broken in the running application. **File:** `src/noa/api/app.py` (missing: `gateway.policy_engine = PolicyEngine()` after gateway construction on line 103-108).

2. **M10 wiring gap — M5 Implementation Completeness (FAIL):** `registration.py` constructs `GoogleAuthClient` without passing `on_token_change` (line 66-73). The persistence callback mechanism built in QC8 is never connected to actual storage at startup. Finding M10 (Google Refresh Tokens Not Persisted) remains unresolved in the running application. **File:** `src/noa/tools/registration.py:66`.

3. **M1 wiring gap — M5 Implementation Completeness (FAIL):** `chat.py` never reads `idempotency_key_ctx` and never calls `IdempotencyStore`. The phase plan states "Wire idempotency key via ContextVar, LRU cache for duplicate detection" in `src/noa/api/v1/chat.py`. This wiring is entirely absent. Finding M1 (Idempotency Implementation Is Dead Code) remains dead code. **File:** `src/noa/api/v1/chat.py` (idempotency_key_ctx not imported, IdempotencyStore not instantiated).

4. **M5 frontend gap — M5 Implementation Completeness (FAIL):** `sse.ts` `tryReconnect()` does not send `Last-Event-ID` header on reconnection. The client tracks `this.runId` (for URL) but never tracks the last-seen event ID, and `startStream()` never adds `Last-Event-ID` to headers. The reconnect endpoint exists but is never called. **File:** `web/src/api/sse.ts:137-148` (no lastEventId tracking, no Last-Event-ID header).

5. **A4 stub not wired — M7 Wiring Completeness (FAIL):** `NoOpCheckpointer` is defined in `src/noa/orchestrator/checkpointer.py` but is never imported or instantiated in `src/noa/orchestrator/runner.py` or `app.py`. The startup warning it is supposed to emit (per the phase plan: "startup warning") never fires. L10 requires no orphaned code in `src/`. **File:** `src/noa/orchestrator/checkpointer.py` (class defined but unreachable from any entry point).

6. **A5 utility not adopted — M7 Wiring Completeness (FAIL):** `transactional()` in `src/noa/db/transaction.py` is never imported or used anywhere in production code. The original finding A5 cited inconsistent `flush()`/`commit()` calls across services; this phase delivers a utility no service uses. L10 violation. **File:** `src/noa/db/transaction.py` (function defined but unreachable from any entry point).

---

## Notes

1. **gateway.py `_RateLimit` is dead code.** Lines 59-72 define a `_RateLimit` dataclass with a `check()` method that is never called. The rate-limiting logic is reimplemented inline in `dispatch()`. Remove `_RateLimit` or use it.

2. **google_auth.py `exchange_code()` may raise `KeyError`.** Lines 178-179 access `body["access_token"]` and `body["refresh_token"]` without guarding. Use `.get()` and raise `GoogleAuthError` explicitly if missing, to maintain the documented exception contract.

3. **M5 replay endpoint TODO is a functional placeholder.** The endpoint always returns `events: []`. The reconnect feature is architectural theater until the event store is populated. This should be tracked as a new open finding or the scope explicitly noted in FINDINGS.md.

4. **sse.ts silent reconnect drop.** If `this.runId` is not captured before disconnect, `tryReconnect()` silently returns without attempting reconnect or calling `onError`. Users see the stream die with no feedback.

5. **test_replay_endpoint_returns_events_after_id asserts `result is not None`.** This is a near-vacuous test: the stub always returns a non-None result. A meaningful test should assert `result["data"]["events"] == []` and document that as the current expected behavior.

---

## Decision Review

The PHASE_DETAILS scope decisions are reasonable (defer full DI migration, defer full checkpointer). However, the decisions were not fully reflected in the implementation:

- "SIMPLIFY: M5 (frontend Last-Event-ID + backend replay endpoint)" — only the backend stub was delivered; the frontend Last-Event-ID sending was not.
- "INCLUDE: M7" — included in code but not in startup wiring.
- "INCLUDE: M10" — included in GoogleAuthClient but not in registration.py startup wiring.

The risk note "M7 step-up defaults to allow if no PolicyEngine injected" is documented in PHASE_DETAILS but the intent was that the PolicyEngine *would* be injected in normal operation. The wiring step to actually inject it was not completed.

These are execution gaps, not decision gaps. The phase decisions were sound; the implementation did not fully execute on them.
