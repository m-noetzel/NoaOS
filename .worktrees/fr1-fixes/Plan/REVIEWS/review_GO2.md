# QA Review: Phase GO2

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 9/9 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Test file header cites SPEC.md sections 12.1, 12.2, 29.2 and Phase GO2. All 12 planned tests present plus 3 extras. |
| M2 | Negative Tests | PASS | GoogleCallback error paths tested (access_denied, generic server_error). Disconnect-only-when-connected verified. |
| M3 | Security Boundaries | PASS | No localStorage, no hardcoded secrets, no dangerouslySetInnerHTML. Error param rendered as React text (auto-escaped). Credentials managed via httpOnly cookies (apiRequest uses `credentials: "include"`). |
| M4 | Determinism | PASS | Timer-based redirect test uses vi.useFakeTimers(). No wall-clock, network, or random dependencies. |
| M5 | Implementation Completeness | PASS | All 4 files from phase plan present and functional: Settings.tsx (Google section), GoogleCallback.tsx, App.tsx (route), test file. |
| M5b | Findings Currency | PASS | No findings resolved or created by this phase. |
| M6 | No Silent Error Swallowing | PASS | handleConnect catch block shows toast with error message. disconnectMutation onError shows toast. No silent swallowing. |
| M7 | Wiring Completeness | PASS | Route `/auth/google/callback` added to App.tsx (line 72). GoogleAuthSection rendered inside Settings page (line 384). Backend routes confirmed in auth_router (GO1). |
| M8 | Domain Isolation | PASS | Frontend-only phase. No cross-domain imports. No Python changes. |
| M8b | Cross-Language Field Optionality | PASS | GoogleStatus interface matches backend response exactly: `{connected: boolean, scopes: string[]}`. No optional field mismatches. |
| S1 | Error Handling & Boundaries | PASS | Empty scopes handled (conditional render). Loading states for both connect and disconnect. Error toast messages are descriptive. |
| S2 | Code Consistency | PASS | Follows existing Settings page patterns (useQuery, useMutation, Card components). Naming consistent with codebase. |
| S3 | Migration & Rollback | N/A | No DB or config changes. |
| S4 | Documentation | PASS | GoogleCallback.tsx has JSDoc header explaining the flow. GoogleAuthSection is self-documenting. |
| S5 | Integration Smoke Test | OPEN | All 15 tests use mocked apiRequest. No non-mocked integration test exists. For a frontend-only phase this is acceptable (real integration would require a running backend), but noted. |

## Test Plan Coverage
No test plan was generated for GO2 (test-plan mode was not run). The phase plan specified 12 tests; 15 were delivered. All 12 planned scenarios are covered. Additional tests: scope display, countdown display, generic error code rendering.

## Spec Compliance
| Spec Requirement | Status |
|-----------------|--------|
| SPEC.md 12.1 (Calendar OAuth2) -- web UI connect | PASS: Connect button calls authorize endpoint |
| SPEC.md 12.2 (Gmail OAuth2) -- web UI connect | PASS: Same flow (combined OAuth) |
| SPEC.md 29.2 (Web UI) -- settings page | PASS: Google section integrated into Settings page |
| Phase plan: status badge | PASS: Green dot + "Connected" / gray dot + "Not connected" |
| Phase plan: connect button | PASS: Calls /authorize, redirects to auth_url |
| Phase plan: disconnect button | PASS: DELETE /disconnect, cache invalidation |
| Phase plan: GoogleCallback page | PASS: Success/error/processing states, 2s redirect |
| Phase plan: route wiring | PASS: /auth/google/callback unprotected (correct) |

## Test Coverage
| Test | Spec Requirement |
|------|-----------------|
| renders 'Not connected' | Status display |
| renders 'Connected' badge | Status display |
| shows scopes when connected | Status display (extra) |
| Connect Google button calls authorize | Connect flow |
| Connect Google shows loading state | UX feedback |
| Disconnect button calls disconnect | Disconnect flow |
| Disconnect only shown when connected | UI state |
| after disconnect, status refreshes | State refresh |
| Settings Google section in layout | Integration |
| GoogleCallback success message | Callback success |
| GoogleCallback access_denied error | Callback error |
| GoogleCallback redirects after 2s | Auto-redirect |
| Countdown in redirect | UX feedback (extra) |
| Generic error for unknown codes | Error handling (extra) |
| Route renders GoogleCallback | Wiring |

**Gap:** No test for `handleConnect` failure path (authorize API rejects or returns no auth_url). The code handles this (lines 59-74 of Settings.tsx) but it's untested. Low risk since the error toast paths are straightforward.

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- No Python changes in this phase. Pre-existing `auth.py:243` `except Exception:` (noqa'd, GO1 scope).

**M7: Wiring:**
- `app.include_router(auth_router)` in app.py:431 -- Google OAuth routes are part of auth_router (confirmed).
- `/auth/google/callback` route in App.tsx:72 -- confirmed.
- `<GoogleAuthSection />` rendered in Settings page at line 384 -- confirmed.

**M8: Domain isolation:**
- No cross-domain imports found (`grep from noa.private_worker` in external_worker: clean; vice versa: clean).

## Smoke Test Results

```
15/15 tests passing in web/src/test/go2-google-connect.test.tsx (291ms)
```

One jsdom stderr warning: `Not implemented: navigation (except hash changes)` -- expected when `window.location.href` is set during the loading-state test. Does not affect test correctness.

## Security

1. **No XSS risk in GoogleCallback:** The `errorParam` from URL is rendered as React text content (line 66: `{errorParam}`), not as HTML. React auto-escapes text nodes. No `dangerouslySetInnerHTML` anywhere in either file.

2. **No token/secret exposure:** No localStorage usage. No hardcoded credentials. API calls use `credentials: "include"` for httpOnly cookies.

3. **Unprotected callback route is correct:** `/auth/google/callback` is intentionally outside `ProtectedRoute` because the browser arrives here via Google redirect, potentially without an active session. The page performs no authenticated API calls -- it only displays a message and redirects to `/settings` (which IS protected).

4. **Open redirect risk: none.** The redirect target is hardcoded to `/settings` (GoogleCallback.tsx line 37). No user-controlled redirect destination.

5. **Error param social engineering (very low risk):** An attacker could craft a URL like `/auth/google/callback?error=please+enter+your+password+at+evil.com`. Since Noa is single-user, this is negligible. React escapes the text, so no code execution.

## Code Quality

- Clean, well-structured React code following existing patterns.
- Proper use of react-query (useQuery for status, useMutation for disconnect).
- useCallback for handleConnect prevents unnecessary re-renders.
- Cleanup in useEffect (clearInterval + clearTimeout) in GoogleCallback.
- The `eslint-disable-line react-hooks/exhaustive-deps` on Settings line 168 is intentional -- the effect should run once on mount when `?google=connected` is in the URL.

## Beyond the Test Plan

1. **Missing test: authorize endpoint failure.** If `apiRequest("/api/v1/auth/google/authorize")` throws or returns no `auth_url`, the code handles it (toast + reset isConnecting) but no test exercises this path. Low severity since error handling is simple.

2. **GoogleCallback countdown can go negative.** The interval decrements every 1s and the timeout navigates after 2s. If the navigation is delayed (React re-render timing), the countdown could show "0s" or "-1s" briefly. Cosmetic only.

3. **The `?google=connected` param cleanup in Settings uses `useEffect([], ...)` with empty deps.** If the component re-mounts (e.g., due to parent layout changes), the toast won't fire again because the param was already cleaned. This is correct behavior.

4. **No test for the "Processing..." state in GoogleCallback** (when neither `?google=connected` nor `?error=` is present). The code handles it (lines 71-78) but it's not tested. Minor gap.

## Notes (PASS_WITH_NOTES)

1. **No integration test (S5 open):** All tests mock `apiRequest`. This is standard for frontend phases but means the real Settings-to-backend flow is untested. The existing Playwright E2E tests (PW3) cover Settings page navigation but not Google OAuth flow.

2. **Untested error paths in handleConnect:** The authorize failure path (catch block at line 67) and the missing auth_url path (line 59) are both untested. Consider adding a test where `apiRequest` rejects to verify the toast and state reset.

3. **GoogleCallback "Processing..." state untested:** When visiting `/auth/google/callback` with no query params, the "Processing..." fallback UI renders but has no test coverage.

## Decision Review
No architectural decisions or trade-offs requiring human input. The implementation matches the phase plan exactly with additional polish (3 extra tests, countdown display, generic error handling).
