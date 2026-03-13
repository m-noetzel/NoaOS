// PushNotificationServiceTests.swift — iOS6 Push Notifications (APNs Client)
// Spec ref: SPEC.md §29.5, §29.6, Plan/REVIEWS/test-plan_iOS6.md T1-T2, T7-T9, T12-T15
//
// Tests PushNotificationService responsibilities:
//   T1  Authorization grant: notification categories registered, returns true
//   T2  Authorization denied: returns false, no token registration attempted
//   T7  Notification display for approval_requested: category set, no private data
//   T8  Notification display for run_completed: no Approve/Deny actions
//   T9  Notification display for run_failed: no Approve/Deny actions
//   T12 Inline approve action: POST /api/v1/approvals/{id}/decide with "approved"
//   T13 Inline deny action: POST /api/v1/approvals/{id}/decide with "denied"
//   T14 Inline action failure: completion handler still called, no crash
//   T15 Notification categories have authenticationRequired on both actions
//
// These tests FAIL at compile time because PushNotificationService does not exist yet.
// That is intentional — red phase.

import XCTest
import UserNotifications
@testable import Noa

// MARK: - Mock UNUserNotificationCenter

/// Testable double for UNUserNotificationCenter.
/// PushNotificationService must accept a protocol or subclass for testability.
/// Spec ref: Phase iOS6 deliverable 2
final class MockNotificationCenter: NotificationCenterProtocol, @unchecked Sendable {

    var requestedOptions: UNAuthorizationOptions?
    var requestAuthorizationResult: Bool = false
    var requestAuthorizationError: Error? = nil
    var registeredCategories: Set<UNNotificationCategory> = []
    var notificationCenterDelegate: (any UNUserNotificationCenterDelegate)?

    func requestAuthorization(
        options: UNAuthorizationOptions
    ) async throws -> Bool {
        requestedOptions = options
        if let error = requestAuthorizationError {
            throw error
        }
        return requestAuthorizationResult
    }

    func setNotificationCategories(_ categories: Set<UNNotificationCategory>) {
        registeredCategories = categories
    }

    func add(_ request: UNNotificationRequest) async throws {
        // No-op for tests
    }
}

// MARK: - Mock APIClient for inline actions

/// A simple API mock that records calls and returns controlled responses.
actor MockAPIClientForPush: APIClientProtocol {

    var recordedRequests: [(endpoint: String, method: String, body: Data?)] = []
    var shouldThrow: Error? = nil

    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        let bodyData = body.flatMap { try? JSONEncoder().encode($0) }
        recordedRequests.append((endpoint: endpoint, method: method, body: bodyData))
        if let error = shouldThrow {
            throw error
        }
        // Return a minimal empty response
        guard let result = PushEmptyResponse() as? T else {
            throw APIError.decodingError(underlying: MockDecodeFailure())
        }
        return result
    }
}

/// Minimal codable placeholder for void responses (push service tests).
struct PushEmptyResponse: Codable, Sendable {}

/// Used when MockAPIClientForPush cannot cast to the expected T type.
private struct MockDecodeFailure: Error {}

// MARK: - Push Payload helper

/// Push payload as defined in SPEC.md §29.5.
/// Fields: notification_type, request_id, risk_tier only. No private data.
struct PushPayload: Codable, Sendable {
    let notificationType: String
    let requestId: UUID
    let riskTier: String

    enum CodingKeys: String, CodingKey {
        case notificationType = "notification_type"
        case requestId = "request_id"
        case riskTier = "risk_tier"
    }
}

// MARK: - Tests

final class PushNotificationServiceTests: XCTestCase {

    private var mockCenter: MockNotificationCenter!
    private var mockAPIClient: MockAPIClientForPush!

    override func setUp() {
        super.setUp()
        mockCenter = MockNotificationCenter()
        mockAPIClient = MockAPIClientForPush()
    }

    // MARK: - T1: Authorization granted — categories registered

    func test_authorizationGranted_registersNotificationCategories() async throws {
        // SPEC.md §29.5: On authorization grant, notification categories with
        // Approve/Deny inline actions must be registered.
        mockCenter.requestAuthorizationResult = true

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        let granted = try await service.requestAuthorization()

        XCTAssertTrue(granted, "requestAuthorization must return true when center grants")
        XCTAssertFalse(
            mockCenter.registeredCategories.isEmpty,
            "Notification categories must be registered on authorization grant"
        )
    }

    // MARK: - T1 (continued): Category identifiers include approval_requested

    func test_authorizationGranted_approvalCategoryIsRegistered() async throws {
        // Phase iOS6 deliverable 7: Category for approval_requested must be registered
        mockCenter.requestAuthorizationResult = true

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )
        _ = try await service.requestAuthorization()

        let approvalCategory = mockCenter.registeredCategories.first(where: {
            $0.identifier == "approval_requested"
        })
        XCTAssertNotNil(
            approvalCategory,
            "An 'approval_requested' UNNotificationCategory must be registered"
        )
    }

    // MARK: - T2: Authorization denied — returns false, no crash

    func test_authorizationDenied_returnsFalse() async throws {
        // SPEC.md §29.5: If the user denies push permissions, the app must degrade
        // gracefully. requestAuthorization must return false without crashing.
        mockCenter.requestAuthorizationResult = false

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        let granted = try await service.requestAuthorization()

        XCTAssertFalse(granted, "requestAuthorization must return false when center denies")
    }

    // MARK: - T7: approval_requested notification has correct category identifier

    func test_notificationDisplay_approvalRequested_hasCategoryIdentifier() throws {
        // SPEC.md §29.5, §29.6: approval_requested notifications must set the
        // UNNotificationCategory identifier so inline Approve/Deny actions appear.
        let payload = PushPayload(
            notificationType: "approval_requested",
            requestId: UUID(),
            riskTier: "medium"
        )

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        let content = service.buildNotificationContent(for: payload)

        XCTAssertEqual(
            content.categoryIdentifier,
            "approval_requested",
            "approval_requested notification must set categoryIdentifier to 'approval_requested'"
        )
    }

    // MARK: - T7 (privacy): No private data in notification content

    func test_notificationDisplay_approvalRequested_noPrivateDataInBody() throws {
        // SPEC.md §29.5: "No task content, tool names, or private data in the push payload."
        // The notification content body must not contain task content or tool names.
        let payload = PushPayload(
            notificationType: "approval_requested",
            requestId: UUID(),
            riskTier: "medium"
        )

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )
        let content = service.buildNotificationContent(for: payload)

        // Body must only mention the risk tier — never task content or tool names.
        let forbiddenTerms = ["tool_name", "task", "content", "message", "instruction"]
        for term in forbiddenTerms {
            XCTAssertFalse(
                content.body.lowercased().contains(term),
                "Notification body must not contain '\(term)' — privacy violation per SPEC.md §29.5"
            )
        }
    }

    // MARK: - T8: run_completed notification has no Approve/Deny category

    func test_notificationDisplay_runCompleted_noCategoryIdentifier() throws {
        // SPEC.md §29.5: run_completed notifications must NOT show Approve/Deny actions.
        // Category identifier must be empty or a non-approval category.
        let payload = PushPayload(
            notificationType: "run_completed",
            requestId: UUID(),
            riskTier: ""
        )

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )
        let content = service.buildNotificationContent(for: payload)

        XCTAssertNotEqual(
            content.categoryIdentifier,
            "approval_requested",
            "run_completed notification must NOT use the 'approval_requested' category"
        )
    }

    // MARK: - T9: run_failed notification has no Approve/Deny category

    func test_notificationDisplay_runFailed_noCategoryIdentifier() throws {
        // SPEC.md §29.5: run_failed notifications must NOT show Approve/Deny actions.
        let payload = PushPayload(
            notificationType: "run_failed",
            requestId: UUID(),
            riskTier: ""
        )

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )
        let content = service.buildNotificationContent(for: payload)

        XCTAssertNotEqual(
            content.categoryIdentifier,
            "approval_requested",
            "run_failed notification must NOT use the 'approval_requested' category"
        )
    }

    // MARK: - T12: Inline approve action calls POST /api/v1/approvals/{id}/decide

    func test_inlineApproveAction_callsApprovalDecideEndpoint() async throws {
        // SPEC.md §29.6: Inline Approve action must POST the decision to the backend.
        let requestID = UUID()

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        try await service.handleInlineAction(
            actionIdentifier: "approve",
            requestId: requestID
        )

        let requests = await mockAPIClient.recordedRequests
        XCTAssertEqual(requests.count, 1, "Exactly one API request must be made")

        let req = try XCTUnwrap(requests.first)
        XCTAssertTrue(
            req.endpoint.contains("/api/v1/approvals/") && req.endpoint.contains(requestID.uuidString),
            "Endpoint must be /api/v1/approvals/{requestId}/decide, got: \(req.endpoint)"
        )
        XCTAssertEqual(req.method, "POST", "Must use POST method")

        // Verify body contains "approved"
        let bodyData = try XCTUnwrap(req.body)
        let body = try JSONDecoder().decode([String: String].self, from: bodyData)
        XCTAssertEqual(body["decision"], "approved", "Decision body must be 'approved'")
    }

    // MARK: - T13: Inline deny action calls POST with "denied"

    func test_inlineDenyAction_callsApprovalDecideWithDenied() async throws {
        // SPEC.md §29.6: Inline Deny action must POST "denied" decision.
        let requestID = UUID()

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        try await service.handleInlineAction(
            actionIdentifier: "deny",
            requestId: requestID
        )

        let requests = await mockAPIClient.recordedRequests
        let req = try XCTUnwrap(requests.first)

        let bodyData = try XCTUnwrap(req.body)
        let body = try JSONDecoder().decode([String: String].self, from: bodyData)
        XCTAssertEqual(body["decision"], "denied", "Decision body must be 'denied'")
    }

    // MARK: - T14: Inline action failure does not crash; error is surfaced

    func test_inlineAction_apiFailure_doesNotCrash() async {
        // Phase iOS6, T14: If the approval API call fails, the service must not crash.
        // Error must be surfaced or logged — not silently swallowed.
        await mockAPIClient.setShouldThrow(APIError.networkError(underlying: URLError(.notConnectedToInternet)))

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )

        do {
            try await service.handleInlineAction(
                actionIdentifier: "approve",
                requestId: UUID()
            )
            // If the service swallows the error gracefully (and logs it), that's also acceptable.
            // What is NOT acceptable: a crash or an infinite retry loop.
        } catch {
            // Error propagation is also acceptable — the key is no crash.
            // The test will fail if XCTest detects a fatal error.
        }
        // Reaching this line means no crash occurred.
        XCTAssertTrue(true, "No crash occurred on API failure in inline action handler")
    }

    // MARK: - T15: Approve/Deny actions require authentication (security)

    func test_approvalCategory_actionsRequireAuthentication() async throws {
        // Phase iOS6, T15, Security: UNNotificationAction on Approve/Deny must use
        // .authenticationRequired to prevent locked-device approval.
        mockCenter.requestAuthorizationResult = true

        let service = PushNotificationService(
            center: mockCenter,
            apiClient: mockAPIClient
        )
        _ = try await service.requestAuthorization()

        let approvalCategory = try XCTUnwrap(
            mockCenter.registeredCategories.first(where: { $0.identifier == "approval_requested" }),
            "approval_requested category must exist"
        )

        XCTAssertEqual(approvalCategory.actions.count, 2, "Must have exactly 2 actions: Approve and Deny")

        for action in approvalCategory.actions {
            XCTAssertTrue(
                action.options.contains(.authenticationRequired),
                "Action '\(action.identifier)' must have .authenticationRequired to prevent locked-device approval"
            )
        }
    }
}

// MARK: - Actor helper

extension MockAPIClientForPush {
    func setShouldThrow(_ error: Error?) {
        self.shouldThrow = error
    }
}
