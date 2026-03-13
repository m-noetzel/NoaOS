# QA Review: Phase PR5

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 9/9 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 12 web tests + 10 Swift tests have docstrings citing finding IDs (FE-M1-M4, iOS-M1-M5) and SPEC.md sections |
| M2 | Negative Tests | PASS | FE-M4: empty + whitespace-only API key rejection (2 tests). iOS-M3: biometric failure + user cancellation distinction (2 tests). iOS-M5: CancellationError path tested |
| M3 | Security Boundaries | PASS | No hardcoded secrets. Auth flag in localStorage only (tokens in httpOnly cookies per C6). Artifact download sends Authorization header. CredentialModal trims + rejects empty keys |
| M4 | Determinism | PASS | No wall-clock time in assertions, no network calls, no unseeded randomness |
| M5 | Implementation Completeness | PASS | All 9 deliverables implemented: FE-M1 (online indicator), FE-M2 (navigate redirect + useEffect cleanup), FE-M3 (blob download), FE-M4 (validation), iOS-M1 (lifecycle cleanup), iOS-M2 (loadTask cancellation), iOS-M3 (biometric retry), iOS-M4 (batch deny confirm), iOS-M5 (cancel button + timeout) |
| M5b | Findings Currency | PASS | FINDINGS.md rows FE-M1 through FE-M4 and iOS-M1 through iOS-M5 all updated to Resolved/PR5. Open/Resolved counts correct (10/90/100) |
| M6 | No Silent Error Swallowing | PASS | No bare except blocks in changed files. Artifact download throws on !response.ok. Voice cancel transitions to .error state on failure |
| M7 | Wiring Completeness | PASS | TopBar is already mounted in layout. AuthContext.tsx registers handler in useEffect with cleanup. Artifact download function used by button onClick. CredentialModal already rendered in Tools page. iOS views all mounted in MainTabView |
| M8 | Domain Isolation | PASS | No cross-domain imports. Frontend-only + iOS-only phase. grep confirmed clean boundaries |
| M8b | Cross-Language Optionality | PASS | No new Pydantic models in this phase |
| S1 | Error Handling & Boundaries | PASS | Validation error clears on new input. Biometric distinguishes retryable vs user-cancelled. Upload timeout bounded to 30s |
| S2 | Code Consistency | PASS | Follows existing patterns: useEffect cleanup, @Observable, actor-based mocks, vi.doMock for module-level constants |
| S3 | Migration & Rollback | N/A | No DB changes |
| S4 | Documentation | PASS | All functions have comments explaining why. VoiceRecordButton states are well-documented. AuthContext cleanup has rationale comment |
| S5 | Integration Smoke Test | OPEN | All tests mock dependencies. No non-mocked integration test in this phase. This is consistent with prior frontend phases but remains a gap |

## Test Plan Coverage
No test plan was written for PR5 (skipped pre-implementation). Despite this, test coverage is adequate. 12 web + 10 Swift tests cover all 9 deliverables.

## Spec Compliance

| Requirement | Status |
|------------|--------|
| FE-M1: Online indicator reflects navigator.onLine | Implemented. useState + useEffect with online/offline events. data-testid for both states |
| FE-M2: Session expiry uses React Router navigate | Implemented. registerSessionExpiredHandler in client.ts, registered in AuthContext useEffect. Cleanup returns no-op handler on unmount |
| FE-M3: Artifact download uses auth headers | Implemented. fetch() with Authorization header + credentials:"include". Blob URL approach with document.body.appendChild for Firefox. requestAnimationFrame for cleanup |
| FE-M4: CredentialModal rejects empty keys | Implemented. Trims whitespace, rejects empty, shows validation error with role="alert" and aria-describedby |
| iOS-M1: MainTabView lifecycle cleanup | Implemented. Optional networkMonitor/offlineQueue params. onDisappear calls stopMonitoring/clear |
| iOS-M2: loadHistory race fix | Implemented. loadTask tracked and cancelled before new load. cancelStreamAndClear also cancels loadTask |
| iOS-M3: Biometric retry UI | Implemented. isBiometricError flag + pendingDecision. Alert with "Try Again" + isSubmitting guard. userCancelled distinguished from retryable errors |
| iOS-M4: Batch deny confirmation | Implemented. confirmationDialog with destructive "Deny All" button. Count-aware title and message |
| iOS-M5: Upload cancel + timeout | Implemented. Cancel button in uploading state. withTimeout helper (30s). CancellationError surfaces as .error state |

## Test Coverage

| Test | Finding/Spec | Category |
|------|-------------|----------|
| FE-M1: 4 tests (online/offline initial + event switching) | FE-M1 | Behavioral |
| FE-M2: 2 tests (handler export + registration contract) | FE-M2 | Behavioral |
| FE-M3: 1 test (fetch with auth header + blob download) | FE-M3 | Integration-like |
| FE-M4: 5 tests (empty, whitespace, trim, valid, closed modal) | FE-M4 | Behavioral |
| iOS T1: MainTabView accepts optional lifecycle params | iOS-M1 | Behavioral |
| iOS T2: cancelStreamAndClear resets all state | iOS-M2 | Behavioral |
| iOS T3: loadHistory populates + second call replaces | iOS-M2 | Behavioral |
| iOS T4-T6: Biometric failure, pending decision, user cancel | iOS-M3 | Behavioral + Negative |
| iOS T7: batchDeny calls decide per selected item | iOS-M4 | Behavioral |
| iOS T8-T10: cancel resets, CancellationError, timeout bounds | iOS-M5 | Behavioral + Negative |

**Gaps:**
- FE-M2 tests verify the handler registration contract but not the actual 401-response-triggers-handler flow. This belongs in E2E (PR6).
- FE-M3 test verifies fetch is called with correct headers but jsdom's navigation warning shows the blob download triggers jsdom's not-implemented navigation handler. The test still passes and asserts correctly.
- No test for the cleanup function returned by the AuthContext useEffect (unmount path).

## Anti-Pattern Scan Results

**M6 (bare except):** No `except:` or `except Exception:` in web/src/ (frontend phase, not applicable). No bare catch blocks in Swift files.

**M7 (wiring):** TopBar already in AppSidebar layout. AuthContext mounts in App.tsx. Artifact download wired via onClick. CredentialModal rendered in Tools page. iOS views in MainTabView.

**M8 (domain isolation):**
- `grep "from noa.private_worker" src/noa/external_worker/` -- no matches
- `grep "from noa.external_worker" src/noa/private_worker/` -- no matches

## Smoke Test Results

**Python backend:**
```
PASS: create_app imports OK
All smoke checks passed
```

**Frontend tests:**
```
 ✓ src/test/pr5-polish.test.tsx (12 tests) 130ms
 Test Files  1 passed (1)
      Tests  12 passed (12)
```

**Ruff:** 1 pre-existing E501 (line-too-long). No new issues.

## Security

- **No hardcoded secrets.** Grep for password/secret/token/api_key in src/ found only mock/test values.
- **Auth tokens in httpOnly cookies.** localStorage stores only the "isAuthenticated" boolean flag.
- **Artifact download sends Authorization header.** Previously, artifact downloads bypassed auth by using bare `<a href>`. Now uses fetch() with credentials:"include" and explicit Bearer token.
- **CredentialModal input validation.** Empty and whitespace-only API keys rejected client-side. Trimmed before onSave.
- **Note:** ErrorBoundary (line 43) renders `error.stack` to the user. This is a pre-existing issue from QC6, not introduced by PR5. In production it could leak internal component paths. Non-blocking (pre-existing).

## Code Quality

- Clean, well-documented code across all changed files.
- AuthContext useEffect cleanup pattern is correct -- registering a no-op handler prevents stale closures from firing during hot-reload.
- iOS `cancelStreamAndClear()` is a good single-method-replaces-two-calls pattern that prevents callers from forgetting to cancel the loadTask.
- The `withTimeout` helper is a clean implementation of structured concurrency timeout.
- CredentialModal's validation error clears on new input (line 54), good UX.

## Beyond the Test Plan

1. **AuthContext cleanup handler is a no-op, not null.** The cleanup registers `() => {}` rather than setting the handler to null. This means if the AuthProvider unmounts and then a 401 fires, the no-op runs silently instead of falling through to `window.location.href`. This is arguably correct (avoids navigation after unmount) but worth documenting as intentional.

2. **Artifact download error is console.error only.** The catch in Artifacts.tsx (line 105-107) logs to console but doesn't show the user a toast or error message. For a download failure, the user gets no feedback. Minor UX gap.

3. **MainTabView onDisappear calls offlineQueue.clear().** This deletes all queued items, not just stops processing. If the user logs out and back in, any queued offline requests are permanently lost. The intent seems correct (clean slate on logout) but could surprise users if they expected queued requests to survive a re-login.

4. **VoiceRecordButton .transcribed state uses Color.clear hack.** The `.onAppear` callback on a zero-size view is a workaround for triggering side effects from a state change. This works but is fragile -- if SwiftUI decides not to render the zero-size view, the callback won't fire.

## Notes (PASS_WITH_NOTES)

1. **S5 open:** No non-mocked integration test in this phase. FE-M2's full 401 flow and FE-M3's download flow should be tested in PR6's E2E suite.

2. **Artifact download failure silently logged.** Consider adding a toast notification in the catch block at Artifacts.tsx:105-107 so users know when a download fails.

3. **ErrorBoundary stack trace exposure (pre-existing).** `ErrorBoundary.tsx:43` renders `error.stack` to the UI. In production this leaks internal paths. Consider gating behind a `NODE_ENV === "development"` check.

## Decision Review

No architectural concerns. This phase cleanly resolves 9 medium-severity findings with appropriate tests. The implementation quality is consistent with earlier PR phases. All FINDINGS.md rows are updated correctly.
