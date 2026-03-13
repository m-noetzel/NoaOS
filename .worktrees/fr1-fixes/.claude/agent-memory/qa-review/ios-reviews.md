# iOS Review Notes (moved from MEMORY.md to save space)

## iOS1/iOS2 Review Notes (2026-03-08)
- Migration 008 created correctly (plan said 005 but 005-007 existed).
- Devices and voice routers registered in app.py. Endpoints reachable.
- Cycle 1 FAIL: APNsService and ApprovalBatcher orphaned, no JWT, no chat mode.
- Cycle 2 PASS_WITH_NOTES: APNsService wired in app.py lifespan, JWT signing added, push hooks in approval.py and service.py, voice mode param added.
- REMAINING: _http_client still None. Push hooks log but never call send(). ApprovalBatcher still orphaned. Voice chat mode is a stub (random thread_id, no pipeline). `or ""` fallbacks for APNs config in app.py.
- validation.py hardcodes 25MB; config.max_audio_size_mb exists but is disconnected.
- "Schema construction tests" pattern: iOS1 tests T15-T17 construct PushPayload directly instead of testing approval-to-push integration.

## iOS3 Review Notes (2026-03-08)
- iOS code uses SPM (Package.swift at `ios/Noa/`), not xcodeproj. App entry point deferred.
- Swift 6 strict concurrency enforced (swift-tools-version: 6.0). APIClient and SSEClient are actors.
- Test target named `NaoTests` (Nao, not Noa -- naming inconsistency).
- `ApiResponse<T>` uses `@unchecked Sendable` -- could constrain T: Decodable & Sendable instead.
- SSEClient.stream() reconnection loop (while-true, backoff, maxReconnectsExceeded) has zero behavioral test coverage. Only backoff constant values tested.
- Backend contract tests in `tests/unit/test_ios3_networking_contract.py` (41 tests) pin JSON shapes.
- Backend envelope is `{ok, data, error, trace_id}` -- flat trace_id, NOT nested meta object.
- For iOS phases: M7 assessed as "deferred to app target phase"; M8 is N/A.

## iOS4 Review Notes (2026-03-09)
- KeychainService is an enum (static methods). AuthService is an actor. AuthViewModel is @Observable final class (not @MainActor).
- AuthService conforms to TokenProviding (iOS3 protocol) -- verified at compile time and via cast test.
- `nonisolated(unsafe)` on AuthViewModel properties -- Swift 6 workaround for @Observable + Sendable. Consider @MainActor instead.
- Login endpoint returns flat AuthTokenResponse; refresh endpoint returns success_envelope(data={...}). APIClient.decode() handles both but fragile.
- CRITICAL GAP: AuthService.refresh() does NOT call clearTokens() on failure.
- `access_token_expire_minutes = 30` (config) vs SPEC "15min" -- pre-existing discrepancy.
- 20 Swift tests + 16 Python contract tests. 60/60 Swift total pass.

## iOS5 Review Notes (2026-03-09)
- Cycle 1 FAIL caught 2 field mismatches: result_ready read `payload["text"]` (should be `"response"`), classification_done read `payload["domain"]` (should be `"privacy_mode"`). Also `try?` on SSE decode silently dropped events.
- Cycle 2 PASS_WITH_NOTES after all 4 blocking issues fixed. 12 Swift Testing tests added (4 suites). 32 Python contract tests.
- ChatViewModel is @Observable + @MainActor. ChatService is an actor. Both correct for Swift 6.
- cancelStream() exists but never called from views -- thread switching while streaming causes events on wrong thread.

## iOS7 Review Notes (2026-03-09)
- BiometricService is an actor wrapping LAContext. BiometricAuthenticating protocol enables mock injection.
- ApprovalService is an actor with fetchPending()/decide() matching backend endpoints.
- Biometric gate only for `.high` risk tier (per SPEC SS29.3 item 4). Low and medium skip biometric.
- Batch approve/deny intentionally bypasses biometric for high-risk items.
- 14 new Swift tests. Total: 109 (97 XCTest + 12 swift-testing). PASS_WITH_NOTES.

## iOS11 Review Notes (2026-03-10)
- Cycle 1 FAIL: 6 of 7 deliverables missing. Only backend Python contract tests delivered.
- Cycle 2 PASS_WITH_NOTES: 13 Swift integration tests (4 files), ErrorView + EmptyStateView created.
- LoginFlowTests (IT1-IT4): genuine multi-component integration.
- ChatFlowTests IT5-IT6 are NOT integration tests -- inline string concat and JSON parsing without calling any Noa type.
- CertificatePinningDelegate still NOT wired. VPN prompt wiring also still unresolved.
