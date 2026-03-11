# Test Plan: Phase iOS11 — Integration Tests & Polish

**Date:** 2026-03-10
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §5.1-5.4 (auth), §22.2 (SSE/chat), §25.3 (API envelope), §29.3 (mobile access), §29.4 (connection security), §29.5 (push), §29.6 (approval flow), §36 Build Phase 3

## Summary

iOS11 is the final iOS phase, delivering end-to-end integration tests that exercise real service wiring (not just mocked protocols), plus accessibility, dark mode, and error/empty state views. The critical testing risk is that all 139 prior Swift tests inject mocks at every boundary -- no test has ever verified that `AuthService -> APIClient -> URLSession -> response -> Keychain` works as a connected chain. This phase must prove the components actually compose correctly, not just that they pass in isolation (the RC1/RC3 failure pattern from the project audit).

A secondary risk is that the "polish" deliverables (ErrorView, EmptyStateView, accessibility labels) are easy to ship as skeleton views that are never wired into real screens, repeating the orphaned-code anti-pattern (L10).

## Test Specifications

### MUST-HAVE Tests

#### T1: test_login_flow_end_to_end
- **Spec ref:** SPEC.md §5.1-5.4, §25.3
- **Category:** Integration
- **Setup:** MockURLProtocol configured to return valid login response (envelope: `{ok: true, data: {access_token, refresh_token, expires_in}, trace_id}`). AuthService created with real APIClient pointing at mock session. Real KeychainService namespace (test-specific, cleaned up in tearDown).
- **Action:** Call `authService.login(username:password:)`. Then read tokens from Keychain.
- **Expected:** (1) The URLRequest sent to MockURLProtocol hits `/api/v1/auth/login` with POST method. (2) Request body contains `email`, `password`, `device_id` fields. (3) After login returns, `KeychainService.read(service:account:"access_token")` returns the mock token string. (4) `authService.accessToken()` returns the same token.
- **Why:** This is the first test that verifies AuthService + APIClient + KeychainService work together without any protocol mocks. If this fails, no authenticated flow works on a real device.

#### T2: test_login_flow_invalid_credentials
- **Spec ref:** SPEC.md §5.1, §25.3
- **Category:** Integration (negative)
- **Setup:** MockURLProtocol returns 401 with error envelope `{ok: false, error: {code: "AUTH_INVALID_CREDENTIALS", message: "..."}}`.
- **Action:** Call `authService.login(username:password:)`.
- **Expected:** (1) Throws `APIError.unauthorized`. (2) Keychain contains NO tokens (nothing stored on failure). (3) `authService.accessToken()` returns `nil`.
- **Why:** Verifies that failed auth does not leave stale tokens. iOS4 review noted `AuthService.refresh()` does NOT call `clearTokens()` on failure -- this test catches similar regressions in the login path.

#### T3: test_token_refresh_on_401_during_request
- **Spec ref:** SPEC.md §29.3, §25.4
- **Category:** Integration
- **Setup:** MockURLProtocol handler: first call returns 401, second call (refresh) returns new tokens, third call (retry) returns success data. AuthService pre-populated with valid refresh token in Keychain.
- **Action:** Call `apiClient.request("/api/v1/threads", method: "GET", body: nil)` to trigger a data fetch.
- **Expected:** (1) Three URLRequests are made in order: original, refresh POST, retry. (2) The retry request contains the new Bearer token. (3) The final return value is the decoded thread list. (4) Keychain now contains the new access token from the refresh response.
- **Why:** The auto-refresh-on-401 flow is the most critical integration path in the networking stack. All prior tests mock TokenProviding, so the real refresh -> store -> retry chain has never been tested.

#### T4: test_chat_sse_streaming_end_to_end
- **Spec ref:** SPEC.md §22.2, §29.2
- **Category:** Integration
- **Setup:** MockURLProtocol configured to return SSE stream data: `data: {"event_type":"meta","payload":{"run_id":"r1","thread_id":"t1"}}\n\n`, followed by multiple `token_stream` events, then `result_ready` with `{"response":"Hello world"}`.
- **Action:** Create real ChatService with real APIClient (mock session). Call `sendMessage(ChatRequest(...))`, iterate the full stream, collect all events.
- **Expected:** (1) First event is type `.meta` with run_id and thread_id. (2) Intermediate events are `.tokenStream` with individual tokens. (3) Final event is `.resultReady` with the full response text. (4) No errors thrown during iteration.
- **Why:** SSE streaming is the core user experience. ChatService creates its own URLSession (not the injected one) for SSE -- this is a known integration gap. The MockURLProtocol must intercept that session too, or the test proves nothing.

**CRITICAL NOTE FOR IMPLEMENTER:** ChatService.sendMessage() creates a SEPARATE URLSession internally (line 70-71 of ChatService.swift). The MockURLProtocol must be registered on URLSessionConfiguration.default or the ChatService must accept an injected session/configuration for this test to actually intercept SSE traffic. If the test passes by mocking ChatService itself, it is NOT an integration test.

#### T5: test_chat_sse_malformed_event_surfaces_error
- **Spec ref:** SPEC.md §22.2
- **Category:** Integration (negative)
- **Setup:** MockURLProtocol returns SSE stream with one valid meta event followed by invalid JSON (`data: {not-json}\n\n`).
- **Action:** Iterate the stream from `sendMessage()`.
- **Expected:** (1) First event is received correctly. (2) Stream terminates with a thrown DecodingError (not silently swallowed). (3) Per iOS5 cycle 1 fix, `try?` is NOT used on SSE decode.
- **Why:** iOS5 cycle 1 found that `try?` on SSE decode silently dropped events. This test pins the fix -- malformed events must surface as errors.

#### T6: test_approval_high_risk_biometric_gate_end_to_end
- **Spec ref:** SPEC.md §29.3 item 4, §29.6
- **Category:** Integration
- **Setup:** Real ApprovalDetailViewModel with real ApprovalService (backed by mock session). Mock BiometricAuthenticating that succeeds. High-risk approval object.
- **Action:** Call `viewModel.decide(.approved)`.
- **Expected:** (1) `biometric.authenticate(reason:)` is called BEFORE the API request. (2) A POST request is made to `/api/v1/approvals/{id}/decide` with body `{"decision":"approved"}`. (3) `viewModel.isDone == true`. (4) `viewModel.errorMessage == nil`.
- **Why:** Verifies the full chain: ViewModel -> biometric gate -> ApprovalService -> APIClient -> server. Prior tests mocked the service entirely.

#### T7: test_approval_high_risk_biometric_failure_blocks_api_call
- **Spec ref:** SPEC.md §29.3 item 4
- **Category:** Integration (negative)
- **Setup:** Same as T6 but mock biometric throws `BiometricError.authenticationFailed`.
- **Action:** Call `viewModel.decide(.approved)`.
- **Expected:** (1) NO API request is made (MockURLProtocol handler is never called). (2) `viewModel.errorMessage` is non-nil and contains "Authentication failed". (3) `viewModel.isDone == false`.
- **Why:** Ensures the biometric gate actually prevents the API call, not just sets an error after the fact.

#### T8: test_offline_queue_drain_end_to_end
- **Spec ref:** SPEC.md §29.3 item 6, §25.4
- **Category:** Integration
- **Setup:** OfflineQueueService with a temp file URL. Enqueue 3 QueuedRequests with different endpoints. Create a mock executor that tracks which requests it receives.
- **Action:** Call `queue.drain(executor:)`.
- **Expected:** (1) Executor is called 3 times in FIFO order (endpoints match enqueue order). (2) After drain, `queue.count == 0`. (3) Each request's idempotency key is preserved through the drain cycle. (4) The file is updated after drain (persisted state reflects empty queue).
- **Why:** Tests the full queue lifecycle: enqueue -> persist -> drain -> dequeue -> persist. Prior tests tested enqueue and drain separately.

#### T9: test_offline_queue_drain_partial_failure
- **Spec ref:** SPEC.md §29.3 item 6
- **Category:** Integration (negative)
- **Setup:** Enqueue 3 requests. Executor succeeds for request 1, throws for request 2, succeeds for request 3.
- **Action:** Call `queue.drain(executor:)`.
- **Expected:** (1) Request 1 is removed from queue. (2) Request 2 is re-appended with retryCount=1. (3) Request 3 is removed. (4) Final queue count is 1 (the failed request). (5) The failed request's idempotency key is unchanged.
- **Why:** Partial failure during drain is the realistic production scenario. Tests that all items get a chance and failed items are correctly re-queued.

#### T10: test_logout_clears_tokens_and_state
- **Spec ref:** SPEC.md §5.4, §29.3
- **Category:** Integration
- **Setup:** AuthService with tokens already stored in Keychain. AuthViewModel initialized (isAuthenticated=true). MockURLProtocol accepts the logout POST.
- **Action:** Call `authViewModel.logout()`.
- **Expected:** (1) A POST is made to `/api/v1/auth/logout`. (2) `authViewModel.isAuthenticated == false`. (3) Keychain contains no access_token or refresh_token for the test namespace. (4) `authViewModel.tokenExpiresAt == nil`.
- **Why:** Logout must clear ALL state. iOS4 review confirmed logout uses `try?` for server call + unconditional `clearTokens()`, but no integration test ever verified the full chain.

#### T11: test_error_view_renders_message_and_retry
- **Spec ref:** PLAN iOS11 deliverable 5
- **Category:** Behavioral
- **Setup:** Instantiate ErrorView with a title, message, and retry action closure.
- **Action:** Verify the view can be constructed and its properties are accessible.
- **Expected:** (1) ErrorView accepts title: String, message: String, retryAction: (() -> Void)?. (2) The view body does not crash on construction. (3) If retryAction is nil, no retry button is shown (or it is hidden).
- **Why:** ErrorView is a deliverable. If it cannot be constructed or crashes, the phase is incomplete (M5).

#### T12: test_empty_state_view_renders_icon_and_message
- **Spec ref:** PLAN iOS11 deliverable 5
- **Category:** Behavioral
- **Setup:** Instantiate EmptyStateView with a system image name and message.
- **Action:** Verify the view can be constructed.
- **Expected:** (1) EmptyStateView accepts systemImage: String, title: String, message: String. (2) The view body does not crash.
- **Why:** EmptyStateView is a deliverable. Must not be an empty file or stub.

#### T13: test_mock_url_protocol_intercepts_all_methods
- **Spec ref:** PLAN iOS11 deliverable 1
- **Category:** Behavioral
- **Setup:** Register MockURLProtocol on a URLSessionConfiguration. Set handler to echo back the request method.
- **Action:** Send GET, POST, PUT, DELETE requests through the session.
- **Expected:** All four requests are intercepted. Handler receives correct method for each. No requests leak to the real network.
- **Why:** MockURLProtocol is the foundation of all integration tests in this phase. If it fails to intercept certain methods, downstream tests are unreliable.

#### T14: test_mock_url_protocol_preserves_request_body
- **Spec ref:** PLAN iOS11 deliverable 1
- **Category:** Behavioral
- **Setup:** Register MockURLProtocol. Set handler to capture request body.
- **Action:** Send a POST with a JSON body through the mock session.
- **Expected:** Handler receives the full JSON body. Body is not nil or empty. Decoded body matches the sent payload. Note: URLSession may move httpBody to httpBodyStream -- the protocol must handle both (as the existing MockURLProtocol in APIClientTests.swift does).
- **Why:** Body inspection is essential for verifying login, chat, and approval request payloads in integration tests.

### NICE-TO-HAVE Tests

#### T15: test_accessibility_labels_on_login_view
- **Spec ref:** PLAN iOS11 deliverable 3
- **Category:** Behavioral
- **Setup:** Instantiate LoginView with a mock AuthViewModel.
- **Action:** Inspect the view hierarchy (or use ViewInspector if available) for accessibility labels.
- **Expected:** Email field has `.accessibilityLabel("Email")`. Password field has `.accessibilityLabel("Password")`. Sign In button has `.accessibilityLabel("Sign In")`.
- **Why:** VoiceOver users need labeled controls. Without tooling like ViewInspector, this may need to be verified manually; a programmatic test that at minimum verifies the view constructs without crash is acceptable.

#### T16: test_accessibility_labels_on_approval_list
- **Spec ref:** PLAN iOS11 deliverable 3
- **Category:** Behavioral
- **Setup:** Instantiate ApprovalListView with mock dependencies and a populated approvals list.
- **Action:** Verify each approval row has an accessible description including the risk tier and domain.
- **Expected:** Approval row accessibilityLabel contains the risk tier (e.g., "high") and domain for VoiceOver.
- **Why:** Approvals are security-critical -- VoiceOver users must understand risk tier before deciding.

#### T17: test_error_view_used_in_chat_error_state
- **Spec ref:** PLAN iOS11 deliverable 5, L10 (wiring completeness)
- **Category:** Integration
- **Setup:** ChatViewModel with errorMessage set to a non-nil value.
- **Action:** Verify that the error state in ChatView references ErrorView (not an inline Text).
- **Expected:** ErrorView is actually used in at least one production view. It is not orphaned code.
- **Why:** Catches the "orphaned utility" anti-pattern (QC8 A5/A4). A view that exists in Shared/ but is never imported by any screen is dead code.

#### T18: test_empty_state_view_used_in_thread_list
- **Spec ref:** PLAN iOS11 deliverable 5, L10
- **Category:** Integration
- **Setup:** ThreadListView with empty threads array.
- **Action:** Verify that EmptyStateView is rendered (or at minimum, imported and used) in the empty-threads state.
- **Expected:** EmptyStateView appears in the ThreadListView body when `viewModel.threads.isEmpty`.
- **Why:** Same as T17 -- wiring completeness.

#### T19: test_offline_queue_drain_max_retries_discards
- **Spec ref:** SPEC.md §29.3 item 6
- **Category:** Behavioral (edge case)
- **Setup:** Enqueue a request. Call `markFailed(id:)` 5 times (maxRetries=5).
- **Action:** Check `queue.count` after the 5th markFailed.
- **Expected:** Queue is empty -- the item was discarded after reaching maxRetries. This test exists in iOS9 unit tests but should be re-verified in the integration context with a real file-backed queue.
- **Why:** Ensures the discard logic works with file persistence, not just in-memory state.

#### T20: test_dark_mode_error_view
- **Spec ref:** PLAN iOS11 deliverable 4
- **Category:** Behavioral
- **Setup:** Render ErrorView in both `.colorScheme(.light)` and `.colorScheme(.dark)` environments.
- **Action:** Verify the view constructs without crash in both schemes.
- **Expected:** No forced colors (no hardcoded `Color.white` or `Color.black`). Uses semantic colors (e.g., `Color.primary`, `Color.secondary`, `.background`).
- **Why:** Dark mode is a deliverable. Hardcoded colors break dark mode.

#### T21: test_chat_sse_stream_cancellation
- **Spec ref:** SPEC.md §22.2
- **Category:** Integration (edge case)
- **Setup:** MockURLProtocol configured to return a slow SSE stream (many events).
- **Action:** Start `sendMessage()`, receive 2 events, then call `cancelStream()`.
- **Expected:** (1) Stream iteration stops without error. (2) No crash or hanging Task. (3) `isStreaming` becomes false.
- **Why:** iOS5 review noted `cancelStream()` exists but is never called from views. If it crashes when called, thread switching while streaming would fail.

## Security Test Requirements

1. **T2 (login failure)** -- Verify no tokens are stored on auth failure.
2. **T7 (biometric gate)** -- Verify high-risk approval API call is blocked when biometric fails.
3. **T10 (logout)** -- Verify ALL tokens are cleared from Keychain on logout.
4. **Token leakage check:** In T1 and T3, verify that tokens are stored ONLY in Keychain via `KeychainService` calls -- not in UserDefaults, files, or in-memory singletons that persist across app launches.
5. **No hardcoded tokens:** The MockURLProtocol test fixtures must use obviously-fake tokens (e.g., "test-access-token-12345"), never anything resembling a real JWT.

## Integration Test Requirements

The following must be tested WITHOUT mocking the service protocol (i.e., using real service classes with mock URLSession):

1. **Login flow (T1, T2):** Real AuthService + real APIClient + real KeychainService + MockURLProtocol
2. **Token refresh (T3):** Real APIClient + real AuthService (as TokenProviding) + MockURLProtocol
3. **Chat SSE (T4, T5):** Real ChatService + MockURLProtocol (see critical note on T4)
4. **Approval + biometric (T6, T7):** Real ApprovalDetailViewModel + real ApprovalService + real APIClient + mock BiometricAuthenticating + MockURLProtocol
5. **Offline queue drain (T8, T9):** Real OfflineQueueService with temp file

The key integration boundary being tested is: **ViewModel -> Service -> APIClient -> URLSession (mocked)**. The ONLY mock allowed is URLProtocol (network layer) and BiometricAuthenticating (hardware dependency).

## Anti-Patterns to Watch For

Based on past retros and iOS review history:

1. **"Integration test" that mocks the service protocol.** If the test injects a `MockApprovalServicing` instead of a real `ApprovalService` backed by a mock URLSession, it is a unit test, not an integration test. This defeats the entire purpose of iOS11. (RC1, RC3 from project audit.)

2. **ChatService.sendMessage() URLSession bypass.** ChatService creates its own URLSession on every call (line 70-71). MockURLProtocol registered on a test session will NOT intercept SSE traffic unless: (a) the protocol is registered on the shared session configuration, or (b) ChatService is modified to accept an injected URLSessionConfiguration. If the implementer cannot solve this, the test must document the gap explicitly -- do not ship a test that passes by coincidence.

3. **ErrorView / EmptyStateView created but never imported.** The "orphaned utility" pattern from QC8. After implementation, grep Sources/Noa/Views/ for `ErrorView` and `EmptyStateView` usage. They must appear in at least one production view file, not just in the test target.

4. **Accessibility labels added to views but never tested.** Adding `.accessibilityLabel("...")` is easy to do superficially. Without ViewInspector or snapshot tests, at minimum verify that the labels exist by inspecting source code or constructing the views.

5. **Test target path mismatch.** The phase plan says `ios/Noa/NaoTests/Integration/` but Package.swift has `path: "Tests/NaoTests"`. The integration test files must be under `Tests/NaoTests/Integration/` (relative to the package root at `ios/Noa/`), not at the absolute paths listed in the plan. If a new test target is created, it must be added to Package.swift.

6. **MockURLProtocol duplication.** `APIClientTests.swift` already has a `MockURLProtocol`. The new one in `Integration/MockURLProtocol.swift` must either replace it or have a different name to avoid symbol conflicts. Shipping two MockURLProtocol classes in the same test target will fail to compile.

7. **`nonisolated(unsafe)` proliferation.** iOS4 review flagged this on AuthViewModel. New view models (if any) should use `@MainActor` instead. Do not copy the pattern.

8. **Keychain test isolation.** Tests using real KeychainService must use a unique service namespace per test (e.g., `"com.noa.test.\(UUID())"`) and clean up in tearDown. Leaking Keychain items between test runs causes flaky failures.
