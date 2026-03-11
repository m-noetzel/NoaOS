# Code Reviewer Memory — NoaOS iOS

## Key Files
- Protocols: `Sources/Noa/Services/Protocols/APIClientProtocol.swift` (TokenProviding, APIClientProtocol)
- Auth models: `Sources/Noa/Models/AuthModels.swift` (AuthTokens, LoginRequest, RefreshRequest)
- Environment: `Sources/Noa/Configuration/Environment.swift` (NoaEnvironment, baseURL)
- Backend auth: `src/noa/api/v1/auth.py` (LoginRequest requires `email` + `device_id`, not `username`)

## Critical Recurring Pattern: iOS/Backend Field Name Mismatch
- iOS `LoginRequest` sends `username` (String)
- Backend `LoginRequest` expects `email` (EmailStr) + `device_id` (str, required)
- This is a contract break that will cause HTTP 422 on every login attempt
- iOS `RefreshRequest` sends only `refresh_token`; backend also requires `device_id`

## Swift 6 Concurrency Pattern
- `nonisolated(unsafe)` on `@Observable` stored properties is the accepted Swift 6 pattern
  when Observation macro handles UI-thread delivery. NOT a data-race if mutations are
  always on the same actor/thread. BUT: if mutations occur from concurrent Task contexts
  (e.g., two overlapping loginAttempt calls), it IS a data race.
- `AuthViewModel` is NOT actor-isolated. Concurrent calls to `loginAttempt` are possible
  and would race on `isAuthenticated` / `errorMessage`.

## Architecture Notes
- Backend uses httpOnly cookies for token transport (C6); iOS is expected to use cookies too,
  but iOS `AuthService` reads tokens from the JSON body and stores in Keychain.
  Backend `AuthTokenResponse` intentionally omits `access_token`/`refresh_token` from body (C6).
  This means iOS cannot decode `access_token` / `refresh_token` from the login response —
  they are only in cookies. This is a fundamental architectural mismatch for native iOS.
- `access_token_expire_minutes` defaults to 30 in config but `AuthTokenResponse.expires_in`
  defaults to 900 (15 min hardcoded) — values are inconsistent.

## Config
- `Settings` now has both `noa_env` and `environment` fields (both default to development).
  Duplication risk: production check only guards `noa_env`, not `environment`.

## iOS6 Push Notifications — Patterns & Pitfalls (2026-03-09)

### Type Shadowing in Tests: NotificationPayload + DeepLinkDestination
- `DeepLinkRouter.swift` exports `public struct NotificationPayload` (module Noa)
- `DeepLinkRouterTests.swift` also defines `struct NotificationPayload` in the test module
- These are in different modules (Noa vs NaoTests) so they compile; tests use `@testable import Noa`
  which means both names are visible. Swift resolves to the local (test) type for unqualified refs.
  In practice this works but creates confusion and a latent bug if conformances ever diverge.
- Same pattern for `DeepLinkDestination` (Noa exports `public enum`, test defines non-Sendable local copy).
  The local test copy lacks `Sendable` — this may cause Swift 6 warnings in test code that awaits.

### Wiring Gap: No app entry point exists yet (SPM library, not app target)
- The iOS package is structured as a `.library` target in Package.swift, not an `.executable`/app target.
- There is no `@main` App struct, no AppDelegate, no scene delegate anywhere in Sources/.
- `PushNotificationService` and `DeviceService` are never instantiated anywhere in the production code.
- This is the project's running pattern for iOS phases — wiring is deferred to a later "integration" phase.
  Code reviewer should flag it but expect it to be known/intentional for now.

### Silent swallow of decodingError in handleInlineAction
- `PushNotificationService.handleInlineAction` catches `APIError.decodingError` and swallows it silently.
- If the backend returns a non-200 that happens to decode as a decodingError, it would be silently ignored.
- The comment explains the intent (fire-and-forget), but network errors and server errors still propagate.
  Only decodingError is swallowed, which is intentional and acceptable per the spec.

### Optional.map private extension shadow
- `DeepLinkRouter.swift` defines a `private extension Optional { func map(...) }` at file scope.
- This shadows `Optional.map` from the Swift stdlib within the file. Because it is private and has the
  same signature as the stdlib version, it is a no-op duplicate that adds confusion with no benefit.

### entitlements hardcoded to "development"
- `Noa.entitlements` has `aps-environment = development`. This is correct for dev builds but will need
  to be `production` for App Store / TestFlight distribution. Must be handled in CI signing config.

## iOS7 Biometric & Approval Flow — Patterns & Pitfalls (2026-03-09)

### LAError not mapped to BiometricError in authenticate()
- `BiometricService.authenticate()` uses `withCheckedThrowingContinuation` and resumes with the raw
  `Error` from `evaluatePolicy`'s completion handler. That error is an `LAError`, NOT a `BiometricError`.
- `mapLAError(_:)` exists in the same file but is never called from `authenticate()`.
- Result: callers that `catch BiometricError.lockedOut` etc. will NOT catch the real errors thrown here.
  The `biometricErrorMessage(_:)` path in `ApprovalDetailViewModel` falls through to `localizedDescription`
  for all real hardware failures — typed error handling is dead code for real failures.
- Fix: call `mapLAError` in the continuation's error path before resuming.

### Spec: biometric gate applies to HIGH only (not MEDIUM)
- SPEC.md §29.6 table + §29.3: "biometric for high tier on native" — medium requires approval but NOT
  biometric step-up. `ApprovalDetailViewModel.decide()` correctly gates on `.high` only. Confirmed correct.

### Batch operations skip biometric gate (intentional per spec)
- `_batchDecide` in `ApprovalListViewModel` calls `service.decide()` directly without biometric.
- SPEC.md §23.2 batching spec does not require biometric for batch — but HIGH risk items in a batch
  therefore bypass step-up auth. This is a spec ambiguity worth flagging to QA.

### nonisolated(unsafe) on actor mutable vars is a data race in tests if tests ever run parallel
- `MockBiometricService` and `MockApprovalService` are actors but use `nonisolated(unsafe)` for all vars,
  then mutate them from outside the actor (e.g., `mock.shouldFail = true` without `await`).
- Safe only because XCTest runs `@MainActor` test methods serially. Not safe if tests ever run with
  Swift Testing's parallel execution. Pattern is established from iOS6 review — consistent across phases.

### Wiring: ApprovalService and BiometricService added to MainTabView init — correctly threaded through
- `MainTabView` now takes `approvalService: any ApprovalServicing` and `biometricService: any BiometricAuthenticating`.
- `ApprovalListViewModel` is created in `MainTabView.init` and `ApprovalListView` is wired in body.
- Neither service is instantiated in production code (no app entry point yet) — consistent with prior phases.

## iOS8 Voice Recording & Playback — Patterns & Pitfalls (2026-03-09)

### BREAKING: iOS2 tests use old TranscriptionService API, will fail after refactor
- iOS2 `test_ios2_voice.py` constructs `TranscriptionService(api_key=..., http_client=...)` directly.
- iOS8 refactored `TranscriptionService.__init__` to `(openai_provider, whisper_cpp_provider)` — old call signature is gone.
- The context says "21 Python tests pass" — likely the iOS2 TranscriptionService tests are currently BROKEN.
  If not, there must be a shim/alias somewhere. QA must verify.

### MIME type mismatch: iOS sends audio/m4a, backend only accepts audio/mp4
- `VoiceService.swift` sets `Content-Type: audio/m4a` in the multipart "file" field.
- `validation.py` ALLOWED_MIME_TYPES has `"audio/mp4"` but NOT `"audio/m4a"`.
- Result: every real iOS recording upload will be rejected with HTTP 400.
- Fix: either add `"audio/m4a"` to ALLOWED_MIME_TYPES, or fix the iOS MIME type to `"audio/mp4"`.

### voice.py bypasses Settings — reads config from os.environ directly
- `voice.py` calls `os.environ.get("TRANSCRIPTION_PROVIDER", "openai")` directly instead of
  using the `Settings` object that has `transcription_provider` and `whisper_cpp_url` fields.
- This creates a dual-source-of-truth: `config.py` has the fields but they are never read by voice.py.
- The `Settings` fields `transcription_provider` and `whisper_cpp_url` are dead code.

### BLE001 violations in transcription.py (bare Exception catch)
- `OpenAIWhisperProvider.transcribe()` line 87: `except Exception as exc` — should be more specific.
- `WhisperCppProvider.transcribe()` line 132: same. These wrap and re-raise so ruff may pass,
  but they are architecturally sloppy (httpx raises `httpx.HTTPError`, `httpx.TimeoutException` etc.).

### whisper-service: process not killed on TimeoutError
- `_run_whisper` calls `asyncio.wait_for(..., timeout=300)` but on TimeoutError does NOT kill the subprocess.
- The whisper.cpp process continues running in the background, consuming CPU/RAM.
- Fix: catch TimeoutError, call `proc.kill()` before raising HTTP 504.

### VoiceViewModel.refreshRecorderState: protocol abstraction leak
- `refreshRecorderState()` casts `recorder as? AudioRecorderService` to read actor properties.
- If any other `AudioRecording` conformer is injected (e.g., in tests), polling silently no-ops.
- Better: extend the `AudioRecording` protocol with `duration` and `audioLevel` properties.

### TranscriptionProviderView: OpenAI API key stored in UserDefaults, not Keychain
- The settings screen stores the Whisper API key in `UserDefaults.standard` under key `"openai_whisper_api_key"`.
- UserDefaults is not encrypted and is readable from the device without authentication.
- This is noted as "per-spec simplicity for now" in the code comment — acceptable if QA agrees.
- The key is also NOT sent to the backend — it sits unused in UserDefaults (backend reads from env var).
  The UI setting has no effect on actual transcription without a separate integration step.

### AudioPlayerService: isPlaying flag uses timer-based heuristic, not delegate
- Completion is detected by sleeping for `avPlayer.duration` seconds, then setting `isPlaying = false`.
- If the user seeks, the file is shorter than expected, or playback fails mid-stream, the flag stays true.
- AVAudioPlayerDelegate would be the correct approach but requires bridging a delegate into an actor.

### VoiceRecordButton: .transcribed case uses Color.clear with onAppear side effect
- The `.transcribed` state renders an invisible `Color.clear` view and fires `onTranscribed` in `.onAppear`.
- This is a side-effect-in-body pattern that SwiftUI may re-trigger on redraws or identity changes.
- Preferred: use `.onChange(of: viewModel.state)` in the parent or an `@Observable` sink.
