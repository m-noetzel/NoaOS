# QA Review Agent Memory (iOS)

## Project Structure
- iOS code lives at `/Users/martin2020/Projekte/NoaOS/ios/Noa/` (SPM package, not xcodeproj)
- Plan docs are at `/Users/martin2020/Projekte/NoaOS/Plan/` (root, not inside ios/Noa/)
- Swift 6 strict concurrency enforced via swift-tools-version: 6.0
- Test target named `NaoTests` (note: Nao, not Noa -- naming inconsistency)

## Backend Contract Tests Pattern
- Backend contract tests in `tests/unit/test_ios{N}_*.py` pin the JSON shapes iOS must decode
- These import real backend modules (schemas, middleware) -- not mocks
- Always verify Swift CodingKeys match backend field names exactly
- **CRITICAL:** Some contract tests test their own mock shapes instead of actual backend emissions. Verified in iOS5: `step_name` in test vs `step` in runner.py. Contract tests should verify the real backend source, not fabricated dicts.
- **RESOLVED in iOS5 cycle 2:** `response_text` fixed to `response`, `domain` fixed to `privacy_mode`
- **iOS6:** No Python contract test written. Swift CodingKeys match backend schema (verified manually). Consider adding test_ios6_push_contract.py.

## Recurring Patterns to Watch
- `@unchecked Sendable` escape hatches -- check if T constraints could be tightened instead
- `nonisolated(unsafe)` on test helpers (MockURLProtocol.handler) -- acceptable for serial tests
- `nonisolated(unsafe)` on AuthViewModel properties -- Swift 6 workaround for @Observable + Sendable; consider @MainActor instead
- `try?` in streaming parsers -- document as intentional resilience, verify error callback exists
- `try?` for best-effort server calls (logout) -- acceptable if local cleanup always follows unconditionally
- `try?` in extractFields JSON round-trip (PushNotificationService, DeepLinkRouter) -- acceptable, produces generic fallback
- SSEClient reconnection logic is complex (while-true loop) but has no behavioral test coverage as of iOS3
- `timeoutIntervalForRequest = 0` may not mean "no timeout" on all platforms
- **Error-path token cleanup:** AuthService.refresh() does NOT clear Keychain on failure -- stale tokens persist. No test covers this (test plan T9 was dropped)
- **cancelStream() never called from views** -- thread switching while streaming causes events to append to wrong thread
- **_VoidResponse duplication:** Defined as private struct in both PushNotificationService.swift and DeviceService.swift. Minor micro-duplication.
- **catch APIError.decodingError** pattern (handleInlineAction): narrow catch for fire-and-forget API calls. Acceptable when HTTP request matters, not response body.

## Key Backend Schemas (iOS model must match)
- Envelope: `{ok, data, error, trace_id}` -- flat trace_id, NOT nested meta object
- AuthTokenResponse: `{token_type, expires_in, authenticated, access_token, refresh_token}`
- Login returns flat AuthTokenResponse; refresh returns success_envelope(data={...}) -- inconsistent but APIClient handles both
- Run: `{id, thread_id, user_id, status, risk_tier, privacy_mode, summary, created_at, updated_at}`
- Approval: `{id, run_id, user_id, risk_tier, preview_text, decision, domain, requested_at, decided_at, decided_by_user_id}`
- SSE event types: 12 total including "meta"
- **result_ready payload uses `"response"` field** (NOT `response_text` or `text`) -- VERIFIED iOS5 cycle 2
- **classification_done payload uses `"privacy_mode"` field** (NOT `domain`) -- VERIFIED iOS5 cycle 2
- **step_started payload uses `"step"` field** (NOT `step_name`) -- Swift correct, Python contract test wrong
- **DeviceTokenRequest:** `{device_id, platform, push_token}` -- VERIFIED iOS6
- **Approval decide:** `POST /{approval_id}/decide` with `{decision: "approved"|"denied"}` -- VERIFIED iOS6

## Thread Response Shape Drift
- Backend list_threads stub returns items WITHOUT `user_id`, WITH `message_count` and `updated_at`
- Swift Thread struct requires `userId: UUID` (non-optional), lacks `messageCount`/`updatedAt`
- Will be a hard runtime crash when stubs become real DB queries -- track for resolution

## Review Process Notes
- `swift test` runs at `/Users/martin2020/Projekte/NoaOS/ios/Noa/`
- Backend contract tests run in Docker: `docker exec noa-dev pytest tests/unit/test_ios5_chat_contract.py`
- For iOS phases, M7 (wiring) is assessed differently -- library package has no app entry point until iOS11
- M8 (domain isolation) is N/A for pure iOS packages
- **Always count Swift tests by test file, not just total count.** iOS5 cycle 1 had "60 tests pass" but all 60 were from prior phases (0 from iOS5).
- Pipe Python scripts to docker via `cat script.py | docker exec -i noa-dev python3 -` since the container rootfs is read-only.
- **Cycle reviews matter:** iOS5 cycle 1 FAIL caught 2 field mismatches that would have caused silent data loss. Adversarial QA process validated.
- **iOS app target is the biggest integration risk.** No @main exists -- all components tested in isolation only. 10+ service actors after iOS8 (APIClient, SSEClient, KeychainService, AuthService, ChatService, PushNotificationService, DeviceService, BiometricService, ApprovalService, AudioRecorderService, AudioPlayerService, VoiceService).
- swift test output: XCTest results show individually, swift-testing shows summary line "Test run with N tests". Total = XCTest passed count + swift-testing count.
- Totals after iOS7: 109 tests (97 XCTest + 12 swift-testing), 14 from iOS7.
- **Batch biometric bypass is intentional**: ApprovalListViewModel._batchDecide does NOT require biometric for high-risk items. Documented in code comment. Spec SS23.2 doesn't mention step-up for batch. If policy changes, update there.
- **_DecisionResponse duplication**: Private Decodable struct pattern continues in ApprovalService.swift (same as PushNotificationService, DeviceService).
- **Backend approval endpoints are stubs**: /pending always returns [], /decide always succeeds. Full flow untestable until backend implements real persistence.
- **iOS8 RESOLVED cycle 2:** MockAudioRecorder fixed with stored properties on actor. Lesson: always run `swift test` to verify mock protocol conformance before claiming pass counts.
- **Voice endpoint chat mode is a stub:** voice.py line 123-134 returns a random thread_id without invoking the chat pipeline. Documented but not flagged in tests.
- **VoiceUploadResponse is flat JSON** (NOT wrapped in ApiResponse envelope). Swift VoiceService decodes directly. CodingKeys: `text`, `mode`, `thread_id`.
- **tools/whisper-service/server.py** is a standalone host service documented in RUNBOOK section 8 but not in Docker Compose. Host-only dev tool.
- **`try? configurePlaybackSession()`** in AudioPlayerService silently swallows session config errors.
- Current totals after iOS8: 124 tests (112 XCTest + 12 swift-testing), 15 new from iOS8.
- Totals after iOS9: 126 tests (not verified individually). 14 new from iOS9 (OfflineQueueService, NetworkMonitorService).
- Totals after iOS10: 139 tests (127 XCTest + 12 swift-testing), 13 new from iOS10.
- **CertificatePinningDelegate is NOT wired into any production URLSession as of iOS10.** All 4 sites (APIClient:61, SSEClient:53, VoiceService:123, ChatService:71) still use `URLSession(configuration: config)` without delegate. iOS11 MUST wire this.
- **VPNStatusBanner and VPNService are orphaned.** Not referenced from any view or ViewModel. iOS11 must compose.
- **DispatchSemaphore in actor context:** VPNService.launchViaSystem blocks cooperative thread with sema.wait() waiting for MainActor task. Latent deadlock risk. Should be refactored to async.
- **NEVPNStatusProvider `@unchecked Sendable`** is acceptable -- no mutable state, NEVPNManager not Sendable in Apple SDK.
- **Placeholder SPKI hash** in PinnedCertificates.swift must be replaced before deployment. T6 catches empty set but not wrong hash.
- **iOS11 overload risk:** Must wire CertificatePinningDelegate, compose 12+ actors, add VPNStatusBanner, write E2E tests, accessibility, dark mode, error states, app icon, launch screen. Estimated 45min but likely much longer.
- **cancelStream() issue RESOLVED in PR3:** cancelStreamAndClear() now called from MainTabView.onChange(of: selectedThreadId). Old entry about "cancelStream() never called from views" is fixed.
- Totals after PR3: 182 tests (170 XCTest + 12 swift-testing), 11 new from PR3.
- **RESOLVED (PR3 cycle 2): ChatRequest contract mismatch.** Backend chat.py:33-34 now has `model: str | None = None` and `provider: str | None = None`. iOS omits these keys (JSONEncoder skips nil), Pydantic accepts missing keys as None, router node falls through to _EXTERNAL_MODEL default. Verified via smoke test.
- **Runner.run() model default is dead code.** chat.py always passes `model=body.model` explicitly (even when None), bypassing the `model: str = "anthropic/claude-haiku"` default on runner.py:42. Actual fallback is in nodes/router.py:56 (_EXTERNAL_MODEL).
- **Swift JSONEncoder omits nil Optional keys** -- does NOT encode them as `null`. This means missing keys, not null values, which Pydantic treats as missing required fields. Always verify optional Swift fields against backend field optionality. **Lesson from PR3:** when adding new optional fields to iOS models, always check that the corresponding Pydantic model has `field: type | None = None` (not just `field: type`). The mismatch is invisible at compile time and only surfaces as HTTP 422 at runtime.
- **NoaApp.swift** (ios/NoaApp/NoaApp/) is the app entry point with @main. Wires all actors via ServiceFactory. ContentView wraps AuthGuard -> MainTabView.
- Totals after GO3: 216 tests (204 XCTest + 12 swift-testing), 16 new from GO3 (9 GoogleAuthServiceTests + 7 SettingsViewModelTests).
- **Google OAuth2 backend response shapes (VERIFIED GO3):** authorize returns `{auth_url}` inside envelope, status returns `{connected, scopes}`, disconnect returns `{disconnected}`. APIClient.get() extracts from envelope `.data` automatically.
- **ASWebAuthSessionAdapter gated behind `#if canImport(AuthenticationServices) && !os(macOS)`** -- only compiles on iOS device target, not in macOS test runs. Tests use MockWebAuthSession.
- **Backend `platform=ios` redirect untested** -- _seed_state accepts platform but no test calls it with "ios". Code at auth.py:507-509 redirects to `noaapp://` for iOS. Simple path but has zero coverage.
