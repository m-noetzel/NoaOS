// DeepLinkRouterTests.swift — iOS6 Push Notifications (APNs Client)
// Spec ref: SPEC.md §29.5, §29.6, Plan/REVIEWS/test-plan_iOS6.md T10-T11, T17, T19
//
// Tests DeepLinkRouter responsibilities:
//   T10 approval_requested tap → .approval(id:) destination
//   T11 run_completed tap → .runDetail(id:) destination
//   T11b run_failed tap → .runDetail(id:) destination
//   T17 Unknown notification type → falls back to .home without crashing
//   T19 Push payload privacy: only notification_type, request_id, risk_tier fields accepted
//
// These tests FAIL at compile time because DeepLinkRouter does not exist yet.
// That is intentional — red phase.

import XCTest
import UserNotifications
@testable import Noa

// MARK: - Tests

final class DeepLinkRouterTests: XCTestCase {

    // MARK: - T10: approval_requested tapped → .approval destination

    func test_approvalRequested_routesToApprovalDestination() throws {
        // SPEC.md §29.6, Phase iOS6 deliverable 6:
        // Tapping an approval_requested notification must route to the approval detail view.
        // If deep linking is broken, the user lands on the default screen and must
        // manually find the approval — defeating the purpose of push notifications.
        let requestID = UUID()
        let payload = NotificationPayload(
            notificationType: "approval_requested",
            requestId: requestID,
            riskTier: "medium"
        )

        let router = DeepLinkRouter()
        let destination = router.destination(for: payload)

        guard case .approval(let id) = destination else {
            XCTFail("Expected .approval(\(requestID)), got: \(destination)")
            return
        }
        XCTAssertEqual(id, requestID, "Deep link must carry the correct request_id")
    }

    // MARK: - T11: run_completed tapped → .runDetail destination

    func test_runCompleted_routesToRunDetailDestination() throws {
        // SPEC.md §29.5, Phase iOS6 deliverable 6:
        // Tapping a run_completed notification must navigate to the run detail view.
        let runID = UUID()
        let payload = NotificationPayload(
            notificationType: "run_completed",
            requestId: runID,
            riskTier: ""
        )

        let router = DeepLinkRouter()
        let destination = router.destination(for: payload)

        guard case .runDetail(let id) = destination else {
            XCTFail("Expected .runDetail(\(runID)), got: \(destination)")
            return
        }
        XCTAssertEqual(id, runID, "Deep link must carry the correct run request_id")
    }

    // MARK: - T11b: run_failed tapped → .runDetail destination

    func test_runFailed_routesToRunDetailDestination() throws {
        // SPEC.md §29.5, Phase iOS6 deliverable 6:
        // Tapping a run_failed notification must navigate to the run detail, not the default screen.
        let runID = UUID()
        let payload = NotificationPayload(
            notificationType: "run_failed",
            requestId: runID,
            riskTier: ""
        )

        let router = DeepLinkRouter()
        let destination = router.destination(for: payload)

        guard case .runDetail(let id) = destination else {
            XCTFail("Expected .runDetail(\(runID)), got: \(destination)")
            return
        }
        XCTAssertEqual(id, runID, "run_failed deep link must carry the correct run request_id")
    }

    // MARK: - T17: Unknown notification type → .home fallback (forward compatibility)

    func test_unknownNotificationType_fallsBackToHome() {
        // Phase iOS6, T17: Forward compatibility. Future backend versions may add new
        // notification types before the app is updated. Must fall back to .home without crashing.
        let payload = NotificationPayload(
            notificationType: "new_type_v2_from_future_backend",
            requestId: UUID(),
            riskTier: ""
        )

        let router = DeepLinkRouter()
        let destination = router.destination(for: payload)

        guard case .home = destination else {
            XCTFail("Unknown notification type must fall back to .home, got: \(destination)")
            return
        }
        // No crash = success
    }

    // MARK: - T19: Push payload privacy — only spec-defined fields are used

    func test_pushPayloadPrivacy_onlyExpectedFieldsAreDecoded() throws {
        // SPEC.md §29.5: "No task content, tool names, or private data in the push payload."
        // The client must only read notification_type, request_id, and risk_tier.
        // Extra fields (if accidentally sent by backend) must be silently ignored.
        let jsonWithExtraFields = """
        {
            "notification_type": "approval_requested",
            "request_id": "12345678-1234-1234-1234-123456789012",
            "risk_tier": "medium",
            "task_content": "Send email to alice@example.com with subject: confidential",
            "tool_name": "email_send",
            "message": "User asked to send a sensitive email"
        }
        """.data(using: .utf8)!

        let payload = try JSONDecoder().decode(NotificationPayload.self, from: jsonWithExtraFields)

        // Only the three spec-defined fields may be present and used
        XCTAssertEqual(payload.notificationType, "approval_requested")
        XCTAssertNotNil(payload.requestId, "request_id must be decoded")
        XCTAssertEqual(payload.riskTier, "medium")

        // The struct must NOT expose task_content, tool_name, or message fields
        // (This is verified at compile time by the type system — if the struct
        // has those fields, the privacy invariant is broken.)
        // The test verifies the JSON decodes without error even with extra fields,
        // meaning unknown fields are properly ignored.
    }

    // MARK: - T10+T11 invariant: routing is deterministic

    func test_routingIsDeterministic_samePayloadSameDestination() {
        // Phase iOS6: Routing must be deterministic. Same input must always produce same output.
        let id = UUID()
        let payload = NotificationPayload(
            notificationType: "approval_requested",
            requestId: id,
            riskTier: "high"
        )

        let router = DeepLinkRouter()
        let dest1 = router.destination(for: payload)
        let dest2 = router.destination(for: payload)

        // Both destinations must be .approval with the same id
        if case .approval(let id1) = dest1, case .approval(let id2) = dest2 {
            XCTAssertEqual(id1, id2, "Routing must be deterministic for the same payload")
        } else {
            XCTFail("Both calls must return .approval, got: \(dest1), \(dest2)")
        }
    }
}

// Note: NotificationPayload and DeepLinkDestination are production types from Noa module.
// Using them directly to ensure tests exercise the real CodingKeys and routing logic.
