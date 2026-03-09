# Test Plan: Phase iOS2 — Voice Upload Endpoint

**Date:** 2026-03-08
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §29.3 (Mobile Access — Voice), §36.3 item 3 (Voice recording and playback)

## Summary

This phase adds a voice transcription endpoint (`POST /api/v1/voice/transcribe`) that accepts multipart audio uploads, validates format/size, calls OpenAI Whisper API, optionally pipes transcription into the chat pipeline, and stores the original audio as an artifact. The key testing risks are: (1) multipart upload validation bypasses (MIME spoofing, oversize files), (2) Whisper API error handling (network failures, rate limits, malformed responses), (3) the chat-pipe mode correctly producing SSE output, (4) wiring — the new voice router must be registered in `app.py` and the TranscriptionService must be instantiated, and (5) artifact storage actually persisting (not write-only).

## Test Specifications

### MUST-HAVE Tests

#### T1: test_transcribe_valid_audio_returns_text
- **Spec ref:** SPEC.md §29.3 Phase 2 — "Voice: Record audio, send to backend for processing"
- **Category:** Behavioral
- **Setup:** Mock Whisper API to return `{"text": "Hello world"}`. Create a valid m4a file fixture.
- **Action:** POST multipart/form-data to `/api/v1/voice/transcribe` with authenticated user, valid audio file, `mode=transcribe`.
- **Expected:** HTTP 200, JSON response containing `{"ok": true, "data": {"text": "Hello world", ...}}`. Response must follow L5 envelope schema.
- **Why:** Core happy path. If this fails, the entire voice feature is broken.

#### T2: test_transcribe_rejects_oversized_file
- **Spec ref:** Phase plan — "max 25MB"
- **Category:** Behavioral (negative)
- **Setup:** Create a file >25MB (or mock file size check).
- **Action:** POST to `/api/v1/voice/transcribe` with oversized file.
- **Expected:** HTTP 413 (Payload Too Large) with error envelope `{"ok": false, "error": {"code": "FILE_TOO_LARGE", ...}}`.
- **Why:** Without size validation, an attacker can exhaust server memory/disk by uploading huge files. The 413 status code is semantically correct (not 400).

#### T3: test_transcribe_rejects_unsupported_mime_type
- **Spec ref:** Phase plan — "allowed MIME types (m4a, wav, mp3)"
- **Category:** Behavioral (negative / security)
- **Setup:** Upload a file with `content_type="application/pdf"` or `"text/plain"`.
- **Action:** POST to `/api/v1/voice/transcribe` with disallowed MIME type.
- **Expected:** HTTP 415 (Unsupported Media Type) with error envelope containing a specific error code like `UNSUPPORTED_AUDIO_FORMAT`.
- **Why:** Prevents uploading arbitrary files (executables, scripts) that could be stored as artifacts. The allow-list approach (m4a/wav/mp3 only) is critical for security.

#### T4: test_transcribe_requires_authentication
- **Spec ref:** SPEC.md §5.1 — all API endpoints require auth unless explicitly public
- **Category:** Security
- **Setup:** No auth token provided.
- **Action:** POST to `/api/v1/voice/transcribe` without Authorization header.
- **Expected:** HTTP 401 Unauthorized.
- **Why:** Voice upload is a write operation that creates artifacts and can trigger chat runs. Unauthenticated access must be rejected.

#### T5: test_transcription_service_handles_whisper_api_failure
- **Spec ref:** Phase plan — "Error handling: Whisper API failure returns proper error envelope"
- **Category:** Behavioral (error path)
- **Setup:** Mock httpx client to raise `httpx.HTTPStatusError` (e.g., 500 from Whisper API) or `httpx.ConnectError`.
- **Action:** Call `TranscriptionService.transcribe(audio_bytes, mime_type)`.
- **Expected:** Raises a specific exception (e.g., `TranscriptionError`) with a meaningful message — NOT silently swallowed, NOT returning empty string. The endpoint must catch this and return HTTP 502 or 503 with error envelope.
- **Why:** L9 requires no silent error swallowing. Whisper API can fail for many reasons (rate limit, invalid audio, network). User must get a clear error, not silence.

#### T6: test_transcription_service_calls_whisper_api_correctly
- **Spec ref:** Phase plan — "TranscriptionService using OpenAI Whisper API"
- **Category:** Behavioral
- **Setup:** Mock httpx client, capture the outgoing request.
- **Action:** Call `TranscriptionService.transcribe(audio_bytes, "audio/mpeg")`.
- **Expected:** httpx sends POST to `https://api.openai.com/v1/audio/transcriptions` with: multipart form-data containing the audio file, `model` field set to configured Whisper model, `Authorization: Bearer {openai_api_key}` header. The service parses the response JSON and returns the `text` field.
- **Why:** Verifies the Whisper API integration contract. Wrong URL, wrong auth, wrong model = silent failure in production.

#### T7: test_transcribe_with_chat_mode_returns_sse_stream
- **Spec ref:** Phase plan — "Optional mode: feed transcription directly into chat pipeline (returns SSE stream)"
- **Category:** Integration
- **Setup:** Mock Whisper API to return transcription text. Mock or stub the OrchestratorRunner. Set `mode=chat` in request.
- **Action:** POST to `/api/v1/voice/transcribe` with `mode=chat`, valid audio, and required chat params (privacy_mode, model, provider).
- **Expected:** HTTP 200 with `Content-Type: text/event-stream`. Response body contains SSE frames. The transcribed text is used as the chat message.
- **Why:** This is the key differentiator for voice — speak and get a streaming AI response. If the SSE plumbing is wrong, the iOS client will hang waiting for data.

#### T8: test_transcribe_creates_artifact_for_audio_file
- **Spec ref:** Phase plan — "Artifact storage for original audio file"
- **Category:** Behavioral
- **Setup:** Mock Whisper API. Provide a valid audio file. Mock or use in-memory DB for artifact storage.
- **Action:** POST to `/api/v1/voice/transcribe` with valid audio.
- **Expected:** An `Artifact` record is created with: `type="audio"`, `mime_type` matching the upload, `size_bytes` matching the file size, `storage_ref` pointing to a valid location, and `name` derived from the original filename or a generated name.
- **Why:** The spec requires audio artifacts to be stored. If this is write-only (artifact created but never retrievable), it's incomplete — but at minimum the write path must work.

#### T9: test_voice_router_registered_in_app
- **Spec ref:** ARCH_INVARIANTS L10 — wiring completeness
- **Category:** Invariant (wiring)
- **Setup:** Import `create_app` from `noa.api.app`.
- **Action:** Create the app, inspect `app.routes` for voice endpoint paths.
- **Expected:** `/api/v1/voice/transcribe` appears in the app's registered routes.
- **Why:** This is the #1 failure mode in this codebase (see MEMORY.md — "wired in class, not in app" pattern from QC5, QC8, HD). If the router is not registered, the endpoint is unreachable despite having code and passing tests.

#### T10: test_whisper_api_key_required
- **Spec ref:** ARCH_INVARIANTS L11 — no fallback defaults on secrets
- **Category:** Security
- **Setup:** No `OPENAI_API_KEY` configured (or empty string).
- **Action:** Attempt to call `TranscriptionService.transcribe()` or instantiate the service.
- **Expected:** Either (a) service refuses to instantiate (raises at startup), or (b) transcribe call fails with a clear error indicating missing API key — NOT a silent empty-string auth header sent to Whisper API.
- **Why:** L11 forbids `secret_key or ""` patterns. An empty API key sent to Whisper API will get a 401, but the error message will be opaque ("invalid API key") instead of "OPENAI_API_KEY not configured".

#### T11: test_transcribe_with_empty_audio_file
- **Spec ref:** M2 — negative test for boundary
- **Category:** Behavioral (edge case)
- **Setup:** Upload a 0-byte file with valid MIME type.
- **Action:** POST to `/api/v1/voice/transcribe` with empty file.
- **Expected:** HTTP 400 (Bad Request) with error code like `EMPTY_AUDIO_FILE`. Must NOT forward a 0-byte file to Whisper API (wastes API call, may crash).
- **Why:** Empty files are a common edge case that can cause downstream errors. Catching it early provides a better user experience.

#### T12: test_config_has_whisper_settings
- **Spec ref:** Phase plan — "Add WHISPER_MODEL, MAX_AUDIO_SIZE_MB settings"
- **Category:** Invariant
- **Setup:** Import `Settings` from `noa.config`.
- **Action:** Instantiate `Settings()`.
- **Expected:** `settings.whisper_model` exists (default: `"whisper-1"` or similar), `settings.max_audio_size_mb` exists (default: `25`). These are NOT secrets, so defaults are acceptable.
- **Why:** Config must be validated at startup per L7. Missing config fields cause AttributeError at runtime.

### NICE-TO-HAVE Tests

#### T13: test_transcribe_mime_type_spoofing
- **Spec ref:** M3 — security boundaries
- **Category:** Security (defense-in-depth)
- **Setup:** Upload a text file with `content_type="audio/mpeg"` (spoofed MIME type).
- **Action:** POST to `/api/v1/voice/transcribe`.
- **Expected:** Ideally, the server performs content-based validation (magic bytes check) and rejects the file. At minimum, the Whisper API error should be caught gracefully (not crash the endpoint).
- **Why:** MIME type headers are client-controlled and easily spoofed. Content validation prevents abuse. This is defense-in-depth — not strictly required by the phase plan but important.

#### T14: test_transcribe_concurrent_requests_idempotency
- **Spec ref:** Phase plan — "idempotency"
- **Category:** Behavioral
- **Setup:** Submit two requests with the same `Idempotency-Key` header.
- **Action:** POST twice with identical idempotency key.
- **Expected:** Second request returns HTTP 409 (Conflict) with `DUPLICATE_REQUEST` error code, matching the pattern in `chat.py`.
- **Why:** Voice uploads are expensive (Whisper API call + artifact storage). Duplicate prevention avoids wasting resources and billing.

#### T15: test_transcribe_all_supported_formats
- **Spec ref:** Phase plan — "m4a, wav, mp3"
- **Category:** Behavioral (parametrized)
- **Setup:** Create small valid audio files (or mock) for each format.
- **Action:** POST each format to the transcribe endpoint.
- **Expected:** All three formats accepted (HTTP 200). MIME types validated: `audio/mp4` or `audio/x-m4a` for m4a, `audio/wav` or `audio/x-wav` for wav, `audio/mpeg` for mp3.
- **Why:** The phase plan lists three specific formats. Testing only one leaves two potentially broken.

#### T16: test_transcribe_whisper_rate_limit_retry
- **Spec ref:** Robustness
- **Category:** Behavioral (error handling)
- **Setup:** Mock Whisper API to return 429 (Rate Limited) on first call, 200 on retry.
- **Action:** Call `TranscriptionService.transcribe()`.
- **Expected:** Service retries after backoff and returns successful transcription. If no retry is implemented, at minimum the 429 error is surfaced as a clear error to the user (not a generic 500).
- **Why:** Whisper API rate limits are common with heavy usage. Graceful degradation is important.

#### T17: test_chat_mode_requires_chat_params
- **Spec ref:** Phase plan — chat pipeline integration
- **Category:** Behavioral (negative)
- **Setup:** Set `mode=chat` but omit required chat parameters (privacy_mode, model, provider).
- **Action:** POST to `/api/v1/voice/transcribe` with `mode=chat` but missing params.
- **Expected:** HTTP 422 (Validation Error) listing the missing fields.
- **Why:** Prevents confusing errors deep in the chat pipeline when required params are missing.

## Security Test Requirements

1. **T4 (auth required)** — unauthenticated access rejected
2. **T10 (API key required)** — no fallback defaults on Whisper API key
3. **T3 (MIME type validation)** — allow-list, not deny-list, for audio formats
4. **T2 (size validation)** — prevents resource exhaustion attacks
5. **T13 (MIME spoofing)** — content-based validation if feasible
6. Verify that uploaded audio files are stored with randomized/non-guessable `storage_ref` paths — NOT using user-supplied filenames directly (path traversal prevention)

## Integration Test Requirements

At minimum one test (T9) must verify wiring without mocks:
- Import `create_app()`, check that `/api/v1/voice/transcribe` is a registered route
- Import `TranscriptionService` and verify it can be instantiated (with mock API key)
- Verify `Settings` includes the new whisper config fields

The chat-mode integration (T7) ideally tests the full path: upload -> transcribe -> chat pipeline invocation (with mocked LLM but real wiring between voice endpoint and chat).

## Anti-Patterns to Watch For

Based on past retros and MEMORY.md findings:

1. **"Wired in class, not in app"** (QC5/QC8/HD pattern): The voice router is created in `src/noa/api/v1/voice.py` but never imported or registered in `app.py`. Tests pass because they test the router directly. This is the single most likely failure mode.

2. **Write-only persistence** (HD cycle 2 pattern): Artifact is created for the audio file, but no code path ever reads it back. Check that artifact creation includes a real `storage_ref` that could be used to retrieve the file.

3. **Silent error swallowing** (RC7): `except Exception: pass` in the transcription service. Whisper API errors must propagate to the user.

4. **Source inspection tests** (QC2 pattern): Tests that check `inspect.getsource()` for Whisper API calls instead of actually calling the service with mocked httpx. Prefer behavioral tests.

5. **Missing config validation** (L7/L11): `openai_api_key` already exists in `config.py` as `str | None = None` — the TranscriptionService must validate at usage time that it's not None, not silently send `Authorization: Bearer None`.

6. **Dual-path ambiguity in chat mode**: The endpoint might return SSE for `mode=chat` and JSON for `mode=transcribe`. Verify the Content-Type header matches the mode. A bug where `mode=chat` returns JSON (or vice versa) would break the iOS client.

7. **Artifact requires run_id**: The `Artifact` model has a non-nullable `run_id` FK. In transcribe-only mode (no chat/run), how is the artifact linked? The phase must either: (a) create a lightweight run for the transcription, or (b) make `run_id` nullable for voice artifacts. This is an implicit spec gap the developer must resolve — test that artifact creation works in BOTH modes.
