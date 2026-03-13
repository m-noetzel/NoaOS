# QA Review: Phase iOS6

**Date:** 2026-03-09
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 23 tests trace to SPEC.md sections or test plan IDs (T1-T19). Every test class has header comments citing spec refs. |
| M2 | Negative Tests | PASS | 5 negative/error-path tests: T2 (auth denied), T4 (401 propagation), T5 (network error), T14 (inline action failure), T18 (unauthenticated guard). |
| M3 | Security Boundaries | PASS | `.authenticationRequired` on Approve/Deny actions (T15). No private data in notification content (T7, T19). Auth guard on registration (T18). No hardcoded secrets. |
| M4 | Determinism | PASS | No wall-clock time, no network calls in unit tests, no unseeded randomness. Determinism test (T10+T11 invariant) explicitly verifies same-input-same-output. |
| M5 | Implementation Completeness | PASS | All 7 deliverables present: entitlement, PushNotificationService, DeviceService, token unregister, notification handling (3 types), deep linking, inline actions. No TODO/FIXME/HACK. |
| M6 | No Silent Error Swallowing | PASS | No bare `except`. `catch APIError.decodingError` in handleInlineAction is narrow and documented (fire-and-forget approval response body). `try?` in extractFields is for resilient JSON round-trip with graceful degradation to generic notification. |
| M7 | Wiring Completeness | PASS | N/A for app-level wiring (SPM library package, no @main entry point until iOS11). Services are constructable via DI and tested via real APIClient with MockURLProtocol. |
| M8 | Domain Isolation | PASS | N/A for pure iOS package. No cross-domain imports. All imports are Foundation and UserNotifications. |
| S1 | Error Handling & Boundaries | PASS | Boundary conditions tested: empty token data hex encoding (T16 with 0x00), unknown notification types (T17), unauthenticated state (T18). Error messages are specific (APIError typed). |
| S2 | Code Consistency | PASS | Actor-based services consistent with iOS3-5 pattern. CodingKeys follow snake_case backend contract. Protocol-based DI. |
| S3 | Migration & Rollback | N/A | No DB changes in this phase. |
| S4 | Documentation | PASS | All public methods have doc comments with spec references. Non-obvious logic (extractFields JSON round-trip, DecodingError catch) has inline comments explaining why. |
| S5 | Integration Smoke Test | OPEN | DeviceServiceTests use real APIClient with MockURLProtocol (non-mocked integration through the request pipeline). No Python contract test exists to pin Swift CodingKeys against backend schema. |

## Test Plan Coverage

The implementation covers all 14 MUST-HAVE tests (T1-T14) and all 5 NICE-TO-HAVE tests (T15-T19) from the test plan. Specific mapping:

| Test Plan ID | Test Method | Status |
|-------------|-------------|--------|
| T1 | test_authorizationGranted_registersNotificationCategories + test_authorizationGranted_approvalCategoryIsRegistered | Covered |
| T2 | test_authorizationDenied_returnsFalse | Covered |
| T3 | test_registerToken_sendsCorrectPostBody | Covered |
| T4 | test_registerToken_401_propagatesUnauthorizedError | Covered |
| T5 | test_registerToken_networkError_surfacedWithoutCrash | Covered |
| T6 | test_unregisterToken_sendsDELETEWithCorrectBody | Covered |
| T7 | test_notificationDisplay_approvalRequested_hasCategoryIdentifier + test_notificationDisplay_approvalRequested_noPrivateDataInBody | Covered |
| T8 | test_notificationDisplay_runCompleted_noCategoryIdentifier | Covered |
| T9 | test_notificationDisplay_runFailed_noCategoryIdentifier | Covered |
| T10 | test_approvalRequested_routesToApprovalDestination | Covered |
| T11 | test_runCompleted_routesToRunDetailDestination + test_runFailed_routesToRunDetailDestination | Covered |
| T12 | test_inlineApproveAction_callsApprovalDecideEndpoint | Covered |
| T13 | test_inlineDenyAction_callsApprovalDecideWithDenied | Covered |
| T14 | test_inlineAction_apiFailure_doesNotCrash | Covered |
| T15 | test_approvalCategory_actionsRequireAuthentication | Covered |
| T16 | test_tokenHexEncoding_producesCorrectLowercaseHex | Covered |
| T17 | test_unknownNotificationType_fallsBackToHome | Covered |
| T18 | test_registerToken_whenUnauthenticated_doesNotCallAPI | Covered |
| T19 | test_pushPayloadPrivacy_onlyExpectedFieldsAreDecoded | Covered |

All 19 test plan specifications are covered. Total: 23 test methods across 3 test classes.

## Spec Compliance

**SPEC.md SS29.5 (Push Notifications):**
- Authorization request with .alert, .sound, .badge options: IMPLEMENTED
- Device token registration POST /api/v1/devices/push-token: IMPLEMENTED with correct field names (device_id, platform, push_token)
- Token unregistration DELETE on logout: IMPLEMENTED
- No private data in push payload: IMPLEMENTED and TESTED (only notification_type, request_id, risk_tier)
- Notification types: approval_requested, run_completed, run_failed: IMPLEMENTED

**SPEC.md SS29.6 (Approval Flow):**
- Inline Approve/Deny actions: IMPLEMENTED with .authenticationRequired
- POST /api/v1/approvals/{id}/decide with decision body: IMPLEMENTED
- Deep link to approval detail on tap: IMPLEMENTED

**Backend contract alignment verified:**
- Swift `RegisterTokenBody` CodingKeys: device_id, platform, push_token -- matches `noa.push.schemas.DeviceTokenRequest`
- Swift `UnregisterTokenBody` CodingKeys: device_id, push_token -- matches backend expectations
- Swift `ApprovalDecisionBody`: decision ("approved"/"denied") -- matches `noa.api.v1.approvals` body schema

## Test Coverage

- **PushNotificationServiceTests:** 11 tests (T1, T2, T7-T9, T12-T15)
- **DeviceServiceTests:** 6 tests (T3-T6, T16, T18)
- **DeepLinkRouterTests:** 6 tests (T10, T11, T11b, T17, T19, determinism invariant)

Negative/error-path tests: 5 (auth denied, 401, network error, inline action failure, unauthenticated guard)
Security tests: 3 (authenticationRequired, privacy in notification content, privacy in payload fields)
Integration tests: DeviceServiceTests T3 and T6 use real APIClient with MockURLProtocol

## Anti-Pattern Scan Results

**M6 -- Silent error swallowing:**
- No bare `except` or `catch {}` blocks in any implementation file
- `catch APIError.decodingError` in handleInlineAction is narrow and documented

**M7 -- Wiring:**
- N/A for library package. No NaoApp.swift exists. Services tested via DI.

**M8 -- Domain isolation:**
- N/A for pure iOS package. Imports only Foundation and UserNotifications.

**`try?` audit:**
- PushNotificationService.swift:178-179 -- JSON round-trip in extractFields. Fallback: generic notification. Acceptable.
- DeepLinkRouter.swift:86-87 -- identical pattern. Fallback: .home destination. Acceptable.

**TODO/FIXME/HACK scan:** None found in any implementation file.

## Smoke Test Results

```
$ swift test 2>&1 | grep "passed ("  | wc -l
83

$ swift test 2>&1 | grep "Test run with"
Test run with 12 tests in 4 suites passed after 0.001 seconds.

Total: 95 tests (83 XCTest + 12 swift-testing), all passing.
iOS6-specific: 23 tests across PushNotificationServiceTests, DeviceServiceTests, DeepLinkRouterTests -- all passing.
No compilation errors. Only pre-existing warnings from AuthViewModel.swift.
```

## Security

1. **Approve/Deny require device authentication:** Both UNNotificationAction options include `.authenticationRequired`, preventing locked-device approval of high-risk actions. Verified by T15.
2. **No private data in notifications:** Notification content only shows "Action Required" / risk tier / generic messages. `NotificationPayload` struct only decodes notification_type, request_id, risk_tier. Extra JSON fields silently ignored. Verified by T7, T19.
3. **Auth guard on token registration:** `DeviceService.registerToken` checks `apiClient.isAuthenticated()` before making API call. Verified by T18.
4. **Token unregistration on logout:** Clears local state and sends DELETE to backend. Privacy violation prevented. Verified by T6.
5. **APNs entitlement:** `aps-environment` set to `development` -- appropriate for current stage. Must be changed to `production` before App Store release.
6. **No hardcoded secrets:** Grep for password/secret/token patterns found only CodingKey definitions, not actual values.

## Code Quality

**Strengths:**
- Actor isolation throughout -- PushNotificationService, DeviceService, MockAPIClientForPush are all actors
- Clean protocol-based DI via NotificationCenterProtocol and APIClientProtocol
- Generic `buildNotificationContent<P: Codable>` and `destination<P: Codable>` methods avoid coupling to specific payload types
- Proper hex encoding using `String(format: "%02x", $0)` -- avoids the classic iOS `Data.description` pitfall
- Tests use production types (NotificationPayload, DeepLinkDestination) not local shadows -- code reviewer feedback incorporated

**Minor observations:**
- `_VoidResponse` is defined in both PushNotificationService.swift and DeviceService.swift as private structs. Not a problem (both are private), but could be deduplicated into a shared utility.
- The JSON round-trip pattern (`encode -> JSONSerialization -> dict`) in both extractFields implementations is duplicated. A shared utility could reduce this.

## Beyond the Test Plan

**Issue 1: No local token caching when unauthenticated (T18 nuance)**
The test plan T18 specifies: "Token is cached locally for registration after login." The current implementation silently returns when unauthenticated -- it does NOT cache the token data for later registration. This means if `didRegisterForRemoteNotificationsWithDeviceToken` fires before the user logs in, the token is lost and registration only happens if iOS re-delivers the token (which it does on each app launch, so this is low-risk but not spec-perfect).

**Issue 2: No local notification scheduling test**
The `NotificationCenterProtocol` includes `add(_:)` for scheduling local notifications, and the mock implements it as a no-op. The implementation never calls `center.add()` -- push notifications are remote, so this is correct. But the protocol surface suggests it was designed for potential local notification use that never materialized.

**Issue 3: Entitlement file location**
The phase plan specified `ios/Noa/Noa/Noa.entitlements` but the file is at `ios/Noa/Sources/Noa/Noa.entitlements`. This is correct for the SPM layout. The entitlement will need to be wired into an Xcode project or xcodebuild flags when the app target is created (iOS11).

None of these are blocking.

## Blocking Issues (FAIL only)

N/A -- no blocking issues.

## Notes (PASS_WITH_NOTES only)

1. **No Python contract test for iOS6:** The test plan recommended a Python contract test pinning the Swift CodingKeys against `noa.push.schemas.DeviceTokenRequest`. Fields match (verified manually), but there is no automated test to catch future drift. Consider adding `tests/unit/test_ios6_push_contract.py` in a future phase.

2. **Token caching when unauthenticated:** `DeviceService.registerToken` silently drops the token when unauthenticated instead of caching it for later. iOS re-delivers tokens on each launch so this is low-risk, but a cached-and-retry-after-login pattern would be more robust.

3. **APNs entitlement is `development`:** Must be changed to `production` before App Store submission. Track as part of iOS11 integration polish.

4. **`_VoidResponse` duplication:** Minor -- defined as private structs in both PushNotificationService.swift and DeviceService.swift. Could be a shared internal type.

## Decision Review

No architectural decisions needed. The implementation is clean, well-tested, and follows established patterns from iOS3-5. The actor-based service pattern is consistent. Protocol-based DI enables testing without mocking frameworks. Backend contract alignment is verified.

The biggest remaining integration risk is the same as noted in previous iOS reviews: no @main app target exists. All components are tested in isolation within the SPM library. iOS11 (Integration Tests) will be the critical phase for verifying real wiring.
