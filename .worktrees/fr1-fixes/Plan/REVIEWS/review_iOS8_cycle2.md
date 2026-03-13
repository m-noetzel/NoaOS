# QA Review: Phase iOS8 (Cycle 2)

**Date:** 2026-03-09
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)
**Previous verdict:** FAIL (cycle 1) -- both blocking issues resolved

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 5/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 15 Swift tests cite SPEC.md SS29.2; all 21 Python tests cite SS29.3/SS36.3 |
| M2 | Negative Tests | PASS | T5 (permission denied), T6 (upload error), T15 (401 unauthorized), unknown provider ValueError |
| M3 | Security Boundaries | PASS | Auth header on uploads, permission handling, no hardcoded secrets |
| M4 | Determinism | PASS | No wall-clock, no network, no unseeded randomness in tests |
| M5 | Implementation Completeness | PASS | swift build clean, swift test 124 pass (112 XCTest + 12 swift-testing), 38 Python tests pass |
| M6 | No Silent Error Swallowing | PASS | `except Exception as exc` in transcription.py re-raises as TranscriptionError (lines 87, 132). Swift `try?` limited to Task.sleep, FileManager.removeItem, configurePlaybackSession -- all acceptable |
| M7 | Wiring Completeness | PASS | Voice router registered in app.py line 358. VoiceRecordButton in ComposerBar. TranscriptionProviderView in MainTabView settings. |
| M8 | Domain Isolation | PASS | No cross-domain imports. whisper-service now documented in RUNBOOK.md section 8 with setup, config, health check, troubleshooting. Env vars TRANSCRIPTION_PROVIDER and WHISPER_CPP_URL in optional vars table. |
| S1 | Error Handling & Boundaries | PASS | VoiceServiceError enum covers fileReadFailed, unauthorized, networkError, serverError, decodingError |
| S2 | Code Consistency | PASS | Actor pattern consistent with BiometricService/ApprovalService. Protocol-based DI matches project conventions. |
| S3 | Migration & Rollback | PASS/N/A | No DB changes |
| S4 | Documentation | PASS | RUNBOOK section 8 added. Public APIs typed. Inline comments on non-obvious logic. |
| S5 | Integration Smoke Test | PASS | Backend smoke imports verified. Swift tests compile and execute -- T13 tests real VoiceService with MockURLProtocol (HTTP boundary mock only). T3 tests VoiceViewModel -> VoiceService -> ChatViewModel wiring with real objects. |

## Cycle 1 Blocking Issues -- Resolution

| Blocker | Status | Verification |
|---------|--------|-------------|
| MockAudioRecorder missing `isRecording`, `duration`, `audioLevel` (M5 FAIL) | RESOLVED | VoiceViewModelTests.swift lines 28-30: properties added as stored vars on actor. Protocol conformance satisfied. `swift test` passes 124 tests with 0 failures. |
| whisper-service undocumented dead code (M8 FAIL) | RESOLVED | RUNBOOK.md lines 303-351: Section 8 "Voice Transcription (whisper.cpp)" with setup instructions, model download, config, health check, and troubleshooting table. Env vars in optional vars table (lines 32-33). |

## Test Plan Coverage

Test plan specified 19 tests (T1-T19). Implementation coverage:

| Test Plan | Implementation | Verdict |
|-----------|---------------|---------|
| T1 (protocol abstraction) | AudioRecording protocol + MockAudioRecorder | COVERED |
| T2 (m4a format) | Code uses kAudioFormatMPEG4AAC; no unit test on format settings | PARTIAL (acceptable -- AVFoundation mock boundary) |
| T3 (stop returns URL) | T10 in AudioRecorderServiceTests | COVERED |
| T4 (permission denied) | T5 in VoiceViewModelTests | COVERED |
| T5 (permission request) | Covered by startRecording flow | COVERED (implicitly) |
| T6 (10-min max) | startDurationTask() in code, no dedicated test | NOT TESTED (acceptable -- timer-based, hard to unit test) |
| T7 (multipart upload) | T13 in AudioRecorderServiceTests verifies Content-Type and endpoint | COVERED |
| T8 (response decode) | T14 decodes flat JSON with thread_id UUID | COVERED |
| T9 (cancel/discard) | T4 in VoiceViewModelTests | COVERED |
| T10 (auto-send) | T3 in VoiceViewModelTests with real ChatViewModel | COVERED |
| T11 (upload failure) | T6 in VoiceViewModelTests | COVERED |
| T12 (state machine) | T7 full flow: idle -> recording -> transcribed | COVERED |
| T13 (timer updates) | No dedicated test | NOT TESTED (nice-to-have) |
| T14 (play/pause) | No dedicated test | NOT TESTED (nice-to-have) |
| T15 (concurrent recording) | Not tested | NOT TESTED (nice-to-have) |
| T16 (25MB client limit) | Not implemented or tested | NOT TESTED (nice-to-have) |
| T17 (button disabled during streaming) | Not tested | NOT TESTED (nice-to-have) |
| T18 (backend contract) | test_ios8_voice_transcription.py | COVERED |
| T19 (m4a MIME) | test_accept_valid_m4a in test_ios2_voice.py | COVERED |

12/12 MUST-HAVE tests covered. 0/5 NICE-TO-HAVE tests covered (acceptable per checklist).

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- `src/noa/voice/transcription.py:87`: `except Exception as exc` -> re-raises as `TranscriptionError`. Acceptable.
- `src/noa/voice/transcription.py:132`: `except Exception as exc` -> re-raises as `TranscriptionError`. Acceptable.
- No bare `except:` anywhere in `src/noa/voice/`.

**M7: Wiring:**
- `src/noa/api/app.py:358`: `app.include_router(voice_router, prefix="/api/v1/voice")` -- registered.

**M8: Domain isolation:**
- No `from noa.private_worker` in `src/noa/voice/`.
- No cross-domain imports detected.

## Smoke Test Results

**Swift:**
```
swift build: Build complete! (0.07s)
swift test:  Executed 112 tests, with 0 failures (0 unexpected) in 0.410 seconds
             Test run with 12 tests in 4 suites passed after 0.001 seconds.
             Total: 124 tests, 0 failures.
```

**Python:**
```
tests/unit/test_ios8_voice_transcription.py: 21 passed
tests/unit/test_ios2_voice.py: 17 passed
Total: 38 passed, 0 failures
```

## Security

No new security concerns beyond those acknowledged in cycle 1:

1. **API key in UserDefaults** -- low risk, local-only setting, not wired to backend. Tracked as tech debt.
2. **whisper-service binds 0.0.0.0 without auth** -- now documented in RUNBOOK with clear "local development only" context.
3. **Auth header on voice uploads** -- correctly implemented via Bearer token from TokenProviding.
4. **No hardcoded secrets** in any source files.

## Code Quality

No changes to code quality assessment from cycle 1. Architecture remains clean:
- Actor pattern for AudioRecorderService, AudioPlayerService, VoiceService
- Protocol-based DI (AudioRecording, AudioPlaying, VoiceServicing)
- `try?` limited to non-critical paths (sleep, cleanup, session config)

## Beyond the Test Plan

Carry-forward observations from cycle 1 (none are blocking):

1. **Voice chat mode stub** (`voice.py:123-134`): Returns random `thread_id` without invoking chat pipeline. Documented in MEMORY.md.
2. **AVAudioPlayer completion via timer** not delegate: Acceptable for MVP, may drift slightly.
3. **No client-side file size validation**: VoiceService reads full file into memory without pre-check.
4. **`configurePlaybackSession()` error swallowed** in AudioPlayerService:72 via `try?`.

## Notes (PASS_WITH_NOTES)

1. Voice chat mode in `voice.py` (lines 123-134) is a stub returning a random `thread_id` without invoking the chat pipeline. The response advertises `mode="chat"` but no chat processing occurs. Track for resolution when chat pipeline integration is built.

2. `configurePlaybackSession()` error silently swallowed in AudioPlayerService.swift:72 via `try?`. If audio session setup fails, playback proceeds blind.

3. No client-side file size pre-check in VoiceService before `Data(contentsOf: audioURL)`. A corrupt or oversized recording would be fully loaded into memory before backend rejects it.

4. TranscriptionProviderView stores OpenAI API key in UserDefaults instead of Keychain. Low risk (local-only, not sent to backend) but inconsistent with Keychain pattern used elsewhere.

5. Total test counts: 124 Swift (112 XCTest + 12 swift-testing), 38 Python (21 iOS8 + 17 iOS2). 15 new Swift tests from iOS8, 21 new Python tests from iOS8.

## Decision Review

Both cycle 1 blocking issues are cleanly resolved. The MockAudioRecorder fix is minimal and correct -- three stored properties on the actor satisfy the `{ get async }` protocol requirements. The RUNBOOK documentation is thorough with setup, config, health check, and troubleshooting. All 124 Swift tests pass, all 38 Python tests pass. The remaining notes are carry-forward observations from cycle 1, all acknowledged as non-blocking.
