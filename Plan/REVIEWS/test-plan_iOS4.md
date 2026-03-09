# Test Plan: Phase iOS4 — Keychain Storage & Auth Flow

**Date:** 2026-03-09
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §5.1–5.4, §29.3 item 5

## Summary

iOS4 implements the iOS authentication stack: a `KeychainService` wrapping the Security framework for secure token storage, an `AuthService` that handles login/refresh/logout against the backend with Keychain persistence, an `AuthViewModel` managing observable auth state, a `LoginView` SwiftUI screen, an `AuthGuard` view modifier, and automatic token refresh on app foreground. The key testing risks are: (1) Keychain operations silently failing (OSStatus errors are easy to ignore), (2) token lifecycle gaps where tokens are stored but never cleared on error, (3) race conditions in auto-refresh on foreground, and (4) AuthService implementing `TokenProviding` correctly so it integrates with the existing `APIClient` from iOS3.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_keychain_save_and_load
- **Spec ref:** SPEC.md §5.2 (session tokens stored), §29.3 item 5 (Keychain storage)
- **Category:** Behavioral
- **Setup:** Fresh KeychainService instance (use a test-specific service name or account to avoid colliding with real Keychain items)
- **Action:** Call `save(key: "test_token", data: someData)`, then `load(key: "test_token")`
- **Expected:** `load` returns the exact bytes that were saved. No OSStatus error thrown.
- **Why:** If save/load round-trip fails, the entire auth flow is broken — tokens vanish between app launches.

#### T2: test_keychain_update_overwrites_existing
- **Spec ref:** SPEC.md §5.2, §29.3 item 5
- **Category:** Behavioral
- **Setup:** KeychainService with a pre-existing item for key "token"
- **Action:** Call `save(key: "token", data: newData)` (overwrite), then `load(key: "token")`
- **Expected:** `load` returns `newData`, not the old value. Implementation must handle `errSecDuplicateItem` by calling `SecItemUpdate` internally.
- **Why:** Token refresh replaces old tokens. If update fails silently and the old value persists, the user gets stuck with an expired token.

#### T3: test_keychain_delete_removes_item
- **Spec ref:** SPEC.md §5.4 (logout invalidates tokens)
- **Category:** Behavioral
- **Setup:** KeychainService with a saved item
- **Action:** Call `delete(key: "token")`, then `load(key: "token")`
- **Expected:** `load` returns nil (or throws a "not found" error). No crash on delete.
- **Why:** Logout must clear tokens from Keychain. If delete is a no-op, tokens survive logout.

#### T4: test_keychain_load_nonexistent_returns_nil
- **Spec ref:** §29.3 item 5
- **Category:** Negative
- **Setup:** Fresh KeychainService, no items saved
- **Action:** Call `load(key: "nonexistent")`
- **Expected:** Returns nil (not a crash, not empty data, not a thrown error)
- **Why:** First launch has no tokens. If load throws on missing items, app crashes on cold start.

#### T5: test_keychain_access_level_afterFirstUnlockThisDeviceOnly
- **Spec ref:** Phase plan deliverable 2 (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly)
- **Category:** Invariant
- **Setup:** KeychainService instance
- **Action:** Save an item, then inspect the attributes passed to SecItemAdd (via source inspection or a test wrapper that captures the query dictionary)
- **Expected:** The `kSecAttrAccessible` attribute is set to `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`
- **Why:** Using a weaker access level (e.g., `kSecAttrAccessibleAlways`) means tokens are available when the device is locked, which is a security violation. Using `kSecAttrAccessibleWhenUnlocked` means background refresh fails.

#### T6: test_auth_login_stores_tokens_in_keychain
- **Spec ref:** SPEC.md §5.3 (login returns access_token + refresh_token), §29.3 item 5
- **Category:** Integration
- **Setup:** AuthService with a mock APIClient that returns `AuthTokens(accessToken: "at", refreshToken: "rt", tokenType: "bearer", expiresIn: 900)` for POST /auth/login. Use a real (in-memory or test) KeychainService.
- **Action:** Call `authService.login(username: "user", password: "pass")`
- **Expected:** (1) Both access and refresh tokens are retrievable from Keychain after login. (2) AuthService's state reflects "authenticated". (3) The mock API received a POST to `/api/v1/auth/login` with `LoginRequest` body.
- **Why:** This is THE critical integration point — API response to Keychain storage. If tokens aren't persisted, the user is logged out on next app launch.

#### T7: test_auth_login_failure_does_not_store_tokens
- **Spec ref:** SPEC.md §5.3 (error path)
- **Category:** Negative
- **Setup:** AuthService with a mock APIClient that throws `APIError.unauthorized` for login
- **Action:** Call `authService.login(username: "bad", password: "wrong")`
- **Expected:** (1) Method throws an error (specific type, not generic). (2) Keychain contains NO tokens (no partial state). (3) AuthService state remains "unauthenticated".
- **Why:** If a failed login stores partial tokens (e.g., saves before validating response), subsequent code may treat the user as authenticated.

#### T8: test_auth_refresh_rotates_both_tokens
- **Spec ref:** SPEC.md §5.2 (rotating refresh tokens — old token invalidated on use), §5.3
- **Category:** Behavioral
- **Setup:** AuthService with mock APIClient. Pre-populate Keychain with old tokens. Mock returns new AuthTokens on refresh.
- **Action:** Call `authService.refreshTokens()` (or however the refresh is exposed)
- **Expected:** (1) Keychain now contains the NEW access and refresh tokens, not the old ones. (2) The mock received a POST to `/api/v1/auth/refresh` with `RefreshRequest(refreshToken: oldRefreshToken)`.
- **Why:** If only the access token is updated but the refresh token stays stale, the next refresh will fail (backend invalidated the old refresh token per spec §5.2).

#### T9: test_auth_refresh_failure_clears_tokens
- **Spec ref:** SPEC.md §5.2, §5.4
- **Category:** Negative
- **Setup:** AuthService with mock APIClient that throws on refresh (e.g., refresh token expired/revoked). Keychain has old tokens.
- **Action:** Call `authService.refreshTokens()`
- **Expected:** (1) Error is thrown. (2) Keychain is cleared (both tokens removed). (3) AuthService state transitions to "unauthenticated".
- **Why:** If refresh fails and old tokens remain, the app may attempt infinite refresh loops or present stale credentials. The user must be forced to re-login.

#### T10: test_auth_logout_clears_keychain_and_state
- **Spec ref:** SPEC.md §5.4 (logout invalidates all tokens for that session)
- **Category:** Behavioral
- **Setup:** AuthService with authenticated state (tokens in Keychain)
- **Action:** Call `authService.logout()`
- **Expected:** (1) Keychain contains no tokens. (2) AuthService state is "unauthenticated". (3) Mock APIClient received POST to `/api/v1/auth/logout` (best-effort — should not throw even if the network call fails).
- **Why:** Incomplete logout leaves tokens on device. If the device is compromised, tokens are usable.

#### T11: test_auth_logout_succeeds_even_when_network_fails
- **Spec ref:** SPEC.md §5.4
- **Category:** Negative
- **Setup:** AuthService with mock APIClient that throws `.networkError` on logout POST
- **Action:** Call `authService.logout()`
- **Expected:** (1) No error thrown to caller. (2) Keychain is still cleared. (3) State is "unauthenticated".
- **Why:** Logout must clear local state regardless of whether the backend is reachable. Users on a plane should still be able to log out.

#### T12: test_auth_conforms_to_token_providing
- **Spec ref:** iOS3 `TokenProviding` protocol, Phase plan deliverable 3
- **Category:** Integration
- **Setup:** AuthService with tokens stored in Keychain
- **Action:** Call `authService.accessToken()` and `authService.refreshAccessToken()` (the `TokenProviding` protocol methods)
- **Expected:** (1) `accessToken()` returns the current access token from Keychain. (2) `refreshAccessToken()` calls the backend refresh endpoint and returns the new access token. (3) AuthService can be passed as `tokenProvider` to APIClient without compiler error.
- **Why:** The entire iOS3 networking layer depends on `TokenProviding`. If AuthService doesn't conform correctly, APIClient's 401-refresh-retry loop is broken.

#### T13: test_viewmodel_state_transitions_login
- **Spec ref:** Phase plan deliverable 4 (AuthViewModel @Observable)
- **Category:** Behavioral
- **Setup:** AuthViewModel with mock AuthService
- **Action:** Call `viewModel.login(username:password:)` with valid credentials
- **Expected:** State transitions: `.unauthenticated` -> `.loading` -> `.authenticated`. No intermediate `.error` state.
- **Why:** SwiftUI views bind to this state. Wrong transitions cause UI glitches (login button disappearing while still unauthenticated, loading spinner stuck).

#### T14: test_viewmodel_login_failure_shows_error
- **Spec ref:** Phase plan test list (error display)
- **Category:** Negative
- **Setup:** AuthViewModel with mock AuthService that throws on login
- **Action:** Call `viewModel.login(username:password:)` with bad credentials
- **Expected:** State transitions to `.error(message)` where message is human-readable (not a raw Swift error dump). State does NOT transition to `.authenticated`.
- **Why:** Users need to see why login failed. If the error is swallowed, the form just stops responding.

#### T15: test_viewmodel_auto_refresh_on_foreground
- **Spec ref:** Phase plan deliverable 7 (automatic token refresh on foreground)
- **Category:** Behavioral
- **Setup:** AuthViewModel with mock AuthService. Simulate "tokens exist but access token is near expiry" (e.g., `expiresIn` was 900 seconds and current time is 800 seconds past issuance).
- **Action:** Trigger the foreground notification (call the method that `scenePhase` change would invoke)
- **Expected:** AuthService's refresh method is called. If refresh succeeds, state remains `.authenticated`.
- **Why:** Without auto-refresh, users returning to the app after 15 minutes get a 401 on their first action, which feels like a logout.

### NICE-TO-HAVE Tests

#### T16: test_keychain_save_empty_data
- **Spec ref:** Robustness
- **Category:** Edge case
- **Setup:** KeychainService
- **Action:** Call `save(key: "empty", data: Data())`
- **Expected:** Either succeeds (stores empty data, retrieves empty data) or throws a clear error. Must NOT crash.
- **Why:** Defensive edge case — empty token response from a malformed server.

#### T17: test_viewmodel_auto_refresh_skips_when_token_fresh
- **Spec ref:** Phase plan deliverable 7
- **Category:** Behavioral
- **Setup:** AuthViewModel with fresh tokens (well within expiry window)
- **Action:** Trigger foreground event
- **Expected:** AuthService's refresh method is NOT called. Avoids unnecessary network traffic.
- **Why:** Refresh on every foreground wastes bandwidth and risks hitting rate limits.

#### T18: test_keychain_concurrent_access_does_not_corrupt
- **Spec ref:** Swift 6 strict concurrency
- **Category:** Robustness
- **Setup:** KeychainService instance
- **Action:** Launch 10 concurrent tasks all calling save/load with different keys
- **Expected:** No data corruption, no crashes. Each key's value is correct.
- **Why:** Swift 6 concurrency may expose races if KeychainService is not thread-safe.

## Security Test Requirements

1. **T5** (access level): Tokens must use `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` — not a weaker level.
2. **T7** (login failure): Failed login must NOT leave tokens in Keychain.
3. **T9** (refresh failure): Failed refresh must clear stale tokens.
4. **T10/T11** (logout): Logout must always clear local tokens, even on network failure.
5. **No plaintext logging of tokens**: AuthService and KeychainService must never log token values. This should be verified by source inspection during review (not a unit test, but a review-time check).
6. **No hardcoded secrets or fallback URLs**: AuthService must not contain fallback credentials or hardcoded API keys.

## Integration Test Requirements

- **T6** (login stores tokens) is the primary integration test: it uses a real KeychainService (or in-memory equivalent) wired to AuthService, with only the network layer mocked. This tests the AuthService-to-KeychainService integration.
- **T12** (TokenProviding conformance) verifies that AuthService integrates with the existing iOS3 APIClient protocol. This is critical because APIClient's 401-retry depends on `TokenProviding`.
- At least one test must verify that AuthService can be passed to `APIClient(tokenProvider:)` and compile — this catches protocol signature mismatches at test time, not at app build time.

## Anti-Patterns to Watch For

Based on past retros and audit findings:

1. **"Wired in class, not in app" (QC5/QC8 pattern):** AuthViewModel created but never injected into `NaoApp.swift`. LoginView built but never shown via AuthGuard. The phase plan says to modify `NaoApp.swift` — verify this actually happens. If AuthGuard is not wired into the root view, the entire auth flow is unreachable.

2. **Source inspection tests instead of behavioral tests (QC2 pattern):** Tests that use `Mirror` or source inspection to verify Keychain attributes are weak. Prefer tests that actually call `SecItemCopyMatching` (or a wrapper) and verify the returned data. However, for `kSecAttrAccessible` specifically (T5), source inspection may be the only practical approach since you can't query accessibility attributes back from Keychain in tests.

3. **TokenProviding not implemented (orphaned protocol):** iOS3 defined `TokenProviding` as a protocol. If AuthService doesn't actually conform to it, APIClient has no real token provider and the 401-refresh loop is dead code in production. T12 must verify conformance.

4. **Logout clears state but not Keychain (half-fix):** A logout that sets `isAuthenticated = false` but forgets to call `KeychainService.delete()` looks correct in ViewModel tests (which mock the service) but leaks tokens on disk. T10 must use a real (or in-memory) KeychainService to catch this.

5. **Auto-refresh with no expiry tracking:** The phase plan says "refresh on foreground if access token near expiry" — but `AuthTokens.expiresIn` is seconds-from-issuance, not an absolute timestamp. AuthService must store the issuance time alongside the token to compute "near expiry." If it only stores the token string, every foreground event either always refreshes (wasteful) or never refreshes (broken). Tests T15/T17 must verify the time-based decision.

6. **`NaoTests` naming (iOS3 note):** Test target is named `NaoTests`, not `NoaTests`. Tests for iOS4 must go in the same target to be discovered by the existing test gate.

7. **Swift 6 strict concurrency:** `KeychainService` will likely be an `actor` or `final class` with `Sendable` conformance. If it's a plain class, Swift 6 will reject cross-isolation calls. Tests must compile under strict concurrency. Similarly, `AuthViewModel` with `@Observable` must be `@MainActor` to avoid data races on published state.
