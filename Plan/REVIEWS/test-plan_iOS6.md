# Test Plan: Phase iOS6

**Date:** 2026-03-09
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §29.5 (Push Notifications), §23.2 (Approval Batching), §29.6 (Approval Flow)

## Summary

iOS6 integrates APNs push notifications on the client side: requesting authorization, registering/unregistering device tokens with the backend, displaying notifications per type, routing deep links from notification taps, and providing inline Approve/Deny actions for approval_requested notifications. The key testing risks are: (1) token registration lifecycle correctness (register on auth, unregister on logout), (2) push payload privacy compliance (no private data leaks into UNNotificationContent), (3) deep link routing to correct views, and (4) inline action handling that actually calls the approval API.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_push_authorization_granted
- **Spec ref:** SPEC.md §29.5, Phase iOS6 deliverable 2
- **Category:** Behavioral
- **Setup:** Mock UNUserNotificationCenter that returns .authorized status.
- **Action:** Call PushNotificationService.requestAuthorization().
- **Expected:** Method returns true/succeeds. Notification categories (with Approve/Deny actions) are registered on the center.
- **Why:** If authorization grant is not handled, no push notifications will ever be received.

#### T2: test_push_authorization_denied
- **Spec ref:** SPEC.md §29.5, Phase iOS6 deliverable 2
- **Category:** Behavioral (error path)
- **Setup:** Mock UNUserNotificationCenter that returns .denied status.
- **Action:** Call PushNotificationService.requestAuthorization().
- **Expected:** Method returns false or throws a specific error. No crash. No token registration attempted.
- **Why:** Users can deny push permissions. App must gracefully degrade without crashing or spamming registration calls.

#### T3: test_device_token_registration_success
- **Spec ref:** SPEC.md §29.5, Phase iOS6 deliverable 3
- **Category:** Behavioral
- **Setup:** Mock APIClient. Provide a valid device token Data (hex string equivalent). User is authenticated.
- **Action:** Call DeviceService.registerToken(tokenData:).
- **Expected:** POST /api/v1/devices/push-token is called with correct JSON body: device_id (DeviceID.current), platform ("ios"), push_token (hex-encoded token). Returns successfully.
- **Why:** Without correct registration, the backend cannot send push notifications to this device.

#### T4: test_device_token_registration_401_clears_auth
- **Spec ref:** SPEC.md §29.5, §29.3 (401 handling)
- **Category:** Behavioral (error path)
- **Setup:** Mock APIClient that throws APIError.unauthorized on the POST call.
- **Action:** Call DeviceService.registerToken(tokenData:).
- **Expected:** The error propagates (or is handled gracefully). No infinite retry loop. Token is NOT stored locally as "registered."
- **Why:** If the user's session has expired, registration must not silently succeed. A 401 during registration means the auth state is stale.

#### T5: test_device_token_registration_network_error
- **Spec ref:** SPEC.md §29.5, Phase iOS6
- **Category:** Behavioral (error path)
- **Setup:** Mock APIClient that throws APIError.networkError.
- **Action:** Call DeviceService.registerToken(tokenData:).
- **Expected:** Error is surfaced or logged. No crash. The app should still function without push. Consider whether retry logic exists (if so, test retry-then-give-up).
- **Why:** Network errors during token registration must not block app startup or cause an infinite retry loop.

#### T6: test_device_token_unregistration_on_logout
- **Spec ref:** SPEC.md §29.5, Phase iOS6
- **Category:** Behavioral
- **Setup:** Mock APIClient. Device was previously registered (token exists).
- **Action:** Call DeviceService.unregisterToken() or trigger the logout flow that calls it.
- **Expected:** DELETE /api/v1/devices/push-token is called with correct body (device_id, push_token). On success, local registration state is cleared.
- **Why:** If tokens are not unregistered on logout, the backend will send notifications to a device whose user has signed out. This is a privacy violation.

#### T7: test_notification_display_approval_requested
- **Spec ref:** SPEC.md §29.5 (notification_type: approval_requested), §29.6
- **Category:** Behavioral
- **Setup:** Construct a UNNotification (or the parsed push payload) with notification_type = "approval_requested", request_id = UUID, risk_tier = "medium".
- **Action:** PushNotificationService processes the notification for display.
- **Expected:** Notification content includes: title mentioning approval/action required, body mentioning risk tier. Category identifier is set to enable Approve/Deny actions. No private data (task content, tool names) appears in the notification.
- **Why:** Spec §29.5 explicitly requires "No task content, tool names, or private data in the push payload." The notification must convey urgency without leaking private information.

#### T8: test_notification_display_run_completed
- **Spec ref:** SPEC.md §29.5 (notification_type: run_completed)
- **Category:** Behavioral
- **Setup:** Push payload with notification_type = "run_completed".
- **Action:** Process notification for display.
- **Expected:** Notification shows completion status. No Approve/Deny actions (those are only for approval_requested). No private data in content.
- **Why:** Different notification types must render differently. Showing Approve/Deny on a run_completed notification is confusing and dangerous.

#### T9: test_notification_display_run_failed
- **Spec ref:** SPEC.md §29.5 (notification_type: run_failed)
- **Category:** Behavioral
- **Setup:** Push payload with notification_type = "run_failed".
- **Action:** Process notification for display.
- **Expected:** Notification shows failure status. No Approve/Deny actions.
- **Why:** Same as T8 -- type-specific rendering.

#### T10: test_deep_link_approval_navigates_to_approval_view
- **Spec ref:** SPEC.md §29.6, Phase iOS6 deliverable 5
- **Category:** Behavioral
- **Setup:** User taps notification with notification_type = "approval_requested" and request_id = some UUID.
- **Action:** DeepLinkRouter processes the notification response.
- **Expected:** Router emits/returns a deep link destination that identifies the approval (e.g., .approval(id: UUID)). The navigation state would change to show the approval detail.
- **Why:** If deep linking is broken, tapping a notification opens the app to the default screen. The user then has to manually find the approval -- defeating the purpose of push notifications.

#### T11: test_deep_link_run_detail_navigates_correctly
- **Spec ref:** SPEC.md §29.5, Phase iOS6 deliverable 5
- **Category:** Behavioral
- **Setup:** User taps notification with notification_type = "run_completed" and request_id = some UUID.
- **Action:** DeepLinkRouter processes the notification response.
- **Expected:** Router emits a deep link to the run detail view (e.g., .runDetail(id: UUID)).
- **Why:** Tapping a run_completed/run_failed notification should navigate to the run, not just open the app.

#### T12: test_inline_approve_action
- **Spec ref:** SPEC.md §29.6 (Approval Flow), Phase iOS6
- **Category:** Behavioral
- **Setup:** Mock APIClient. Notification with approval category. User selects "Approve" action.
- **Action:** PushNotificationService handles the UNNotificationResponse with actionIdentifier = "approve".
- **Expected:** POST /api/v1/approvals/{request_id}/decide is called with body {"decision": "approved"}. Completion handler is called. On success, no error is surfaced.
- **Why:** The inline approve action is the primary UX benefit of push notifications for approvals. If it silently fails or calls the wrong endpoint, approvals are broken.

#### T13: test_inline_deny_action
- **Spec ref:** SPEC.md §29.6, Phase iOS6
- **Category:** Behavioral (mirror of T12)
- **Setup:** Same as T12 but user selects "Deny" action.
- **Action:** Handle response with actionIdentifier = "deny".
- **Expected:** POST /api/v1/approvals/{request_id}/decide with {"decision": "denied"}.
- **Why:** Deny must work identically to approve in terms of API call correctness.

#### T14: test_inline_action_failure_does_not_crash
- **Spec ref:** SPEC.md §29.6, Phase iOS6
- **Category:** Behavioral (error path)
- **Setup:** Mock APIClient that throws on the approval decide call (e.g., network error or 500).
- **Action:** Handle "Approve" action.
- **Expected:** Error is logged. Completion handler is still called (iOS requires this). No crash. User can retry by opening the app.
- **Why:** If the inline action fails and the completion handler is never called, iOS kills the app extension. If it crashes, the user has no recourse.

### NICE-TO-HAVE Tests

#### T15: test_notification_categories_registered_with_correct_actions
- **Spec ref:** Phase iOS6 deliverable 4
- **Category:** Behavioral
- **Setup:** App startup or PushNotificationService initialization.
- **Action:** Inspect registered UNNotificationCategory.
- **Expected:** Category for approval_requested has two actions: "Approve" (identifier: "approve") and "Deny" (identifier: "deny"). Both are marked as requiring authentication (UNNotificationActionOptions.authenticationRequired).
- **Why:** Without .authenticationRequired on the action, someone with physical access to a locked device could approve high-risk actions.

#### T16: test_push_token_hex_encoding
- **Spec ref:** Phase iOS6 deliverable 3
- **Category:** Behavioral (edge case)
- **Setup:** Raw Data bytes from iOS (e.g., 32 bytes).
- **Action:** Convert to hex string for backend registration.
- **Expected:** Correct lowercase hex string without angle brackets or spaces (common iOS pitfall: description returns "<aabb ccdd>" format).
- **Why:** Incorrectly encoded tokens cause silent push delivery failures. This is a historically common iOS bug.

#### T17: test_deep_link_unknown_notification_type
- **Spec ref:** Phase iOS6 deliverable 5
- **Category:** Behavioral (edge case)
- **Setup:** Notification with an unknown notification_type (e.g., "new_type_v2" from a future backend version).
- **Action:** DeepLinkRouter processes the response.
- **Expected:** Falls through to a default destination (e.g., home/chat) without crashing.
- **Why:** Forward compatibility. Backend may add new notification types before the app is updated.

#### T18: test_no_registration_when_unauthenticated
- **Spec ref:** SPEC.md §29.5
- **Category:** Behavioral (security edge case)
- **Setup:** User is not logged in. didRegisterForRemoteNotificationsWithDeviceToken is called.
- **Action:** AppDelegate receives device token.
- **Expected:** DeviceService.registerToken is NOT called (no auth token available). Token is cached locally for registration after login.
- **Why:** Sending a registration request without auth will 401 and waste network. Worse, if the endpoint doesn't require auth (misconfiguration), tokens could be registered for no user.

#### T19: test_push_payload_privacy_no_task_content
- **Spec ref:** SPEC.md §29.5 -- "No task content, tool names, or private data in the push payload"
- **Category:** Invariant (security)
- **Setup:** Notification payload matching backend PushPayload schema.
- **Action:** Parse and verify.
- **Expected:** Only notification_type, request_id, and risk_tier are used. No fields named "content", "tool_name", "message", "task", etc. are read or displayed.
- **Why:** The spec's privacy requirement is that push payloads contain only metadata. If the client extracts and displays extra fields, it undermines the privacy guarantee even if the backend doesn't send them today.

## Security Test Requirements

1. **Approve/Deny actions require authentication** (T15): UNNotificationAction must use `.authenticationRequired` so locked-device approval is prevented.
2. **No private data in notification display** (T7, T8, T9, T19): Push content must only show notification_type, risk_tier. Never task content, tool names, or user messages.
3. **Token unregistration on logout** (T6): Failure to unregister means a device receives notifications for a user who has signed out -- privacy violation.
4. **No registration without auth** (T18): Prevents token registration from being called with no Bearer token.

## Integration Test Requirements

1. **DeviceService -> APIClient -> backend contract** (T3, T6): The POST/DELETE /api/v1/devices/push-token payloads must match the backend's DeviceTokenRequest schema (device_id: str, platform: str, push_token: str). Write a Python contract test that verifies the expected JSON shape against `noa.push.schemas.DeviceTokenRequest`.
2. **Inline action -> approval endpoint contract** (T12, T13): The approval decide payload must match POST /api/v1/approvals/{id}/decide expected body. Write a Python contract test verifying the shape.
3. **DeepLinkRouter -> navigation** (T10, T11): At minimum, verify that the router returns correct destination enum values for each notification type -- this tests the wiring between notification handling and app navigation.

## Anti-Patterns to Watch For

Based on past retros and audit findings:

1. **"Wired in class, hooks log but never call" (iOS1 cycle 2 pattern):** The backend APNsService has `_http_client = None` and push hooks that log but never call `send()`. Verify the iOS client actually calls the API endpoints, not just logs "would register token."

2. **`try?` silently dropping errors (iOS5 cycle 1):** iOS5 had `try?` on SSE decode that silently dropped events. Watch for `try?` on token registration or inline action handling -- these must surface errors.

3. **Module exists but never wired (QC8 pattern):** PushNotificationService and DeviceService must be instantiated and connected in NaoApp.swift's AppDelegate. If they exist as standalone files but are never initialized in the app's lifecycle, they are dead code. Grep for class names in NaoApp.swift.

4. **Token hex encoding via `.description`:** On iOS, `Data.description` returns `"<aabbccdd>"` with angle brackets. Many implementations accidentally use this instead of proper hex mapping. Verify the hex conversion uses `map { String(format: "%02x", $0) }.joined()` or equivalent.

5. **Completion handler not called:** UNUserNotificationCenter delegate methods require calling the completion handler. If the async action (API call) throws and the catch block doesn't call the handler, iOS will terminate the extension process.

6. **Notification categories not registered at launch:** Categories must be registered early (application:didFinishLaunchingWithOptions: or SwiftUI App init). If registered lazily after the first notification, the first notification will not show actions.
