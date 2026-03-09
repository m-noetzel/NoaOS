# Test Plan: Phase iOS8

**Date:** 2026-03-09
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md SS29.3 item "Voice" (Phase 2), SS36.3 item 3 ("Voice recording and playback")

## Summary

iOS8 adds voice recording (AVAudioRecorder), playback (AVAudioPlayer), microphone permission handling, a voice button in ComposerBar, waveform/timer visualization, upload to POST /api/v1/voice/transcribe, and optional auto-send to chat. The key testing risks are: (1) AVFoundation APIs require hardware mocking and protocol abstraction to be testable, (2) the multipart upload must match the backend contract exactly (audio/mp4 MIME, 25MB limit, mode=transcribe|chat), (3) auto-send integration with ChatViewModel is a new cross-service dependency that could silently break, and (4) max 10-minute recording enforcement must be server-side-validated (not just client-side timer).

## Critical Context from Dependencies

**Backend contract (iOS2):** `POST /api/v1/voice/transcribe` accepts multipart form-data with `file` (UploadFile) and `mode` (transcribe|chat). Response schema: `VoiceUploadResponse { text: str, mode: "transcribe"|"chat", thread_id: UUID? }`. Validation: 25MB max, allowed MIME types: audio/mp4, audio/mpeg, audio/wav, audio/x-wav, audio/flac, audio/ogg, audio/webm.

**Chat integration (iOS5):** `ChatViewModel.sendMessage(text:threadId:)` is the entry point. Auto-send must call this with the transcribed text. `ChatService` is an actor.

**APIClient (iOS3):** Currently only supports JSON `request<T>()`. Voice upload requires **multipart/form-data**, which is NOT supported by APIClient. This is the biggest implementation risk -- either APIClient must be extended or VoiceService must bypass it with raw URLSession.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_audio_recorder_protocol_abstraction
- **Spec ref:** Phase iOS8 deliverable 1
- **Category:** Invariant
- **Setup:** None
- **Action:** Verify AudioRecorderService conforms to a protocol (e.g., AudioRecording) that allows mock injection
- **Expected:** Protocol exists, AudioRecorderService conforms, mock can be created
- **Why:** Without protocol abstraction, all downstream tests must use real AVAudioRecorder which requires simulator hardware. This is the foundation for every other test. Past pattern: iOS7 BiometricService used BiometricAuthenticating protocol -- same pattern required here.

#### T2: test_recording_start_creates_m4a_file
- **Spec ref:** Phase iOS8 deliverable 1 (m4a format)
- **Category:** Behavioral
- **Setup:** Mock AudioRecording protocol
- **Action:** Call startRecording()
- **Expected:** Recorder is called with settings for m4a (kAudioFormatMPEG4AAC), state transitions to .recording, file URL has .m4a extension
- **Why:** Wrong format would fail backend validation (audio/mp4 MIME type required)

#### T3: test_recording_stop_returns_audio_url
- **Spec ref:** Phase iOS8 deliverable 1
- **Category:** Behavioral
- **Setup:** Mock recorder in recording state
- **Action:** Call stopRecording()
- **Expected:** Returns a file URL to the recorded audio, state transitions to .idle or .stopped
- **Why:** No URL = nothing to upload

#### T4: test_microphone_permission_denied_surfaces_error
- **Spec ref:** Phase iOS8 deliverable 3
- **Category:** Behavioral (negative path)
- **Setup:** Mock AVAudioApplication/AVAudioSession to return .denied permission status
- **Action:** Attempt to start recording
- **Expected:** Recording does NOT start. An error/state is surfaced (e.g., VoiceViewModel.permissionDenied = true or VoiceError.microphonePermissionDenied thrown). No silent failure.
- **Why:** Silent permission denial means user taps record, nothing happens, no feedback. This is a UX and security concern -- spec requires explicit permission handling.

#### T5: test_microphone_permission_not_determined_requests_permission
- **Spec ref:** Phase iOS8 deliverable 3
- **Category:** Behavioral
- **Setup:** Mock permission status as .notDetermined
- **Action:** Attempt to start recording
- **Expected:** Permission request is triggered (mock verifies requestRecordPermission() called). Recording does NOT start until permission is granted.
- **Why:** First-time users must see the system prompt. Starting recording without permission crashes.

#### T6: test_max_duration_enforced_at_10_minutes
- **Spec ref:** Phase iOS8 deliverable 7
- **Category:** Behavioral (boundary)
- **Setup:** Mock recorder, start recording
- **Action:** Simulate 10 minutes elapsed (timer fires or duration check triggers)
- **Expected:** Recording automatically stops. Audio file is available for upload. State transitions to stopped/ready. No crash, no data loss.
- **Why:** Spec explicitly requires "Max 10 min recording duration". If not enforced, users could create arbitrarily large files that exceed the 25MB backend limit.

#### T7: test_upload_sends_multipart_form_data
- **Spec ref:** Phase iOS8 deliverable 6, backend contract from iOS2
- **Category:** Integration (contract)
- **Setup:** Mock URLSession or APIClient extension. Provide a fake audio file URL.
- **Action:** Call VoiceService.upload(audioURL:mode:)
- **Expected:** Request is multipart/form-data with: (a) field name "file" containing audio bytes with MIME type "audio/mp4", (b) field name "mode" with value "transcribe" or "chat", (c) endpoint is /api/v1/voice/transcribe, (d) Authorization header present, (e) method is POST
- **Why:** Multipart encoding must match exactly what FastAPI's UploadFile + Form expects. Wrong field names = 422 Unprocessable Entity. This is the most common integration failure point.

#### T8: test_upload_decodes_voice_upload_response
- **Spec ref:** Phase iOS8 deliverable 6, VoiceUploadResponse schema
- **Category:** Integration (contract)
- **Setup:** Mock HTTP response with JSON: `{"text": "Hello world", "mode": "transcribe", "thread_id": null}`
- **Action:** Call VoiceService.upload(), decode response
- **Expected:** Returns a Swift model with text="Hello world", mode="transcribe", threadId=nil. Also test chat mode response: `{"text": "Remind me", "mode": "chat", "thread_id": "uuid-string"}` decodes with non-nil threadId.
- **Why:** Response shape must match VoiceUploadResponse from backend. Field name mapping (snake_case to camelCase) is a common source of decode failures.

#### T9: test_cancel_discards_recording
- **Spec ref:** Phase iOS8 planned test "cancel/discard"
- **Category:** Behavioral
- **Setup:** Start recording via mock
- **Action:** Call cancel() or discard()
- **Expected:** Recording stops, temporary audio file is deleted (cleanup), state returns to idle, no upload is triggered
- **Why:** Without cleanup, temporary files accumulate in the app sandbox. Without state reset, the UI could be stuck in recording state.

#### T10: test_auto_send_feeds_transcription_to_chat
- **Spec ref:** Phase iOS8 deliverable 6 ("auto-send to chat")
- **Category:** Integration
- **Setup:** VoiceViewModel with mock VoiceService that returns VoiceUploadResponse(text="Buy milk", mode="chat", threadId=uuid). Mock or spy on ChatViewModel.
- **Action:** Record, stop, upload completes in chat mode
- **Expected:** ChatViewModel.sendMessage is called with text="Buy milk" and the returned threadId. The transcribed text appears in the chat.
- **Why:** This is the core feature -- voice to chat. If auto-send is broken, voice is just a transcription tool with no chat integration. Past pattern (iOS5 review): field mismatches between services silently drop data.

#### T11: test_upload_failure_surfaces_error
- **Spec ref:** Phase iOS8 deliverable 6 (negative path)
- **Category:** Behavioral (negative path)
- **Setup:** Mock VoiceService to throw an error (network failure, 502 from backend, timeout)
- **Action:** Attempt upload after recording
- **Expected:** VoiceViewModel.errorMessage is set with a meaningful message. State returns to idle (not stuck in "uploading"). User can retry.
- **Why:** Backend may return 502 (Whisper API down), 503 (OPENAI_API_KEY not configured), 400 (bad audio). Silent failure = user records, nothing happens. Past pattern: `try?` silently dropping errors was a blocking issue in iOS5.

#### T12: test_voice_view_model_state_machine
- **Spec ref:** Phase iOS8 deliverables 4, 5
- **Category:** Behavioral
- **Setup:** VoiceViewModel with mocked services
- **Action:** Walk through the full lifecycle: idle -> permission check -> recording -> stopped -> uploading -> transcribed/sent -> idle
- **Expected:** State transitions are correct at each step. isRecording, isUploading, transcribedText, elapsedTime all update properly. No invalid state transitions (e.g., uploading while recording).
- **Why:** The UI (waveform, timer, button state) all bind to ViewModel state. Wrong states = broken UI.

### NICE-TO-HAVE Tests

#### T13: test_recording_timer_updates_elapsed_time
- **Spec ref:** Phase iOS8 deliverable 5 (timer visualization)
- **Category:** Behavioral
- **Setup:** VoiceViewModel, mock recorder
- **Action:** Start recording, advance time
- **Expected:** elapsedTime property updates (e.g., from 0 to some value). Timer granularity is reasonable (updates at least once per second).
- **Why:** Timer display is a UX requirement but not a correctness concern.

#### T14: test_audio_player_play_and_pause
- **Spec ref:** Phase iOS8 deliverable 2
- **Category:** Behavioral
- **Setup:** Mock AudioPlayerService with protocol
- **Action:** Call play(url:), then pause()
- **Expected:** Player state transitions: idle -> playing -> paused. URL is passed correctly.
- **Why:** Playback is listed as a deliverable but is secondary to recording+upload flow.

#### T15: test_concurrent_recording_prevented
- **Spec ref:** Defensive
- **Category:** Behavioral (edge case)
- **Setup:** VoiceViewModel in recording state
- **Action:** Call startRecording() again
- **Expected:** Second call is no-op or throws. Only one recording at a time.
- **Why:** Double-tap could corrupt audio or create orphaned file handles.

#### T16: test_upload_respects_25mb_client_side_limit
- **Spec ref:** Backend validation.py MAX_AUDIO_SIZE_BYTES = 25MB
- **Category:** Behavioral (boundary)
- **Setup:** Create a mock audio file reference > 25MB
- **Action:** Attempt upload
- **Expected:** Client rejects before sending (saves bandwidth), or backend returns 400 and client surfaces it
- **Why:** 10 min of m4a at typical bitrate is ~5-10MB, well under limit, but edge case with high quality settings could approach it.

#### T17: test_voice_button_disabled_during_streaming
- **Spec ref:** Phase iOS8 deliverable 4 (ComposerBar)
- **Category:** Behavioral (edge case)
- **Setup:** ChatViewModel.isStreaming = true
- **Action:** Check voice button state
- **Expected:** Voice button is disabled (same as send button behavior in current ComposerBar)
- **Why:** Recording during SSE streaming would create confusing UX.

## Security Test Requirements

1. **T5 (permission handling):** Microphone access must go through the system permission flow. No bypass, no silent access.
2. **T7 (auth header):** Upload request MUST include Authorization: Bearer token. Unauthenticated uploads must fail.
3. **Temporary file cleanup (T9):** Recorded audio files must be cleaned up after upload or cancel. Audio left in the sandbox is a privacy concern -- the user's voice recordings should not persist unnecessarily.
4. **No `try?` on upload errors (T11):** iOS5 review found `try?` silently dropping SSE decode errors. Same pattern is likely here. Upload errors MUST throw, not be silently swallowed.

## Integration Test Requirements

The following MUST be tested without mocks at the Swift layer (mocking only the HTTP boundary):

1. **T10 (auto-send flow):** VoiceViewModel -> VoiceService -> ChatViewModel. Real Swift objects, mock only the URLSession response. This tests the actual wiring between voice and chat.
2. **T8 (response decoding):** Real JSONDecoder against the exact JSON shape the backend produces. Not a mock model -- actual JSON bytes in, Swift model out.

## Python Backend Contract Tests

Add to `tests/unit/test_ios8_voice_contract.py` (or extend test_ios2_voice.py):

#### T18: test_voice_upload_response_json_shape_matches_swift_model
- **Category:** Contract
- **Setup:** Create VoiceUploadResponse from backend schemas
- **Action:** Serialize to JSON, verify field names
- **Expected:** JSON has exactly: `text` (string), `mode` ("transcribe"|"chat"), `thread_id` (string|null). No extra fields. snake_case keys.
- **Why:** Swift model must decode this exactly. Past pattern (iOS5): field name mismatches ("payload['text']" vs "payload['response']") caused blocking issues.

#### T19: test_m4a_mime_type_accepted_by_validation
- **Category:** Contract
- **Setup:** Call validate_audio with content_type="audio/mp4"
- **Action:** Should not raise
- **Expected:** Pass
- **Why:** iOS records as m4a which maps to audio/mp4. If backend rejects this MIME type, the entire voice feature is broken.

## Anti-Patterns to Watch For

Based on past retros and audit findings:

1. **`try?` on decode/upload (iOS5 pattern):** VoiceService or VoiceViewModel using `try?` to silently discard upload failures or decode errors. MUST throw on failure.

2. **APIClient bypass without auth (RC1 pattern):** If VoiceService uses raw URLSession instead of APIClient for multipart, it might forget to add the Authorization header. Check that token injection happens.

3. **Protocol-less AVFoundation wrappers:** If AudioRecorderService directly instantiates AVAudioRecorder without a protocol, tests will require a simulator and will be fragile/untestable. iOS7 got this right with BiometricAuthenticating -- same pattern required.

4. **"Wired in ViewModel, not in view" pattern:** VoiceViewModel exists but ComposerBar or ChatView never instantiates or injects it. Check that the ViewModel is actually created and passed to the view hierarchy.

5. **State machine holes:** VoiceViewModel has states (idle, recording, uploading, done) but no guard against invalid transitions (e.g., upload while still recording). The `isStreaming` guard in ChatViewModel is a good model -- same discipline required here.

6. **Hardcoded file paths:** Temporary audio files should use `FileManager.default.temporaryDirectory`, not hardcoded paths. Hardcoded paths fail on different devices/simulators.

7. **Missing cleanup on app backgrounding:** AVAudioRecorder may stop when the app backgrounds (no background audio entitlement). If the recording is in progress and the app backgrounds, the state must be cleaned up gracefully -- not left as "recording" with a dead recorder.

8. **Timer using wall-clock time:** If elapsed time is computed from `Date()` rather than a `Timer`/`CADisplayLink`, tests become non-deterministic. Prefer injectable time source or timer-based counting.

9. **Multipart boundary format:** Hand-rolled multipart encoding is error-prone. If the developer builds the multipart body manually (not using URLSession's built-in multipart support), verify the boundary, Content-Disposition field names, and CRLF line endings exactly match what the server expects.

10. **Response envelope confusion:** Backend voice endpoint returns a flat `VoiceUploadResponse`, NOT wrapped in the standard `{ok, data, error}` envelope (the endpoint returns the Pydantic model directly via FastAPI). The Swift decode must handle this -- if it expects ApiResponse<VoiceUploadResponse>, it will fail. Check: does the voice endpoint use the standard envelope or return raw?
