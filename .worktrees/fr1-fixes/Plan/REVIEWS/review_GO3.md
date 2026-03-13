# QA Review: Phase GO3

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 9/9 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 16 tests have spec ref docstrings (SPEC.md SS29.3, SS11.1, SS12.1, SS12.2). Phase plan test list maps 1:1 to T-GO3-01 through T-GO3-16. |
| M2 | Negative Tests | PASS | T-GO3-05 (cancellation), T-GO3-06 (session error), T-GO3-14 (silent cancel), T-GO3-16 (biometric rejection). 4 negative tests. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. Google tokens never stored locally (T-GO3-15 verifies Keychain + UserDefaults). OAuth flow requires JWT auth on authorize endpoint. CSRF state verified on callback. |
| M4 | Determinism | PASS | No wall-clock, no network, no randomness in tests. All use protocol-injected mocks. |
| M5 | Implementation Completeness | PASS | All deliverables present: GoogleAuthService, SettingsViewModel, SettingsView, MainTabView edit, Info.plist URL scheme, NoaApp wiring, ContentView threading. No TODO/FIXME/HACK. |
| M5b | Findings Currency | PASS | GO3 does not resolve any existing findings. No update needed. |
| M6 | No Silent Error Swallowing | PASS | No bare except. SettingsViewModel catch blocks distinguish cancelled vs failed vs generic. WebAuthError.cancelled and BiometricError.userCancelled are intentionally silent (documented in spec). |
| M7 | Wiring Completeness | PASS | NoaApp.swift creates GoogleAuthService (line 67-69) and SettingsViewModel (line 85-88). ContentView threads settingsViewModel to MainTabView. MainTabView conditionally renders SettingsView. Settings tab wired at tag 2. |
| M8 | Domain Isolation | PASS | N/A for pure iOS package. No cross-domain imports. |
| M8b | Cross-Language Field Optionality | PASS | `GoogleStatusResponse.scopes` is `[String]?` matching backend's optional list. `GoogleAuthorizeResponse.authUrl` is required matching backend's always-present `auth_url`. `GoogleDisconnectResponse.disconnected` is required matching backend's always-present `disconnected`. |
| S1 | Error Handling & Boundaries | PASS | Invalid auth URL handled (line 179, throws WebAuthError.failed). Error messages are user-facing ("Connection failed. Please try again."). |
| S2 | Code Consistency | PASS | Actor pattern (GoogleAuthService) matches existing services (ApprovalService, DeviceService). @Observable ViewModel pattern matches existing VMs. Protocol-injected mocks follow project conventions. |
| S3 | Migration & Rollback | PASS | N/A -- no DB changes. |
| S4 | Documentation | PASS | All public types and methods have doc comments. CodingKeys documented. Flow documented in header comment. |
| S5 | Integration Smoke Test | OPEN | All 16 tests use mocks. No non-mocked integration test. However, this is consistent with the iOS package pattern -- real ASWebAuthenticationSession requires a device. The wiring is verified by NoaApp.swift compilation. |

## Test Plan Coverage
No prior test plan existed for GO3. The implementation covers all 15 test specifications from the phase plan plus one additional test (T-GO3-16: biometric cancellation).

## Spec Compliance

| Spec Requirement | Status | Evidence |
|-----------------|--------|---------|
| SPEC.md SS29.3: OAuth2 via ASWebAuthenticationSession | PASS | GoogleAuthService.connect() uses WebAuthSessionProviding protocol wrapping ASWebAuthenticationSession |
| SPEC.md SS11.1: Credentials in Postgres only | PASS | T-GO3-15 verifies no Keychain/UserDefaults storage. Backend persists tokens. |
| SPEC.md SS12.1, SS12.2: Calendar + Gmail scopes | PASS | Backend authorize endpoint includes both scope sets |
| Phase plan: `noaapp://` callback scheme | PASS | T-GO3-03 verifies. Info.plist registers scheme. |
| Phase plan: Biometric guard on connect | PASS | SettingsViewModel checks biometricService before connect. T-GO3-16 verifies biometric cancel path. |
| Phase plan: Disconnect confirmation sheet | PASS | SettingsView has .alert for disconnect confirmation |
| Phase plan: Loading state during requests | PASS | T-GO3-11 verifies isLoading toggle |
| Phase plan: Status on view appear | PASS | SettingsView .onAppear calls loadStatus() |

## Test Coverage
- **GoogleAuthService (actor):** 9 tests covering connect (authorize + session), disconnect, getStatus (connected/disconnected), cancellation, session error
- **SettingsViewModel:** 7 tests covering loadStatus, isLoading, connectGoogle success, disconnectGoogle success, cancellation ignored, biometric cancel ignored, token storage verification

**Gaps (non-blocking):**
1. No test for `loadStatus()` failure path (backend error sets errorMessage)
2. No test for `disconnectGoogle()` failure path (backend error sets errorMessage)
3. No test for `connectGoogle()` generic error (non-cancellation, non-biometric)
4. No backend test for `platform=ios` redirect to `noaapp://` (pre-existing gap from GO1)

## Anti-Pattern Scan Results

**M6: Bare except blocks** -- None found in GO3 Swift files.

**M7: Wiring** -- Verified:
- `NoaApp.swift:67-69` creates `GoogleAuthService(apiClient: client, webAuthSession: ASWebAuthSessionAdapter())`
- `NoaApp.swift:85-88` creates `SettingsViewModel(googleAuthService: googleAuth, biometricService: bio)`
- `ContentView.swift:9` accepts `settingsViewModel`
- `ContentView.swift:18` passes to `MainTabView`
- `MainTabView.swift:104-105` renders `SettingsView` when `settingsViewModel` is non-nil

**M8: Domain isolation** -- N/A for iOS package.

## Smoke Test Results
```
swift test --filter GoogleAuthServiceTests: 9 tests, 0 failures
swift test --filter SettingsViewModelTests: 7 tests, 0 failures
Full suite: 204 XCTest + 12 swift-testing = 216 total, 0 failures
Backend GO1 tests: 28 passed (via docker exec)
```

## Security

1. **No local token storage** -- Google tokens are never written to Keychain or UserDefaults (verified by T-GO3-15 with actual SecItemCopyMatching check).
2. **CSRF protection** -- Backend uses server-side state token for OAuth callback verification.
3. **JWT auth required** -- authorize and status endpoints require authentication.
4. **`prefersEphemeralWebBrowserSession = false`** -- Shares cookies with Safari. This is intentional for UX (user stays logged into Google). Acceptable for a personal assistant app.
5. **Info.plist URL scheme** -- `noaapp` registered correctly. No risk of scheme hijacking since this is a personal-use app.
6. **`NSAllowsLocalNetworking` + HTTP exception for `100.106.15.98`** -- Pre-existing from earlier phases, development-only. Not a GO3 concern.

## Code Quality

1. **Actor isolation** -- GoogleAuthService is correctly an actor. Properties are private. Protocol-injected dependencies follow existing patterns.
2. **`nonisolated(unsafe)` on mock properties** -- Consistent with project pattern for serial test execution. Documented in MEMORY.md as acceptable.
3. **`_VoidResponse`-like pattern** -- `GoogleDisconnectResponse` is a private struct similar to `_VoidResponse` in other services. Minor duplication, consistent with project pattern.
4. **Conditional compilation** -- `ASWebAuthSessionAdapter` correctly gated behind `!os(macOS)` since it uses UIKit APIs.
5. **MainTabView `settingsViewModel` is optional** -- Good backwards compatibility. Existing callers (tests) don't break.

## Beyond the Test Plan

1. **`connect()` does not call `getStatus()` after success** -- The service's `connect()` method just opens the session and returns. The ViewModel's `connectGoogle()` calls `getStatus()` after `connect()`. If `getStatus()` fails after a successful connect, the user sees an error despite being connected. This is a minor UX edge case, not a spec violation.

2. **Backend `platform=ios` redirect is untested** -- The `_seed_state` helper accepts `platform` but no backend test verifies the `noaapp://` redirect. This is a pre-existing gap from GO1. The code at `auth.py:507-509` is straightforward. Non-blocking.

3. **In-memory `_oauth_states` dict is not bounded** -- If many authorize requests are made without completing callbacks, the dict grows unbounded. Single-user system mitigates this. Non-blocking for personal use.

4. **No timeout on ASWebAuthenticationSession** -- If the user starts OAuth but never completes it, the session hangs indefinitely. This is standard iOS behavior -- the system handles this by allowing the user to dismiss the sheet. Non-blocking.

## Blocking Issues (FAIL only)
N/A -- no blocking issues.

## Notes (PASS_WITH_NOTES only)
1. **S5 open:** No non-mocked integration test. This is inherent to the iOS testing model (ASWebAuthenticationSession requires a real device). The wiring is verified by NoaApp.swift compilation and ContentView pass-through. Consider adding a PR6-style live backend test for the status endpoint.
2. **Missing ViewModel error-path tests:** `loadStatus()` failure, `disconnectGoogle()` failure, and generic `connectGoogle()` error are untested at the ViewModel layer. The error handling code exists and is well-structured, but these paths have zero coverage. Low risk since the patterns are simple (set errorMessage, set isLoading=false).
3. **Backend `platform=ios` redirect untested:** The `noaapp://` redirect path in `auth.py:507-509` has no backend test. Consider adding a test in `test_go1_oauth_backend.py` that calls `_seed_state(user_id, platform="ios")` and verifies the redirect URL starts with `noaapp://`.

## Decision Review
No decisions needed. The implementation is clean, well-structured, and follows existing patterns. The phase delivers everything specified in the plan.
