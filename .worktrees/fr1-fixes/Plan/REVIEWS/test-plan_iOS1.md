# Test Plan: Phase iOS1

**Date:** 2026-03-08
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §29.5, §23.2, §29.6

## Summary

iOS1 adds the push notification backend: device token registration (DB + endpoints), an APNs HTTP/2 service with JWT auth, approval batching (30-second window), and integration hooks into approval/run services. The key testing risks are: (1) private data leaking into push payloads (security), (2) the batcher window logic being subtly wrong (timing edge cases), (3) APNs config secrets having unsafe fallback defaults, and (4) the new router/service not being wired into app.py (the project's most recurring anti-pattern).

## Test Specifications

### MUST-HAVE Tests

#### T1: test_register_device_push_token_success
- **Spec ref:** SPEC.md §29.5, Phase iOS1 deliverable 3
- **Category:** Behavioral
- **Setup:** Authenticated user, valid device_id + platform + push_token
- **Action:** POST /api/v1/devices/push-token with valid payload
- **Expected:** 200/201 response. Token stored in DB with correct user_id, device_id, platform, push_token, created_at, updated_at.
- **Why:** Without token registration, no push notifications can ever be sent.

#### T2: test_register_device_push_token_upsert_on_duplicate
- **Spec ref:** Phase iOS1 test list ("duplicate update works")
- **Category:** Behavioral
- **Setup:** Authenticated user with an already-registered device_id
- **Action:** POST /api/v1/devices/push-token with same device_id but new push_token
- **Expected:** Existing row updated (not duplicated). Only one row per user_id + device_id. updated_at changes.
- **Why:** APNs tokens rotate; re-registration must not create duplicates.

#### T3: test_delete_device_push_token_success
- **Spec ref:** SPEC.md §29.5, Phase iOS1 deliverable 4
- **Category:** Behavioral
- **Setup:** Authenticated user with a registered push token
- **Action:** DELETE /api/v1/devices/push-token with device_id
- **Expected:** Token row deleted from DB. 200/204 response.
- **Why:** Logout must remove push tokens to stop notifications.

#### T4: test_register_push_token_unauthenticated_rejected
- **Spec ref:** Phase iOS1 test list ("Auth required: unauthenticated requests rejected with 401")
- **Category:** Invariant / Security
- **Setup:** No auth token/cookie
- **Action:** POST /api/v1/devices/push-token
- **Expected:** 401 Unauthorized. No DB row created.
- **Why:** Unauthenticated users must not register push tokens — this would allow push notification injection.

#### T5: test_delete_push_token_unauthenticated_rejected
- **Spec ref:** Phase iOS1 test list, M3 (auth boundaries)
- **Category:** Invariant / Security
- **Setup:** No auth token/cookie
- **Action:** DELETE /api/v1/devices/push-token
- **Expected:** 401 Unauthorized.
- **Why:** Same auth boundary applies to deletion.

#### T6: test_apns_payload_contains_only_allowed_fields
- **Spec ref:** SPEC.md §29.5 — "Push payload contains only: notification_type, request_id, and risk_tier. No task content, tool names, or private data."
- **Category:** Security / Invariant
- **Setup:** An APNsService instance, a mock approval/run event with rich data (tool names, task content, user notes)
- **Action:** Call the payload construction method
- **Expected:** Returned payload contains EXACTLY notification_type, request_id, risk_tier (and Apple-required aps dict). NO other fields — no task content, no tool names, no preview_text, no summary, no user data. Assert the complete set of top-level keys.
- **Why:** THIS IS THE MOST IMPORTANT SECURITY TEST. Private data in push payloads transits Apple's servers unencrypted to the notification system. Any leak is a privacy violation per §29.5.

#### T7: test_apns_payload_notification_type_values
- **Spec ref:** SPEC.md §29.5 — notification types: approval_required, run_completed, run_failed
- **Category:** Behavioral
- **Setup:** APNsService or payload builder
- **Action:** Build payloads for each of the three notification types
- **Expected:** notification_type field is exactly one of: "approval_required", "run_completed", "run_failed". No other values accepted.
- **Why:** Ensures the notification type enum is correct per spec.

#### T8: test_apns_http2_send_success_mock
- **Spec ref:** Phase iOS1 deliverable 5
- **Category:** Behavioral
- **Setup:** APNsService with mocked HTTP/2 client (httpx or h2), valid JWT signing key
- **Action:** Call send_notification with a valid push token and payload
- **Expected:** HTTP/2 POST to api.push.apple.com:443 with correct path (/3/device/{token}), correct headers (authorization: bearer {jwt}, apns-topic: {bundle_id}, apns-push-type: alert), correct JSON body.
- **Why:** Validates the APNs protocol integration without hitting real Apple servers.

#### T9: test_apns_jwt_token_generation
- **Spec ref:** Phase iOS1 deliverable 5 — JWT-based auth
- **Category:** Behavioral
- **Setup:** APNsService with a test ES256 private key, key_id, team_id
- **Action:** Generate the APNs JWT
- **Expected:** JWT has correct header (alg=ES256, kid=key_id), payload contains iss=team_id and iat (issued-at timestamp). Token is decodable with the corresponding public key.
- **Why:** APNs rejects invalid JWTs — this must be correct.

#### T10: test_apns_handles_expired_token_response
- **Spec ref:** Phase iOS1 test list ("error handling for expired/invalid tokens")
- **Category:** Behavioral / Error path
- **Setup:** APNsService with mocked HTTP/2 client returning 410 Gone (expired token)
- **Action:** Call send_notification
- **Expected:** APNsService handles the 410 gracefully — logs the error, marks the device token as invalid/deleted (or returns an error indicating removal needed). Does NOT raise unhandled exception.
- **Why:** APNs returns 410 for expired tokens; the service must clean up stale tokens, not crash.

#### T11: test_apns_handles_invalid_token_response
- **Spec ref:** Phase iOS1 test list
- **Category:** Behavioral / Error path
- **Setup:** APNsService with mocked HTTP/2 client returning 400 BadDeviceToken
- **Action:** Call send_notification
- **Expected:** Graceful error handling, token flagged for removal. Specific error type/log, not silently swallowed.
- **Why:** Invalid tokens must be cleaned up, not retried indefinitely.

#### T12: test_approval_batcher_batches_within_window
- **Spec ref:** SPEC.md §23.2 — "30 seconds (configurable). If multiple approval-required tasks arrive within this window, they are grouped into a single approval request."
- **Category:** Behavioral
- **Setup:** ApprovalBatcher with 30-second window, mock push service
- **Action:** Submit 3 approval events for the same user within 30 seconds (use injected clock, NOT real time)
- **Expected:** Exactly 1 push notification sent (not 3). The notification references all 3 pending approvals.
- **Why:** Core batching requirement. Without this test, each approval could fire its own push — notification fatigue.

#### T13: test_approval_batcher_sends_separately_outside_window
- **Spec ref:** SPEC.md §23.2
- **Category:** Behavioral
- **Setup:** ApprovalBatcher with 30-second window, mock push service, injected clock
- **Action:** Submit approval event at t=0, then another at t=35s (outside window)
- **Expected:** 2 separate push notifications sent.
- **Why:** Events outside the window must not be batched together.

#### T14: test_approval_batcher_no_cross_domain_batching
- **Spec ref:** SPEC.md §23.2 — "Private-domain and external-domain tasks are never batched together"
- **Category:** Security / Invariant
- **Setup:** ApprovalBatcher, two approval events within 30s: one private domain, one external domain
- **Action:** Submit both events
- **Expected:** 2 separate push notifications (one per domain), not 1 batched notification.
- **Why:** Cross-domain batching violates domain isolation — a user seeing private and external tasks grouped together could leak domain affiliation information.

#### T15: test_push_trigger_on_approval_requested
- **Spec ref:** SPEC.md §29.6 — "Push notification sent (native iOS only)" after approval_requested
- **Category:** Integration
- **Setup:** ApprovalService with push hook wired, user with registered device token, mock APNs
- **Action:** Call request_approval for a medium/high risk action
- **Expected:** Push notification triggered (or queued for batching) with notification_type="approval_required", correct request_id, correct risk_tier.
- **Why:** The approval-to-push integration is the primary use case.

#### T16: test_push_trigger_on_run_completed
- **Spec ref:** SPEC.md §29.5 — run_completed notification type
- **Category:** Integration
- **Setup:** RunService with push hook wired, user with registered device token, mock APNs
- **Action:** Transition a run to "completed"
- **Expected:** Push notification sent with notification_type="run_completed".
- **Why:** Users must be notified when runs finish.

#### T17: test_push_trigger_on_run_failed
- **Spec ref:** SPEC.md §29.5 — run_failed notification type
- **Category:** Integration
- **Setup:** RunService with push hook wired, user with registered device token, mock APNs
- **Action:** Transition a run to "failed"
- **Expected:** Push notification sent with notification_type="run_failed".
- **Why:** Users must be notified of failures.

#### T18: test_no_push_for_low_risk_auto_approved
- **Spec ref:** Phase iOS1 test list — "No push sent for low-risk auto-approved actions"
- **Category:** Behavioral
- **Setup:** RunService/ApprovalService with push hook, low-risk action that auto-approves
- **Action:** Process a low-risk action
- **Expected:** No push notification sent. Mock push service assert_not_called.
- **Why:** Low-risk actions should not generate notification noise.

#### T19: test_apns_config_secrets_no_fallback_defaults
- **Spec ref:** ARCH_INVARIANTS.md L11 — "No fallback defaults on secrets"
- **Category:** Security / Invariant
- **Setup:** Config/Settings with APNS_KEY_ID, APNS_TEAM_ID, APNS_KEY_PATH, APNS_BUNDLE_ID
- **Action:** Instantiate APNsService without required config values
- **Expected:** Raises an error at construction/startup. Does NOT fall back to empty string, None, or dev default. The app must refuse to send pushes with misconfigured APNs credentials.
- **Why:** L11 requires no fallback defaults on secrets. An APNs key path defaulting to "" would silently disable push.

#### T20: test_migration_008_creates_device_push_tokens_table
- **Spec ref:** Phase iOS1 deliverable 2
- **Category:** Behavioral
- **Setup:** Alembic migration environment
- **Action:** Run upgrade for migration 008 (note: plan says 005 but 005-007 already exist)
- **Expected:** Table `device_push_tokens` created with columns: id (PK), user_id (FK to users), device_id (unique per user), platform, push_token, created_at, updated_at. Has index on user_id. Has unique constraint on (user_id, device_id).
- **Why:** Without correct schema, all token operations fail.

#### T21: test_migration_008_has_downgrade
- **Spec ref:** QA_CHECKLIST.md S3 — "migration is reversible"
- **Category:** Invariant
- **Setup:** Migration file
- **Action:** Inspect downgrade function
- **Expected:** downgrade() drops the device_push_tokens table. Not empty/pass.
- **Why:** Reversible migrations are required by S3.

#### T22: test_devices_router_registered_in_app
- **Spec ref:** ARCH_INVARIANTS.md L10 — wiring completeness
- **Category:** Integration / Invariant
- **Setup:** Import create_app or app
- **Action:** Check registered routes on the app
- **Expected:** POST /api/v1/devices/push-token and DELETE /api/v1/devices/push-token are in the route table.
- **Why:** The project's most recurring anti-pattern (MEMORY: "wired in class, not in app"). If the router is not registered, the endpoints are unreachable despite passing unit tests.

#### T23: test_apns_service_instantiated_at_startup
- **Spec ref:** ARCH_INVARIANTS.md L10 — "Every service class must be instantiated during app startup"
- **Category:** Integration / Invariant
- **Setup:** App with APNs config provided
- **Action:** Check that APNsService (or equivalent) is created during lifespan/startup and accessible
- **Expected:** APNsService instance exists and is wired to the approval/run hooks.
- **Why:** Without startup wiring, the push hooks have no service to call. Tests will pass with manually injected mocks but production will fail.

### NICE-TO-HAVE Tests

#### T24: test_register_push_token_invalid_platform
- **Spec ref:** M3 — input validation
- **Category:** Behavioral / Error path
- **Setup:** Authenticated user
- **Action:** POST /api/v1/devices/push-token with platform="android" or platform="windows"
- **Expected:** 422 or 400 error. Only "ios" (and possibly "ipados", "macos") accepted.
- **Why:** Prevents junk data in the token table.

#### T25: test_register_push_token_empty_or_blank_token
- **Spec ref:** S1 — boundary conditions
- **Category:** Behavioral / Error path
- **Setup:** Authenticated user
- **Action:** POST /api/v1/devices/push-token with push_token="" or push_token="   "
- **Expected:** 422 validation error. Empty tokens must not be stored.
- **Why:** Sending to an empty token wastes APNs calls and returns errors.

#### T26: test_approval_batcher_configurable_window
- **Spec ref:** SPEC.md §23.2 — "30 seconds (configurable)"
- **Category:** Behavioral
- **Setup:** ApprovalBatcher with window=10s
- **Action:** Submit events at t=0 and t=12s
- **Expected:** 2 separate notifications (outside 10s window). Proves the window is configurable, not hardcoded to 30.
- **Why:** Ensures configurability per spec.

#### T27: test_push_token_user_isolation
- **Spec ref:** M3 — auth boundaries
- **Category:** Security
- **Setup:** User A registers a token. User B is authenticated.
- **Action:** User B tries to delete User A's token
- **Expected:** User B cannot delete User A's tokens. Either 404 or 403.
- **Why:** Users must not be able to manipulate other users' device registrations.

#### T28: test_approval_batcher_single_event_sends_after_window_expires
- **Spec ref:** SPEC.md §23.2
- **Category:** Behavioral
- **Setup:** ApprovalBatcher with 30s window, injected clock
- **Action:** Submit 1 approval event, advance clock past 30s
- **Expected:** Push notification sent with the single event (not held indefinitely).
- **Why:** A single approval must still result in a notification after the batch window closes.

#### T29: test_apns_http2_connection_reuse
- **Spec ref:** Performance concern
- **Category:** Behavioral
- **Setup:** APNsService
- **Action:** Send 2 notifications in sequence
- **Expected:** HTTP/2 connection is reused (not reconnected per message).
- **Why:** APNs recommends connection reuse; creating a new TLS connection per push is expensive.

## Security Test Requirements

1. **T6 (payload leak)** is the highest-priority security test. The push payload MUST contain only notification_type, request_id, risk_tier. The test must assert the COMPLETE set of keys — not just check that those three exist (which would miss additional leaked fields).

2. **T14 (cross-domain batching)** prevents domain isolation leakage through notification grouping.

3. **T19 (config secrets)** prevents APNs credentials from having unsafe fallback defaults (L11).

4. **T4/T5 (auth boundaries)** prevent unauthenticated token registration.

5. **T27 (user isolation)** prevents cross-user token manipulation.

6. **APNs JWT private key must NOT be hardcoded** in source or tests. Tests should generate an ephemeral ES256 key pair in setup.

## Integration Test Requirements

The following must be tested WITHOUT mocking the internal component under test:

1. **T22 (router registration)** — call create_app(), inspect routes. No mocks needed.
2. **T23 (service wiring)** — verify APNsService is instantiated in lifespan. The APNs HTTP client can be mocked, but the service object must be real.
3. **T15 (approval -> push)** — call real ApprovalService.request_approval(), verify push hook fires. APNs client mocked, but the approval-to-push wiring must be real.
4. **T16/T17 (run -> push)** — call real RunService.update_status(), verify push hook fires. Same principle.

## Anti-Patterns to Watch For

Based on past retros and memory:

1. **"Wired in class, not in app" (QC5/QC8 pattern):** The developer implements APNsService and ApprovalBatcher correctly but never registers the devices router in app.py or never instantiates APNsService in the lifespan. Tests pass because they manually construct the service. Production has no push notifications. **T22 and T23 catch this.**

2. **"Orphaned utility" (QC8 A5/A4):** ApprovalBatcher exists in src/noa/push/batcher.py but is never imported by approval.py or app.py. **Grep for the class name in all non-test files after implementation.**

3. **Migration number collision:** Phase plan says `005_device_push_tokens.py` but migrations 005, 006, 007 already exist. The migration MUST be `008_device_push_tokens.py`. Using 005 would collide. **T20 catches the number but the developer must be told.**

4. **Source inspection tests (QC2 weakness):** Do not write tests that use `inspect.getsource()` to verify payload contents. Write tests that CALL the payload builder and assert on the RETURNED value.

5. **Bare except blocks (L9):** APNs HTTP/2 calls will have error paths. Every except block must catch specific exceptions and log or re-raise. No `except Exception: pass`.

6. **Wall-clock time in batcher tests (M4):** The 30-second batch window MUST use an injected clock or freezegun, NOT `time.sleep(30)` or `asyncio.sleep(30)`. Tests that sleep for 30+ seconds are both slow and non-deterministic.

7. **Push token stored as plaintext vs encrypted:** The spec does not require encryption for push tokens (they are Apple-assigned identifiers, not user secrets), but if the column is named `_enc` it must have actual encryption (per HD memory note).

8. **ApprovalService is sync, APNsService will likely be async:** The hook integration must handle the sync-to-async boundary correctly. If approval.py calls an async push function from a sync method, it will get a coroutine object, not a result. **T15 must actually await the result chain.**
