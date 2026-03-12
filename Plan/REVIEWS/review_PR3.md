# QA Review: Phase PR3 (Cycle 2)

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 11 tests (T1-T10b) cite PR3 / iOS-H1..H4. Spec refs present in source files. |
| M2 | Negative Tests | PASS | T2 (drain NOT called on disconnect), T8 (unknown provider returns empty), T4 (idempotent double-cancel). |
| M3 | Security Boundaries | PASS | [weak authVM] on onUnauthorized closure. No hardcoded secrets. Token provider injection. |
| M4 | Determinism | PASS | T1 uses polling loop with deadline (no fragile sleep). No wall-clock assertions. |
| M5 | Implementation Completeness | PASS | Cycle 1 blocker resolved: backend ChatRequest now accepts `model: str | None = None` and `provider: str | None = None`. Verified via Pydantic model_validate_json with missing keys -- returns None as expected. OrchestratorRunner.run() receives None and the router node falls through to `_EXTERNAL_MODEL` default. |
| M6 | No Silent Error Swallowing | PASS | No `try?` in new PR3 code. Exception paths throw specific errors. Pre-existing `except Exception` blocks in chat.py have `# noqa: BLE001` and log or yield error events. |
| M7 | Wiring Completeness | PASS | NoaApp.swift wires all components: ServiceFactory.makeNetworkMonitor(draining:via:), onUnauthorized callback with [weak authVM], ContentView -> AuthGuard -> MainTabView. onChange(of: selectedThreadId) calls cancelStreamAndClear(). |
| M8 | Domain Isolation | N/A | Pure iOS package + single backend file change; no cross-domain backend imports. |
| S1 | Error Handling & Boundaries | PASS | APIClient.replayRequest handles 401/403/404/429 with specific error types. handleUnauthorized clears both isAuthenticated and tokenExpiresAt. |
| S2 | Code Consistency | PASS | Follows existing naming conventions (actor, @Observable, @MainActor). LLMProviders.swift mirrors web Settings.tsx structure. |
| S3 | Migration & Rollback | N/A | No DB changes. |
| S4 | Documentation | PASS | All public APIs have doc comments with spec refs. iOS-H1..H4 annotations inline. |
| S5 | Integration Smoke Test | OPEN | T1 tests the drain wiring pattern but uses a mock queue, not the real OfflineQueueService. No test exercises the real NoaApp composition root. Acceptable for a library package without app target in test suite. |

## Test Plan Coverage
No pre-written test plan existed for PR3. The 11 tests (T1-T10b) cover all four fixes with both positive and negative paths. The cycle 1 gap (ChatRequest contract mismatch) has been resolved at the backend level -- the Pydantic model now accepts missing model/provider keys.

## Spec Compliance

| Requirement | Status | Detail |
|-------------|--------|--------|
| iOS-H1: drain on reconnect | PASS | ServiceFactory.makeNetworkMonitor wires onChange -> queue.drain(). NoaApp.swift calls it. |
| iOS-H2: cancel stream on thread switch | PASS | cancelStreamAndClear() clears 8 state properties (messages, isStreaming, errorMessage, currentRunId, capturedThreadId, currentIndicator, optimisticIndex, streamTask). onChange(of: selectedThreadId) calls it in MainTabView. |
| iOS-H3: handleUnauthorized on 401 | PASS | APIClient calls onUnauthorized on refresh failure (line 154) and on retry-still-401 (line 173). AuthViewModel.handleUnauthorized sets isAuthenticated=false and tokenExpiresAt=nil. NoaApp wires with [weak authVM] and Task { @MainActor in }. |
| iOS-H4: inline provider/model picker | PASS | LLMProviders catalogue correct (4 providers). ComposerBar picker works. ChatRequest CodingKeys match backend field names. Backend now accepts nil for both fields -- router node falls back to _EXTERNAL_MODEL. |

## Test Coverage

| Test | Spec Requirement | Verdict |
|------|------------------|---------|
| T1 | iOS-H1: drain on connect | PASS |
| T2 | iOS-H1: no drain on disconnect | PASS |
| T3 | iOS-H2: cancelStreamAndClear resets state | PASS |
| T4 | iOS-H2: idempotent cancel | PASS |
| T5 | iOS-H3: handleUnauthorized -> unauthenticated | PASS |
| T6 | iOS-H3: handleUnauthorized clears expiry | PASS |
| T7 | iOS-H4: 4 providers in catalogue | PASS |
| T8 | iOS-H4: models per provider + unknown | PASS |
| T9 | iOS-H4: default nil provider/model | PASS |
| T10 | iOS-H1: idempotency key round-trip | PASS |
| T10b | iOS-H1: QueuedRequest.id equals idempotencyKey | PASS |

## Anti-Pattern Scan Results
- No `TODO`/`FIXME`/`HACK` in PR3 source files: clean.
- No `try?` in PR3 production code: clean.
- No bare `except:` in chat.py: clean (ruff check passes).
- `@unchecked Sendable` on `ApiResponse<T>`: pre-existing, not PR3.

## Smoke Test Results
```
Swift tests: 170 XCTest + 12 swift-testing = 182 total, 0 failures.
Python tests: 1452 passed, 3 pre-existing failures (network_isolation, invalid_privacy_mode marker, route_count).

Backend contract verification (run in Docker):
  PASS: ChatRequest accepts omitted model/provider (both None)
  PASS: ChatRequest accepts explicit model/provider
  PASS: ChatRequest parses iOS-style JSON (missing model/provider keys)
  INFO: Runner receives model=None from chat.py, router node falls back to _EXTERNAL_MODEL
  ALL CHECKS PASSED

ruff check src/noa/api/v1/chat.py: All checks passed!
```

## Security
- `[weak authVM]` on onUnauthorized closure prevents retain cycle: correct.
- onUnauthorized dispatches to @MainActor via `Task { @MainActor in }`: correct.
- NullTokenProvider for bootstrap client returns nil/throws: correct.
- No hardcoded secrets or tokens.
- No `try?` suppressing auth errors.

## Code Quality
- Clean separation: ServiceFactory is a static composition root, NoaApp wires everything.
- LLMProviders.swift is a pure data catalogue with no side effects.
- ComposerBar correctly resets model when provider changes (providerBinding set handler).
- cancelStreamAndClear() is thorough -- clears 8 state properties including optimisticIndex.
- replayRequest correctly reuses the stored idempotency key.

## Beyond the Test Plan

### Resolved: ChatRequest contract mismatch (cycle 1 blocker)
The fix is correct and minimal: `model: str | None = None` and `provider: str | None = None` in `src/noa/api/v1/chat.py:33-34`. The runner's own `model: str = "anthropic/claude-haiku"` default on line 42 is effectively overridden when chat.py passes `model=None` explicitly, but the router node (`nodes/router.py:44-56`) handles this correctly by falling through to `_EXTERNAL_MODEL`. The classification_done event payload will contain `"model": null` which is cosmetic (not consumed by any downstream logic that would break on None).

### Note: runner.run() receives None despite having a default
`chat.py:132` passes `model=body.model` which is `None` when not set by the client, overriding the runner's `model: str = "anthropic/claude-haiku"` default parameter. This works because the graph-based path (nodes/router.py) reads `user_model_override` from state, not the `model` parameter directly. But it means the runner's default is dead code -- it only takes effect if the runner is called without `model=` keyword (which chat.py never does). Not blocking, just a clarity concern.

### Minor: NetworkMonitor never stopped
NoaApp stores `networkMonitor` but never calls `stopMonitoring()` on app termination. Acceptable (process dies anyway), but noted for iOS lifecycle completeness.

## Notes (PASS_WITH_NOTES)
1. **Runner model default is dead code**: `OrchestratorRunner.run(model: str = "anthropic/claude-haiku")` default on line 42 of runner.py is never used because chat.py always passes `model=body.model` explicitly (which may be None). The actual fallback happens in `nodes/router.py:56` (`_EXTERNAL_MODEL`). Consider removing the default from runner.run() to avoid confusion, or document that it is intentionally overridden.
2. **S5 Integration Smoke Test remains OPEN**: No test exercises the real NoaApp composition root end-to-end. This is a persistent gap across all iOS phases -- the Swift Package library target cannot import the app target. Acceptable for now but becomes a risk when the app is deployed.
3. **classification_done event contains `"model": null`** when no model is selected. If any downstream consumer (e.g., web UI, analytics) relies on this field being a non-null string, it could silently display "null" or fail. Low risk since current consumers handle it gracefully.

## Decision Review
All four fixes (iOS-H1 through iOS-H4) are correctly implemented and wired into the running app. The cycle 1 blocker (ChatRequest contract mismatch) is resolved with a clean backend-side fix. The Pydantic model now accepts omitted model/provider, and the orchestrator's router node correctly falls back to the default external model. The fix was verified both via unit tests and a direct Pydantic model_validate_json smoke test in Docker.
