# QA Review: Wave 15A (iOS1 + iOS2)

**Date:** 2026-03-08
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 5/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All test classes have docstrings citing SPEC.md or phase plan |
| M2 | Negative Tests | PASS | Size, MIME, expired token, invalid token, unauth tests present |
| M3 | Security Boundaries | PASS | PushPayload extra=forbid, auth required on endpoints, API key validated at use |
| M4 | Determinism | PASS | No wall-clock time in test assertions; batcher tests use window=0 trick |
| M5 | Implementation Completeness | **FAIL** | 4 missing deliverables (see Blocking Issues) |
| M6 | No Silent Error Swallowing | PASS | except Exception blocks log or re-raise |
| M7 | Wiring Completeness | **FAIL** | APNsService and ApprovalBatcher are orphaned (L10 violation) |
| M8 | Domain Isolation | PASS | No cross-domain imports detected |
| S1 | Error Handling & Boundaries | OPEN | No validation on empty push_token, empty device_id, or platform values |
| S2 | Code Consistency | PASS | Naming conventions followed, layering correct |
| S3 | Migration & Rollback | PASS | Migration 008 has proper downgrade() |
| S4 | Documentation | PASS | All public functions have type annotations and docstrings |
| S5 | Integration Smoke Test | OPEN | Auth tests use real ASGI transport (good), but no integration test for push-to-approval or voice-to-chat flow |

## Test Plan Coverage

The test plans (test-plan_iOS1.md and test-plan_iOS2.md) identified 29 MUST-HAVE tests across both phases. Of these:

**iOS1 test plan vs actual tests (23 MUST-HAVE planned, 20 tests written):**

| Test Plan ID | Status | Notes |
|---|---|---|
| T1 (register success) | Weak | Only tests schema construction, not actual DB write |
| T2 (upsert duplicate) | Weak | Only tests schema, not actual upsert behavior |
| T3 (delete success) | Weak | Only tests schema, not actual DB delete |
| T4 (register unauth) | PRESENT | Real ASGI transport, 401 check |
| T5 (delete unauth) | PRESENT | Real ASGI transport, 401 check |
| T6 (payload allowed fields) | PRESENT | Asserts exact key set |
| T7 (notification type values) | PRESENT | Tests all three types |
| T8 (HTTP/2 send mock) | Partial | Tests construction only, not the actual POST call |
| T9 (JWT token generation) | MISSING | No JWT generation test -- APNsService does not implement JWT signing |
| T10 (expired token 410) | PRESENT | Mocked HTTP response |
| T11 (invalid token 400) | PRESENT | Mocked HTTP response |
| T12 (batcher within window) | PRESENT | |
| T13 (batcher outside window) | PRESENT | Uses window=0 |
| T14 (no cross-domain batching) | PRESENT | |
| T15 (push on approval) | Weak | Only tests PushPayload construction, not approval-to-push integration |
| T16 (push on run_completed) | Weak | Only tests PushPayload construction |
| T17 (push on run_failed) | Weak | Only tests PushPayload construction |
| T18 (no push low-risk) | PRESENT | Tests should_notify() |
| T19 (config no fallback) | N/A | APNs is optional; None defaults are acceptable |
| T20 (migration 008) | Not tested directly | But migration file exists and is correct |
| T22 (router registered) | Not explicitly tested | But verified by smoke test |
| T23 (APNsService at startup) | MISSING | APNsService is never instantiated at startup |

**iOS2 test plan vs actual tests (12 MUST-HAVE planned, 17 tests written):**

| Test Plan ID | Status | Notes |
|---|---|---|
| T1 (transcribe returns text) | PRESENT | |
| T2 (reject oversized) | PRESENT | |
| T3 (reject bad MIME) | PRESENT | |
| T4 (auth required) | Partial | Router exists and has require_auth, but no ASGI test |
| T5 (API error handling) | PRESENT | Tests TranscriptionError |
| T6 (Whisper API call) | PRESENT | Checks endpoint URL in call |
| T7 (chat mode SSE) | Weak | Only tests VoiceUploadResponse schema, not actual SSE streaming |
| T8 (artifact creation) | MISSING | No artifact storage test -- feature not implemented |
| T9 (router registered) | Partial | Tests router import but not registration in app.py |
| T10 (API key required) | Covered | Endpoint checks OPENAI_API_KEY at line 58-62 |
| T11 (empty audio) | MISSING | No empty file test |
| T12 (config settings) | PRESENT | |

## Spec Compliance

### SPEC.md SS29.5 (Push Notifications)
- Payload contains only notification_type, request_id, risk_tier: **COMPLIANT** (PushPayload extra=forbid)
- No task content, tool names, or private data: **COMPLIANT**

### SPEC.md SS23.2 (Approval Batching)
- 30-second configurable window: **COMPLIANT** (ApprovalBatcher accepts window_seconds param)
- Single notification per batch: **IMPLEMENTED** in batcher, but **NOT WIRED** to any caller
- No cross-domain batching: **COMPLIANT** (domain key in batcher)

### SPEC.md SS29.3 (Voice)
- Record audio, send to backend for processing: **PARTIALLY COMPLIANT** (transcribe-only mode works)
- Chat mode (stream response): **NOT IMPLEMENTED** (endpoint always returns mode="transcribe")
- Artifact storage: **NOT IMPLEMENTED**

### SPEC.md SS29.6 (Approval Flow)
- Push notification sent on approval_requested: **NOT WIRED** (no hook in approval.py)

## Test Coverage

37 tests total (20 iOS1 + 17 iOS2). All pass.

**Critical gaps:**
1. Several iOS1 "integration" tests only test schema/model construction, not actual service/endpoint behavior. Tests T15-T17 (push triggers) construct PushPayload objects directly instead of testing the approval-to-push wiring.
2. No iOS2 test exercises the actual endpoint through ASGI transport (like iOS1 auth tests do).
3. No test for chat mode producing SSE output.
4. No test for artifact creation.

## Anti-Pattern Scan Results

**M6 (bare except / blind exception):**
- `src/noa/push/apns.py:97`: `except Exception:` -- has `logger.exception()`, PASSES L9
- `src/noa/voice/transcription.py:58`: `except Exception as exc:` -- re-raises as TranscriptionError, PASSES L9

**M7 (wiring -- routers registered):**
- `app.py:343`: `app.include_router(devices_router)` -- REGISTERED
- `app.py:344`: `app.include_router(voice_router, prefix="/api/v1/voice")` -- REGISTERED
- `APNsService`: NOT imported in app.py, NOT instantiated at startup -- **L10 VIOLATION**
- `ApprovalBatcher`: NOT imported anywhere in production code -- **L10 VIOLATION**

**M8 (domain isolation):**
- No `from noa.private_worker` in `src/noa/external_worker/`: CLEAN
- No `from noa.external_worker` in `src/noa/private_worker/`: CLEAN

## Smoke Test Results

```
OK: push.schemas imports
OK: push.apns imports
OK: push.batcher imports
OK: db.models.device_token imports
OK: devices router imported, routes: ['/api/v1/devices/push-token', '/api/v1/devices/push-token']
OK: voice.schemas imports
OK: voice.transcription imports
OK: voice.validation imports, MIME types: frozenset({'audio/mpeg', 'audio/mp4', 'audio/ogg', 'audio/flac', 'audio/webm', 'audio/wav', 'audio/x-wav'})
OK: voice router imported, routes: ['/transcribe']
OK: config.apns_key_id=None, apns_team_id=None
OK: config.whisper_model=whisper-1, max_audio_size_mb=25
OK: APNs config defaults to None (optional service)
OK: Both routers registered in app.py
OK: PushPayload rejects extra fields (extra=forbid)
OK: validate_audio rejects unsupported MIME types
OK: validate_audio rejects oversized files
OK: TranscriptionError is an Exception subclass
OK: Batcher isolates private and external domains

=== ALL SMOKE TESTS PASSED ===
```

All 37 tests pass: `37 passed, 2 warnings in 0.27s`

## Security

1. **PushPayload extra=forbid**: Correctly prevents private data leakage. GOOD.
2. **Auth on endpoints**: Both devices and voice endpoints use `require_auth`. GOOD.
3. **OPENAI_API_KEY validation**: Voice endpoint checks for empty key at line 58-62 and returns 503. GOOD. Not a fallback default -- it actively rejects empty values.
4. **APNs config as Optional (None)**: Acceptable because APNs is an optional service. The service constructor takes explicit required strings. If someone creates APNsService with empty strings, it would fail at Apple's end -- but it cannot accidentally send to the wrong endpoint.
5. **No hardcoded secrets**: All API keys are from environment. GOOD.

## Code Quality

1. **Inline imports in voice.py** (lines 54-56): `import os` and `import httpx` inside the endpoint function. Should be at module level. Non-blocking.
2. **MAX_AUDIO_SIZE_BYTES hardcoded in validation.py**: Config has `max_audio_size_mb = 25` but validation.py uses its own `25 * 1024 * 1024` constant. The config setting is disconnected. Non-blocking but means the config setting does nothing.
3. **voice.py creates a new httpx.AsyncClient per request** (line 65): Should be shared or injected. Each request creates and destroys a client. Non-blocking for correctness but poor for performance.
4. **APNsService._http_client is never set**: The constructor initializes `self._http_client = None` but no code ever sets it to an actual HTTP client. In production, `send()` would always return `SendResult(success=False, reason="no_client")`. This is a consequence of the missing startup wiring.
5. **DeviceTokenRequest accepts any string for platform**: No enum validation. Accepts "windows", "android", arbitrary strings. Non-blocking (S1).
6. **No validation for empty push_token or device_id**: Empty strings accepted. Non-blocking (S1).

## Beyond the Test Plan

1. **voice.py HTTP status codes**: Oversized files return HTTP 400 (via ValueError catch at line 49), not 413 as semantically expected. The test plan called for 413 but the test (test_reject_oversized_audio) only tests the validation module directly (ValueError), not the endpoint's HTTP response code. The endpoint maps all ValueError to 400.
2. **voice.py has no mode parameter**: The endpoint signature only accepts `file` and `payload` (auth). There's no `mode` query parameter. It always returns `mode="transcribe"`. The chat pipeline integration from the phase plan (deliverable 4) is not implemented.
3. **APNsService has no JWT signing**: The spec says "JWT-based auth" for APNs (deliverable 5). The service takes key_id, team_id, key_path but never generates a JWT. The `send()` method sends no `authorization` header. In production, Apple would reject every request.
4. **Batcher uses time.monotonic() directly**: Not injectable. Tests work around this with window=0, which is clever but doesn't test the actual timing behavior. The test plan T12 explicitly called for "injected clock, NOT real time." This is acceptable since the tests don't depend on wall-clock time, but the batcher is not testable for precise window behavior.

## Blocking Issues

1. **M5: APNsService and ApprovalBatcher are orphaned code (L10 violation)**
   - `APNsService` is defined in `src/noa/push/apns.py` but never imported by `app.py` or any other production module
   - `ApprovalBatcher` is defined in `src/noa/push/batcher.py` but never imported by any production module
   - Neither is wired to the approval service or run service as required by phase plan deliverable 8: "Integration hooks in approval service and run service for push triggers"
   - Files: `src/noa/api/app.py` (no APNsService), `src/noa/policy/approval.py` (no push hook), `src/noa/runs/service.py` (no push hook)

2. **M5: Voice chat mode not implemented**
   - Phase plan deliverable 4: "Optional mode: feed transcription directly into chat pipeline (returns SSE stream)"
   - The endpoint has no `mode` parameter and always returns `mode="transcribe"`
   - File: `src/noa/api/v1/voice.py` -- no chat pipeline integration

3. **M5: Voice artifact storage not implemented**
   - Phase plan deliverable 5: "Artifact storage for original audio file"
   - No artifact creation code exists in the voice endpoint
   - File: `src/noa/api/v1/voice.py` -- no artifact import or creation

4. **M7: APNsService._http_client never initialized**
   - `__init__` sets `self._http_client = None` at `src/noa/push/apns.py:59`
   - No code ever sets it to a real HTTP client
   - `send()` at line 84-86 returns immediate failure: `SendResult(success=False, reason="no_client")`
   - This means push notifications can never be sent even if the service were wired

## Notes

1. The router registration for both `devices_router` and `voice_router` in `app.py` is correct. The endpoint-level wiring is done; it's the service-level wiring that is missing.
2. The PushPayload schema with `extra=forbid` is an excellent security pattern for preventing private data leakage. Well done.
3. The ApprovalBatcher domain isolation design is correct and well-structured.
4. The TranscriptionService design with injected httpx client is good for testability.
5. The voice endpoint's API key validation at use-time (not startup) is acceptable since transcription is optional.
6. Consider using HTTP 413 (Payload Too Large) instead of 400 for oversized audio files.
7. Consider using HTTP 415 (Unsupported Media Type) instead of 400 for invalid MIME types.
8. `max_audio_size_mb` in config is unused -- validation.py has its own hardcoded constant.

## Decision Review

The implementation delivers correct schemas, models, and validation logic but falls short on integration. The four blocking issues all follow the same pattern identified in MEMORY.md as "wired in class, not in app" -- the most recurring anti-pattern in this codebase. The classes exist and are well-designed, but they are disconnected from the running application. Tests pass because they test the classes in isolation.

To fix:
1. Wire `APNsService` instantiation in app.py lifespan (conditional on APNs config being present)
2. Set `APNsService._http_client` to a real httpx client during initialization
3. Add push hooks in approval.py and runs/service.py that call the batcher/APNs service
4. Add a `mode` query parameter to the voice endpoint; implement chat pipeline integration
5. Add artifact creation in the voice endpoint
