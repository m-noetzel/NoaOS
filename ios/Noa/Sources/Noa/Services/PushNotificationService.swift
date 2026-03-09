// PushNotificationService.swift — APNs client-side push handling
// Spec ref: SPEC.md §29.5, §29.6, Phase iOS6
//
// Responsibilities:
//   - Request push notification authorization from the user
//   - Register notification categories (APPROVAL with Approve/Deny actions)
//   - Build UNMutableNotificationContent from incoming push payloads
//   - Handle inline Approve/Deny actions by POSTing to /api/v1/approvals/{id}/decide

import Foundation
import UserNotifications

// MARK: - NotificationCenterProtocol

/// Abstraction over UNUserNotificationCenter for testability.
/// PushNotificationService accepts any conformer at init time.
public protocol NotificationCenterProtocol: Sendable {
    /// Requests push authorization from the user.
    func requestAuthorization(options: UNAuthorizationOptions) async throws -> Bool
    /// Registers the given notification categories with the system.
    func setNotificationCategories(_ categories: Set<UNNotificationCategory>)
    /// Schedules a local notification.
    func add(_ request: UNNotificationRequest) async throws
}

// MARK: - UNUserNotificationCenter conformance

// UNUserNotificationCenter conforms to NotificationCenterProtocol via the SDK's
// native async methods (iOS 15+/macOS 12+). No additional bodies needed.
// @unchecked Sendable is safe here: UNUserNotificationCenter is a singleton with
// thread-safe method implementations documented by Apple.
extension UNUserNotificationCenter: NotificationCenterProtocol, @retroactive @unchecked Sendable {}

// MARK: - Inline action body

private struct ApprovalDecisionBody: Encodable, Sendable {
    let decision: String
}

// MARK: - PushNotificationService

/// Actor-isolated service for APNs push notification handling.
/// Spec ref: SPEC.md §29.5, §29.6
public actor PushNotificationService {

    // MARK: - Constants

    private static let approvalCategoryID = "approval_requested"
    private static let approveActionID = "approve"
    private static let denyActionID = "deny"

    // MARK: - Properties

    private let center: any NotificationCenterProtocol
    private let apiClient: any APIClientProtocol

    // MARK: - Init

    public init(center: any NotificationCenterProtocol, apiClient: any APIClientProtocol) {
        self.center = center
        self.apiClient = apiClient
    }

    // MARK: - Authorization

    /// Requests push authorization. On grant, registers notification categories.
    /// - Returns: `true` if authorization was granted, `false` if denied.
    /// - Throws: Any error from the notification center (e.g. permission dialog failure).
    public func requestAuthorization() async throws -> Bool {
        let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
        if granted {
            registerCategories()
        }
        return granted
    }

    // MARK: - Notification content

    /// Builds display content for an incoming push payload.
    /// Reads only `notification_type`, `request_id`, and `risk_tier` — no private data.
    /// Spec ref: SPEC.md §29.5 — "No task content, tool names, or private data in the push payload."
    ///
    /// This method is generic so tests can pass any Codable payload type with the
    /// expected JSON keys (notification_type, request_id, risk_tier).
    public nonisolated func buildNotificationContent<P: Codable & Sendable>(for payload: P) -> UNMutableNotificationContent {
        // Decode fields from the payload via JSON round-trip, accepting any Codable type.
        let decoded = extractFields(from: payload)
        let notificationType = decoded.notificationType

        let content = UNMutableNotificationContent()

        switch notificationType {
        case Self.approvalCategoryID:
            content.title = "Action Required"
            content.body = "Risk level: \(decoded.riskTier). Tap to review."
            content.categoryIdentifier = Self.approvalCategoryID
        case "run_completed":
            content.title = "Run Completed"
            content.body = "Your task has finished."
            content.categoryIdentifier = "run_completed"
        case "run_failed":
            content.title = "Run Failed"
            content.body = "Your task encountered an error."
            content.categoryIdentifier = "run_failed"
        default:
            content.title = "Noa"
            content.body = "You have a new notification."
            content.categoryIdentifier = ""
        }

        return content
    }

    // MARK: - Inline actions

    /// Handles a tapped notification action (Approve or Deny) by POSTing the decision to the backend.
    /// Spec ref: SPEC.md §29.6 — inline actions POST to /api/v1/approvals/{id}/decide
    ///
    /// - Parameters:
    ///   - actionIdentifier: "approve" or "deny"
    ///   - requestId: The UUID of the pending approval request
    /// - Throws: `APIError` if the backend call fails. Does not suppress errors.
    public func handleInlineAction(actionIdentifier: String, requestId: UUID) async throws {
        let decision: String
        switch actionIdentifier {
        case Self.approveActionID:
            decision = "approved"
        case Self.denyActionID:
            decision = "denied"
        default:
            // Unknown action — no-op
            return
        }

        let body = ApprovalDecisionBody(decision: decision)
        let endpoint = "/api/v1/approvals/\(requestId.uuidString)/decide"

        // POST the decision. We discard the response body — only the request being sent matters.
        // DecodingErrors are swallowed: the approval endpoint may return a minimal body that
        // doesn't decode to _VoidResponse; what matters is the HTTP request was accepted.
        do {
            let _: _VoidResponse = try await apiClient.request(endpoint, method: "POST", body: body)
        } catch APIError.decodingError {
            // Response body format is irrelevant for fire-and-forget approval decisions.
            // The POST was sent; any decoding issue on the response is benign here.
        }
    }

    // MARK: - Private helpers

    /// Registers the APPROVAL notification category with Approve/Deny actions.
    /// Both actions require device authentication (biometrics/passcode) per SPEC.md §29.6.
    private func registerCategories() {
        let approveAction = UNNotificationAction(
            identifier: Self.approveActionID,
            title: "Approve",
            options: [.authenticationRequired]
        )
        let denyAction = UNNotificationAction(
            identifier: Self.denyActionID,
            title: "Deny",
            options: [.authenticationRequired]
        )
        let approvalCategory = UNNotificationCategory(
            identifier: Self.approvalCategoryID,
            actions: [approveAction, denyAction],
            intentIdentifiers: [],
            options: []
        )
        center.setNotificationCategories([approvalCategory])
    }

    /// Extracts notification fields from any Codable payload via JSON round-trip.
    /// This avoids coupling to a specific payload type, enabling both production
    /// (NotificationPayload) and test (PushPayload) types to work with the same method.
    private nonisolated func extractFields<P: Codable>(from payload: P) -> _ExtractedFields {
        guard
            let data = try? JSONEncoder().encode(payload),
            let dict = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else {
            return _ExtractedFields(notificationType: "", riskTier: "")
        }
        let type_ = dict["notification_type"] as? String ?? ""
        let tier = dict["risk_tier"] as? String ?? ""
        return _ExtractedFields(notificationType: type_, riskTier: tier)
    }
}

// MARK: - Supporting private types

private struct _ExtractedFields {
    let notificationType: String
    let riskTier: String
}

/// Minimal decodable for endpoints that return an empty body or irrelevant data.
private struct _VoidResponse: Decodable, Sendable {}
