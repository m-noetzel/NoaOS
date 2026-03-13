# Test Plan: Phase iOS3

**Date:** 2026-03-08
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §29.1, §29.3, §25.3, §25.4, §29.4

## Summary

iOS3 creates the entire iOS application from scratch: Xcode project, MVVM structure, `APIClient` (generic HTTP with auth injection and 401 retry), `SSEClient` (streaming line parser with reconnection backoff), shared model types mirroring the backend schemas, `DeviceID` (Keychain-persisted UUID), and `NoaEnvironment` configuration. The key testing risks are: (1) model types silently diverge from backend schemas, (2) SSE parser fails on real server output, (3) auth retry creates infinite loops, (4) DeviceID leaks across Keychain groups, (5) idempotency keys are not unique or not attached to write requests.

**Simulator target:** iPhone 17 Pro (iOS 26 / Xcode 26.3)
**Deployment target:** iOS 17.0
**Test gate:** `xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 17 Pro'`

---

## Test Specifications

### MUST-HAVE Tests

#### T1: test_api_client_get_request_decodes_api_response
- **Spec ref:** SPEC.md §25.3
- **Category:** Behavioral
- **Setup:** Mock URLProtocol returning `{"data": {...}, "meta": {"request_id":"uuid","trace_id":"uuid","timestamp":"..."}}`
- **Action:** Call `APIClient.get<SomeModel>("/api/v1/resource")`
- **Expected:** Returns decoded `ApiResponse<SomeModel>` with `.data` populated and `.meta.request_id` non-nil. The generic decoding must handle nested `data` field — not decode the top-level JSON as `T` directly.
- **Why:** If the envelope is decoded wrong, every API call silently returns nil data or crashes. §25.3 defines the exact envelope shape.

#### T2: test_api_client_post_encodes_body_as_json
- **Spec ref:** SPEC.md §25.3
- **Category:** Behavioral
- **Setup:** Mock URLProtocol that captures the outgoing request body
- **Action:** Call `APIClient.post<Response>("/api/v1/resource", body: someEncodable)`
- **Expected:** Request body is valid JSON matching the Encodable. Content-Type header is `application/json`.
- **Why:** Malformed request bodies cause silent 422 errors from the backend.

#### T3: test_api_client_injects_auth_header
- **Spec ref:** SPEC.md §29.3 (Keychain for session tokens)
- **Category:** Security / Behavioral
- **Setup:** Mock URLProtocol; configure APIClient with a token provider that returns "test-token"
- **Action:** Call any authenticated endpoint
- **Expected:** Request includes `Authorization: Bearer test-token` header
- **Why:** Without auth injection, every request returns 401. This is the foundation of all authenticated communication.

#### T4: test_api_client_401_triggers_token_refresh_and_retry
- **Spec ref:** SPEC.md §29.3 (token refresh lifecycle)
- **Category:** Behavioral
- **Setup:** Mock URLProtocol returns 401 on first call, 200 on second call. Mock token refresh delegate.
- **Action:** Call an authenticated endpoint
- **Expected:** (1) Token refresh delegate is called exactly once, (2) original request is retried with new token, (3) final result is the 200 response. Must NOT retry more than once (no infinite loop).
- **Why:** Without this, any expired token kills the session. Infinite retry loops would freeze the app.

#### T5: test_api_client_401_retry_does_not_loop_on_repeated_401
- **Spec ref:** PLAN Phase iOS3
- **Category:** Invariant (safety)
- **Setup:** Mock URLProtocol always returns 401. Mock token refresh that returns a new (but still invalid) token.
- **Action:** Call an authenticated endpoint
- **Expected:** After exactly 1 refresh attempt and 1 retry, the client surfaces the 401 error to the caller. Does NOT attempt a second refresh.
- **Why:** A buggy refresh flow can cause infinite 401 -> refresh -> 401 loops, freezing the app and hammering the server.

#### T6: test_api_client_429_rate_limit_handling
- **Spec ref:** PLAN Phase iOS3 (429 handling listed in deliverables)
- **Category:** Behavioral
- **Setup:** Mock URLProtocol returns 429 with `Retry-After: 2` header
- **Action:** Call any endpoint
- **Expected:** Client either (a) waits and retries after the Retry-After interval, or (b) surfaces a specific rate-limit error to the caller. Must not silently drop the request.
- **Why:** Without 429 handling, bursts of requests during reconnection flood the server.

#### T7: test_api_client_network_error_returns_typed_error
- **Spec ref:** PLAN Phase iOS3
- **Category:** Negative
- **Setup:** Mock URLProtocol throws `URLError(.notConnectedToInternet)`
- **Action:** Call any endpoint
- **Expected:** Returns a typed error (e.g., `.networkError(underlying:)`) — not a generic `Error` or crash. The error must be distinguishable from a server error.
- **Why:** The app needs to show "No connection" vs "Server error" — different user-facing messages. Generic errors make this impossible.

#### T8: test_api_client_idempotency_key_attached_to_write_requests
- **Spec ref:** SPEC.md §25.4
- **Category:** Behavioral
- **Setup:** Mock URLProtocol that captures outgoing headers
- **Action:** Call `APIClient.post(...)` (a write endpoint)
- **Expected:** Request includes `Idempotency-Key` header with a valid UUID string
- **Why:** §25.4 says "Clients must send a unique key for each distinct write operation." Missing idempotency keys cause duplicate side effects on unreliable networks.

#### T9: test_api_client_idempotency_key_unique_per_request
- **Spec ref:** SPEC.md §25.4
- **Category:** Invariant
- **Setup:** None
- **Action:** Generate two idempotency keys (e.g., two POST calls)
- **Expected:** The two keys are different UUIDs
- **Why:** If keys are reused, the server de-duplicates legitimate distinct requests.

#### T10: test_api_client_idempotency_key_not_on_get_requests
- **Spec ref:** SPEC.md §25.4 ("write endpoints")
- **Category:** Behavioral
- **Setup:** Mock URLProtocol that captures outgoing headers
- **Action:** Call `APIClient.get(...)`
- **Expected:** Request does NOT include `Idempotency-Key` header
- **Why:** GET requests are idempotent by nature. Adding the header is harmless but indicates a misunderstanding of the spec that could mask bugs elsewhere.

#### T11: test_sse_parser_data_frame
- **Spec ref:** SPEC.md §29.1 (SSE streaming)
- **Category:** Behavioral
- **Setup:** Feed the SSE parser a byte stream: `data: {"event_type":"token","payload":{"text":"hello"}}\n\n`
- **Action:** Parser processes the stream
- **Expected:** Emits exactly one event with the parsed JSON. Event type is extractable. Payload contains `text: "hello"`.
- **Why:** This is the fundamental SSE parsing operation. If it fails, the chat UI shows nothing.

#### T12: test_sse_parser_multiline_data
- **Spec ref:** PLAN Phase iOS3
- **Category:** Edge case
- **Setup:** Feed: `data: {"part1":\n"data: "value"}\n\n`
- **Action:** Parser processes
- **Expected:** Multi-line `data:` fields are concatenated before JSON parsing (per SSE spec, multiple `data:` lines are joined with newlines)
- **Why:** Long JSON payloads from the server may span multiple `data:` lines. Failure to concatenate causes JSON parse errors on every large response.

#### T13: test_sse_parser_ignores_comments_and_empty_lines
- **Spec ref:** SSE specification
- **Category:** Edge case
- **Setup:** Feed: `: this is a comment\n\ndata: {"ok":true}\n\n`
- **Action:** Parser processes
- **Expected:** Comment line (starting with `:`) is ignored. The `{"ok":true}` event is emitted.
- **Why:** Servers often send `:keepalive\n\n` comments. Parsing these as data corrupts the event stream.

#### T14: test_sse_parser_malformed_line_does_not_crash
- **Spec ref:** PLAN Phase iOS3 (malformed line handling)
- **Category:** Negative
- **Setup:** Feed: `garbage without colon\ndata: {"ok":true}\n\n`
- **Action:** Parser processes
- **Expected:** Malformed line is skipped (not crash). The valid event is still emitted.
- **Why:** Network corruption or server bugs can inject garbage. A crash here kills the chat session.

#### T15: test_sse_client_reconnection_backoff
- **Spec ref:** PLAN Phase iOS3 (reconnection with backoff [1s, 2s, 5s, 10s])
- **Category:** Behavioral
- **Setup:** Mock URLSession that fails connection 4 times, then succeeds
- **Action:** SSEClient connects
- **Expected:** Reconnection delays are approximately [1s, 2s, 5s, 10s]. After 4th failure, the 5th attempt succeeds and streaming resumes. Delays must be testable (injected clock or recorded timestamps).
- **Why:** Without backoff, reconnection storms flood the server. The specific intervals [1s, 2s, 5s, 10s] are in the phase plan.

#### T16: test_sse_client_reconnection_sends_last_event_id
- **Spec ref:** SPEC.md §29.3 (SSE reconnection)
- **Category:** Behavioral
- **Setup:** Mock stream delivers events with `id:` fields, then disconnects. Mock reconnection succeeds.
- **Action:** SSEClient reconnects after disconnect
- **Expected:** Reconnection request includes `Last-Event-ID` header with the last received event ID
- **Why:** Without Last-Event-ID, the client re-receives all events on reconnection, causing duplicate messages in the UI. This is a known anti-pattern from the web client (see MEMORY: "SSE Last-Event-ID pattern").

#### T17: test_model_decoding_api_response_success
- **Spec ref:** SPEC.md §25.3
- **Category:** Behavioral
- **Setup:** JSON string matching the §25.3 envelope: `{"data":{...},"meta":{"request_id":"...","trace_id":"...","timestamp":"..."}}`
- **Action:** Decode as `ApiResponse<SomeModel>`
- **Expected:** All fields populated. `meta.request_id` is a valid UUID string. `meta.timestamp` is ISO8601.
- **Why:** If the response envelope struct doesn't match the backend's JSON shape, all API calls fail silently.

#### T18: test_model_decoding_api_response_error
- **Spec ref:** SPEC.md §25.3
- **Category:** Negative
- **Setup:** JSON: `{"data":null,"error":{"code":"AUTH_TOKEN_EXPIRED","message":"Access token has expired","details":{}},"meta":{...}}`
- **Action:** Decode as `ApiResponse<SomeModel>`
- **Expected:** `.data` is nil, `.error` is populated with `.error.code == "AUTH_TOKEN_EXPIRED"` and `.error.message` non-empty
- **Why:** If error responses can't be decoded, the app can't display error messages or handle specific error codes (like triggering refresh on AUTH_TOKEN_EXPIRED).

#### T19: test_model_decoding_thread
- **Spec ref:** SPEC.md §29.1, backend schema
- **Category:** Behavioral
- **Setup:** JSON matching backend Thread schema (id, title, created_at, updated_at, etc.)
- **Action:** Decode as `Thread`
- **Expected:** All fields populated. Date fields are Date objects. UUID fields are UUID objects (or strings, consistently).
- **Why:** Schema mismatch between iOS model and backend JSON is the #1 cause of silent data loss in mobile apps.

#### T20: test_model_decoding_run_event
- **Spec ref:** SPEC.md §22.4 (Run/Event model)
- **Category:** Behavioral
- **Setup:** JSON matching backend RunEvent schema (id, run_id, event_type, payload, created_at)
- **Action:** Decode as `RunEvent`
- **Expected:** `event_type` decodes to an enum (token, tool_call, approval_requested, etc.). `payload` is accessible as a dictionary or typed union.
- **Why:** RunEvent is the core SSE payload. If it doesn't decode, the entire streaming UI breaks.

#### T21: test_model_decoding_approval
- **Spec ref:** SPEC.md §29.6, backend ApprovalRead schema
- **Category:** Behavioral
- **Setup:** JSON matching Approval schema (id, run_id, risk_tier, status, dry_run_preview, etc.)
- **Action:** Decode as `Approval`
- **Expected:** `risk_tier` maps to RiskTier enum. `status` maps to approval status enum.
- **Why:** Approval flow is a critical governance path. Wrong decoding means users can't approve/deny actions.

#### T22: test_device_id_generated_and_persisted
- **Spec ref:** PLAN Phase iOS3 (persistent UUID in Keychain)
- **Category:** Behavioral
- **Setup:** Clean Keychain state (no existing device ID entry)
- **Action:** Call `DeviceID.current()` twice
- **Expected:** First call generates a UUID and stores it in Keychain. Second call returns the SAME UUID (not a new one). Both return valid UUID strings.
- **Why:** Device ID is used for push token registration (iOS1). If it changes on every call, push tokens get orphaned.

#### T23: test_device_id_survives_app_reinstall_simulation
- **Spec ref:** PLAN Phase iOS3 (persistent in Keychain)
- **Category:** Integration
- **Setup:** Call `DeviceID.current()` to establish a device ID. Clear UserDefaults (simulating app reinstall — Keychain persists across reinstalls on real devices).
- **Action:** Call `DeviceID.current()` again
- **Expected:** Returns the same UUID as before (Keychain survives app deletion, unlike UserDefaults/files)
- **Why:** If DeviceID uses UserDefaults or file storage instead of Keychain, it will change on reinstall, breaking push notification registration.

#### T24: test_environment_configuration_base_url
- **Spec ref:** PLAN Phase iOS3 (NoaEnvironment configuration)
- **Category:** Behavioral
- **Setup:** None
- **Action:** Access `NoaEnvironment.development.baseURL` and `NoaEnvironment.production.baseURL`
- **Expected:** Both return valid URLs. Development URL points to a local/LAN address. Production URL is configurable (not hardcoded to localhost).
- **Why:** Wrong base URL means zero connectivity. This is the single configuration that must be correct.

#### T25: test_environment_no_hardcoded_secrets
- **Spec ref:** ARCH_INVARIANTS.md L11, M3
- **Category:** Security
- **Setup:** None
- **Action:** Inspect `NoaEnvironment` / `Environment.swift` source
- **Expected:** No hardcoded API keys, secrets, tokens, or credentials in the configuration. Only base URLs and non-sensitive settings.
- **Why:** Hardcoded secrets in iOS source are extractable from the binary.

---

### NICE-TO-HAVE Tests

#### T26: test_api_client_timeout_handling
- **Spec ref:** Robustness
- **Category:** Edge case
- **Setup:** Mock URLProtocol that never responds
- **Action:** Call any endpoint with a timeout
- **Expected:** Times out after a reasonable interval (e.g., 30s) with a typed timeout error
- **Why:** Hung requests without timeouts leak resources and block the UI.

#### T27: test_sse_parser_event_field
- **Spec ref:** SSE specification
- **Category:** Edge case
- **Setup:** Feed: `event: token\ndata: {"text":"hi"}\n\n`
- **Action:** Parser processes
- **Expected:** Event has type "token" (from the `event:` field, not from the data payload)
- **Why:** Some servers use the `event:` field for routing. Supporting it is correct per SSE spec.

#### T28: test_model_decoding_unknown_enum_value
- **Spec ref:** Forward compatibility
- **Category:** Edge case
- **Setup:** JSON with `"risk_tier": "ULTRA_HIGH"` (a value not in the current enum)
- **Action:** Decode as the model containing RiskTier
- **Expected:** Decoding does NOT crash. Either maps to `.unknown("ULTRA_HIGH")` or fails gracefully.
- **Why:** When the backend adds new enum values, old app versions must not crash. This is the #1 cause of App Store review rejections.

#### T29: test_api_response_decoding_with_extra_fields
- **Spec ref:** Forward compatibility
- **Category:** Edge case
- **Setup:** JSON with all expected fields PLUS unexpected additional fields
- **Action:** Decode as the model
- **Expected:** Decoding succeeds, extra fields are ignored (not a crash)
- **Why:** Backend API evolution will add fields. The iOS client must tolerate unknown fields.

#### T30: test_sse_client_max_reconnection_attempts
- **Spec ref:** Robustness
- **Category:** Edge case
- **Setup:** Mock URLSession that always fails
- **Action:** SSEClient connects
- **Expected:** After exhausting backoff schedule [1s, 2s, 5s, 10s], stops reconnecting and reports a final error
- **Why:** Without a max, the client reconnects forever, draining battery.

#### T31: test_model_decoding_message_with_all_roles
- **Spec ref:** Backend schema
- **Category:** Completeness
- **Setup:** JSON messages with role: "user", "assistant", "system", "tool"
- **Action:** Decode each
- **Expected:** All roles decode to distinct enum values
- **Why:** Missing role values cause messages to disappear from the UI.

---

## Security Test Requirements

1. **T25 (no hardcoded secrets):** Environment configuration must not embed API keys, JWT secrets, or other credentials. Only base URLs and non-sensitive configuration.

2. **T3 (auth header injection):** Verify the Authorization header is correctly formed. A missing "Bearer " prefix or wrong token value would cause authentication bypass or failure.

3. **T5 (no infinite 401 loop):** A server that always returns 401 must not cause the client to loop forever. This is both a security concern (credential stuffing amplification) and a reliability concern.

4. **DeviceID Keychain access group:** If DeviceID uses a Keychain access group, verify it is scoped to the app's bundle ID — not a shared group that other apps could read. (Verify in code review if not testable in unit tests.)

5. **No plaintext token storage:** Verify that `APIClient`'s token provider interface does NOT store tokens in UserDefaults, plist files, or any non-Keychain storage. The actual Keychain implementation is iOS4's responsibility, but iOS3 must not introduce a competing storage mechanism.

---

## Integration Test Requirements

Tests that must exercise real code paths (not just mocks):

1. **T17-T21 (model decoding):** These MUST decode actual JSON strings through Swift's `JSONDecoder` — not mock the decoder. Use real JSON payloads matching the backend's actual output format.

2. **T22-T23 (DeviceID):** Must interact with the real Keychain API (available in simulator). Mocking Keychain would defeat the purpose — the test verifies Keychain persistence actually works.

3. **T11-T14 (SSE parsing):** The parser itself should be tested with real byte streams, not mocked. Only the network transport layer (URLSession) should be mocked.

4. **At least one test must verify that `APIClient` can be instantiated with `NoaEnvironment` configuration and produce a valid `URLRequest`** — proving the wiring between configuration and networking works.

---

## Anti-Patterns to Watch For

Based on past retros and audit findings, these are the specific anti-patterns most likely to appear in iOS3:

1. **"Wired in class, not in app" (recurring):** `APIClient` exists but is never instantiated in `NaoApp.swift` or injected via SwiftUI's `@EnvironmentObject`. Check that the app entry point actually creates and injects the networking layer.

2. **Source inspection instead of behavioral tests:** Do NOT write tests that just check "APIClient has a method called `get`." Tests must call the method and verify the output.

3. **Model types that don't match backend JSON:** The iOS `Thread` model must decode the exact JSON the backend produces. Get a real response example from the backend code (or construct one from the Pydantic schema) and use it as the test fixture. Do NOT invent a JSON shape.

4. **SSE parser tested only with perfect input:** Real SSE streams have keepalive comments, empty lines, and occasional malformed data. Test the parser with messy input, not just clean `data: {...}\n\n`.

5. **DeviceID using UserDefaults instead of Keychain:** UserDefaults does NOT persist across app reinstalls. The spec requires Keychain. Test must verify Keychain is used (T23 catches this).

6. **Idempotency keys generated but never attached:** The key generation function exists but `APIClient.post()` doesn't include it in headers. T8 catches this.

7. **Missing error enum cases:** If `ApiError` has only `.serverError` and `.networkError` but not `.unauthorized` or `.rateLimited`, the app can't handle 401/429 responses properly. Ensure the error type covers all HTTP status categories the client cares about.

8. **`or ""` fallback on base URL:** `NoaEnvironment.baseURL` must not fall back to an empty string or `localhost` if unconfigured. An empty base URL causes every request to go to the wrong place silently.

9. **Deployment target mismatch:** The Xcode project must set minimum deployment target to iOS 17.0. If it defaults to iOS 26, the app won't run on older devices. Verify the project setting.

---

## Unit Test vs Simulator Boundary

| Area | Unit Testable (no simulator) | Requires Simulator |
|------|------------------------------|-------------------|
| JSON model decoding | Yes | No |
| APIClient request construction | Yes (with mock URLProtocol) | No |
| APIClient auth header injection | Yes (with mock URLProtocol) | No |
| APIClient 401 retry logic | Yes (with mock URLProtocol) | No |
| SSE line parsing | Yes (pure function) | No |
| SSE reconnection backoff | Yes (with injected clock) | No |
| Idempotency key generation | Yes (pure function) | No |
| DeviceID Keychain read/write | Partially (Keychain works in test host) | Better in simulator |
| Environment configuration | Yes | No |
| SwiftUI view rendering | No | Yes |
| Full URLSession networking | No | Yes (or mock URLProtocol) |

All 31 tests in this plan are unit-testable with `XCTest` using mock `URLProtocol` for networking. No simulator-only tests are required for iOS3 (the simulator is needed only to run the test host, not for simulator-specific behavior).

---

## Acceptance Criteria (mapped to QA_CHECKLIST)

| ID | Criterion | iOS3 Requirement |
|----|-----------|-------------------|
| M1 | Spec Traceability | Every test references SPEC.md §25.3, §25.4, §29.1, or PLAN Phase iOS3 |
| M2 | Negative Tests | T5 (infinite 401 loop), T7 (network error), T14 (malformed SSE), T18 (API error response) |
| M3 | Security Boundaries | T25 (no hardcoded secrets), T3 (auth header), T5 (no loop), DeviceID Keychain scoping |
| M4 | Determinism | No wall-clock time in assertions; backoff tested via injected delays; no network calls (mock URLProtocol) |
| M5 | Implementation Completeness | All 13 files from phase plan created; all 7 deliverables functional |
| M6 | No Silent Error Swallowing | No empty catch blocks; all errors surfaced as typed errors |
| M7 | Wiring Completeness | APIClient instantiated in app; environment injected; not orphaned code |
| M8 | Domain Isolation | N/A for iOS (no private/external worker split), but no backend imports in iOS code |
