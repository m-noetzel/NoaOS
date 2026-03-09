# QA Review: Phase iOS8

**Date:** 2026-03-09
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 6/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All tests cite SPEC.md SS29.2 or Phase iOS8; backend tests cite SS29.3 and SS36.3 |
| M2 | Negative Tests | PASS | T5 (permission denied), T6 (upload error), T15 (401 unauthorized), unknown provider ValueError |
| M3 | Security Boundaries | PASS | Auth header on uploads, permission handling, no hardcoded secrets. API key in UserDefaults is acknowledged tech debt. |
| M4 | Determinism | PASS | No wall-clock, no network, no unseeded randomness in tests |
| M5 | Implementation Completeness | FAIL | **Swift test target does not compile.** MockAudioRecorder missing isRecording/duration/audioLevel properties required by AudioRecording protocol. Claimed "112 tests pass" is false. |
| M6 | No Silent Error Swallowing | PASS | `except Exception as exc` in transcription.py re-raises as TranscriptionError. `try?` in Swift limited to file cleanup, sleep, and session config -- all acceptable. |
| M7 | Wiring Completeness | PASS | Voice router registered in app.py (line 358). VoiceRecordButton wired into ComposerBar. TranscriptionProviderView in MainTabView settings. |
| M8 | Domain Isolation | FAIL | N/A for pure iOS package. However, `tools/whisper-service/server.py` is a new standalone service with no integration into Docker Compose or startup wiring -- it is dead code from the running system perspective. |
| S1 | Error Handling & Boundaries | PASS | VoiceServiceError enum covers all paths: fileReadFailed, unauthorized, networkError, serverError, decodingError |
| S2 | Code Consistency | PASS | Actor pattern consistent with BiometricService/ApprovalService. Protocol-based DI matches project conventions. |
| S3 | Migration & Rollback | PASS/N/A | No DB changes in this phase |
| S4 | Documentation | PASS | Good inline comments, docstrings on all public APIs |
| S5 | Integration Smoke Test | OPEN | Backend smoke test passes. Swift tests do not compile -- cannot verify integration. |

## Test Plan Coverage

The test plan (test-plan_iOS8.md) identified 19 test specifications. Coverage mapping:

| Test Plan | Implementation | Status |
|-----------|---------------|--------|
| T1 (protocol abstraction) | AudioRecording protocol exists, MockAudioRecorder created | PRESENT but broken -- mock does not compile |
| T2 (m4a format) | AudioRecorderService uses kAudioFormatMPEG4AAC | Code present, untestable |
| T3 (stop returns URL) | T10 in tests | PRESENT but broken |
| T4 (permission denied) | T5 in VoiceViewModelTests | PRESENT but broken |
| T5 (permission request) | Covered by startRecording flow in AudioRecorderService | Code present, untestable |
| T6 (10-min max duration) | startDurationTask() in AudioRecorderService | Code present, NO test |
| T7 (multipart upload) | T13 in AudioRecorderServiceTests | PRESENT but broken |
| T8 (response decode) | T14 in AudioRecorderServiceTests | PRESENT but broken |
| T9 (cancel/discard) | T4 in VoiceViewModelTests | PRESENT but broken |
| T10 (auto-send) | T3 in VoiceViewModelTests | PRESENT but broken |
| T11 (upload failure) | T6 in VoiceViewModelTests | PRESENT but broken |
| T12 (state machine) | T7 in VoiceViewModelTests | PRESENT but broken |
| T18 (backend contract) | Covered in test_ios8_voice_transcription.py | PASS |
| T19 (m4a MIME) | audio/m4a in ALLOWED_MIME_TYPES, test_accept_valid_m4a | PASS |

The test plan's predicted risk #3 (APIClient bypass without auth) was handled well -- VoiceService uses raw URLSession with explicit Bearer token injection.

The test plan's anti-pattern #9 (hand-rolled multipart) was realized -- VoiceService.buildMultipartBody() is manually constructed. The format looks correct (boundary, CRLF, Content-Disposition) but untestable due to compilation failure.

## Spec Compliance

| Requirement | Status |
|-------------|--------|
| AVAudioRecorder-based recording (SS29.2) | Implemented |
| m4a format (AAC, 16kHz, mono) | Implemented |
| 10-minute max duration | Implemented (timer-based) |
| Microphone permission handling | Implemented |
| Upload to /api/v1/voice/transcribe | Implemented |
| Multipart form-data with "file" and "mode" fields | Implemented |
| Auto-send transcription to chat | Implemented |
| Dual transcription provider (OpenAI + whisper.cpp) | Implemented (backend) |
| Provider selection via config/settings | Implemented (backend: TRANSCRIPTION_PROVIDER env; iOS: UserDefaults) |
| Audio playback (AVAudioPlayer) | Implemented |
| VoiceRecordButton with waveform + timer | Implemented |
| ComposerBar integration | Implemented |
| TranscriptionProviderView in Settings | Implemented |

## Test Coverage

**Python backend:** 38 tests pass (21 new iOS8 + 17 updated iOS2). Good coverage of:
- TranscriptionProvider ABC enforcement
- OpenAIWhisperProvider happy path + error path
- WhisperCppProvider happy path + error path + env-var URL
- Provider dispatch routing + unknown provider rejection
- Config defaults
- Integration tests with real provider objects (HTTP-only mocked)

**Swift iOS:** 15 tests written but **0 compile**. The test target fails with:
```
error: type 'MockAudioRecorder' does not conform to protocol 'AudioRecording'
```
`MockAudioRecorder` does not implement the `isRecording`, `duration`, or `audioLevel` async properties required by the `AudioRecording` protocol.

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- `src/noa/voice/`: No `except:` or `except Exception: pass` found
- `src/noa/voice/transcription.py:87,132`: `except Exception as exc` re-raised as TranscriptionError -- acceptable per L9

**M7: Wiring:**
- `src/noa/api/app.py:32`: `from noa.api.v1.voice import router as voice_router`
- `src/noa/api/app.py:358`: `app.include_router(voice_router, prefix="/api/v1/voice")`
- Voice router properly wired.

**M8: Domain isolation:**
- No cross-domain imports in `src/noa/voice/`

## Smoke Test Results

**Backend (Python):**
```
OK: transcription module imports
OK: validation module imports
OK: schemas module imports
OK: voice router imports
OK: TranscriptionProvider ABC raises TypeError
OK: audio/m4a in ALLOWED_MIME_TYPES
OK: config has transcription_provider and whisper_cpp_url
OK: /transcribe route registered
OK: TranscriptionService.transcribe() has provider param
OK: TranscriptionService init takes provider objects

All smoke tests passed.
```

**Swift:**
```
swift build: Build complete! (0.09s)  -- library compiles
swift test:  error: type 'MockAudioRecorder' does not conform to protocol 'AudioRecording'
             -- test target FAILS to compile
```

## Security

1. **API key in UserDefaults (TranscriptionProviderView):** OpenAI API key stored in UserDefaults, not Keychain. Acknowledged as tech debt in implementation summary. UserDefaults is plaintext on-disk and accessible to any code in the app sandbox. For a local-only settings UI not wired to backend, this is low risk but should be tracked.

2. **Auth header on voice upload:** VoiceService correctly injects `Bearer` token from TokenProviding. 401 handled explicitly as `VoiceServiceError.unauthorized`.

3. **No hardcoded secrets** in any source files.

4. **OPENAI_API_KEY in voice.py:** Read from `os.environ.get("OPENAI_API_KEY", "")` -- empty string fallback. When provider is "openai" and key is empty, the endpoint correctly returns 503. When provider is "whisper_cpp", the empty key is never used. Acceptable pattern.

5. **whisper-service (server.py):** Runs on host with `--host 0.0.0.0`, no authentication. Anyone on the network can POST audio for transcription. This is intended for local development only, but should be documented.

## Code Quality

1. **Actor pattern:** AudioRecorderService, AudioPlayerService, VoiceService all use actor isolation -- consistent with project conventions.

2. **Protocol-based DI:** AudioRecording, AudioPlaying, VoiceServicing protocols enable test injection -- good design.

3. **`@unchecked Sendable` on AVAudioPlayer:** Line 36 of AudioPlayerService.swift. Justified by actor serial execution. Consistent with prior pattern.

4. **`try?` usage:** Limited to `FileManager.removeItem` (cleanup), `Task.sleep` (timer loops), `configurePlaybackSession` (best-effort). All acceptable -- not on error paths or data-producing operations.

5. **Timer-based completion detection (AudioPlayerService):** `startCompletionTask` uses `Task.sleep(duration)` instead of `AVAudioPlayerDelegate.audioPlayerDidFinishPlaying`. Acknowledged limitation. Could drift slightly from actual playback end but acceptable for MVP.

6. **`nonisolated(unsafe)` in test mocks:** Same pattern as prior phases, acceptable for serial test execution.

7. **Data.append helper (VoiceService.swift:236):** Silently no-ops if UTF-8 encoding fails. Since all strings are ASCII (boundaries, field names), this is safe in practice but the "no-op on failure" pattern is worth noting.

## Beyond the Test Plan

1. **MockAudioRecorder missing protocol conformance** -- the test plan anticipated protocol abstraction (T1) but the implementation's mock does not implement the `async` property getters. This is the root cause of the compilation failure.

2. **`configurePlaybackSession()` error swallowed in AudioPlayerService:** Line 72 uses `try? configurePlaybackSession()`. If audio session configuration fails, playback proceeds anyway and may fail silently or produce no audio. This is a minor resilience concern -- the play() call will likely fail subsequently, but the error origin is lost.

3. **`chat` mode in voice.py is a stub:** Lines 123-134 create a random `thread_id = uuid.uuid4()` and return it, but do NOT actually feed the transcription into the chat pipeline. The response claims `mode="chat"` but no chat processing occurs. This is a silent behavioral gap between what the API advertises and what it does.

4. **VoiceService URL construction:** Line 148 `baseURL.appendingPathComponent("/api/v1/voice/transcribe")` -- when `baseURL` already has a path and you append with a leading `/`, Foundation may produce a double-slash or unexpected URL depending on the base. Should verify this produces the correct URL.

5. **No client-side file size validation:** The test plan's T16 (25MB client limit) is not implemented. VoiceService reads the full file into memory (`Data(contentsOf: audioURL)`) without checking size first. A corrupt or very large recording would be fully loaded into memory before the backend rejects it.

## Blocking Issues (FAIL)

1. **Swift test target does not compile.** `ios/Noa/Tests/NaoTests/VoiceViewModelTests.swift:19` -- `MockAudioRecorder` does not conform to `AudioRecording` protocol. Missing properties: `isRecording: Bool { get async }`, `duration: TimeInterval { get async }`, `audioLevel: Float { get async }`. All 15 Swift tests for iOS8 are untestable. The claim of "112 total pass" is false -- the test target fails to build.

   **Fix:** Add the three missing properties to `MockAudioRecorder`:
   ```swift
   var isRecording: Bool { false }
   var duration: TimeInterval { 0 }
   var audioLevel: Float { 0 }
   ```
   (with appropriate `nonisolated(unsafe)` state backing if needed for test assertions)

2. **M8/whisper-service dead code:** `tools/whisper-service/server.py` is a new 162-line FastAPI service that is not referenced by Docker Compose, not started by any project automation, and not documented in RUNBOOK.md or SETUP.md. Per L10 (wiring completeness), code that exists but is not reachable from any running application entry point is dead code. The service itself is well-implemented, but it needs at minimum a README or Docker Compose entry to be considered "wired."

   **Fix (choose one):** (a) Add a `docker-compose.override.yml` or `tools/whisper-service/README.md` documenting how to run it, OR (b) add a section to `docs/SETUP.md` describing the local whisper.cpp setup.

## Notes

_(Would be included if verdict were PASS_WITH_NOTES -- listed here for post-fix reference)_

1. Chat mode in `voice.py` (line 123-134) is a stub -- returns a fake `thread_id` without actually invoking the chat pipeline. Consider documenting this as a known limitation or TODO.

2. `configurePlaybackSession()` error silently swallowed in AudioPlayerService:72.

3. No client-side file size pre-check in VoiceService before reading full file into memory.

4. TranscriptionProviderView stores API key in UserDefaults instead of Keychain -- tracked as tech debt.

5. `tools/whisper-service/server.py` binds to `0.0.0.0` with no authentication -- fine for local dev, but document the security implications.

## Decision Review

The backend implementation is solid -- dual-provider architecture is clean, tests are comprehensive (38 pass), config wiring is correct, and the voice router is properly registered. The Swift implementation is architecturally sound (actors, protocols, DI) but fails on a basic test compilation issue. This is a one-line fix per missing property (3 properties total), so the turnaround should be fast. The whisper-service dead code issue is a documentation/wiring concern, not a code quality problem.
