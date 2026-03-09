// DeepLinkRouter.swift — Navigation routing from push notification payloads
// Spec ref: SPEC.md §29.5, §29.6, Phase iOS6 deliverable 5/6
//
// Responsibilities:
//   - Parse incoming notification payloads (only spec-defined fields)
//   - Route to the correct in-app destination
//   - Forward-compatible: unknown types fall back to .home without crashing

import Foundation

// MARK: - NotificationPayload

/// Decoded push notification payload.
/// Only reads the three spec-defined fields per SPEC.md §29.5.
/// Extra JSON keys are silently ignored for forward compatibility (T17/T19).
public struct NotificationPayload: Codable, Sendable {
    public let notificationType: String
    public let requestId: UUID
    public let riskTier: String

    enum CodingKeys: String, CodingKey {
        case notificationType = "notification_type"
        case requestId = "request_id"
        case riskTier = "risk_tier"
    }

    public init(notificationType: String, requestId: UUID, riskTier: String) {
        self.notificationType = notificationType
        self.requestId = requestId
        self.riskTier = riskTier
    }
}

// MARK: - DeepLinkDestination

/// In-app navigation destination derived from a push notification.
/// Spec ref: Phase iOS6 deliverable 5/6
public enum DeepLinkDestination: Equatable, Sendable {
    /// Navigate to the approval detail view for the given request ID.
    case approval(id: UUID)
    /// Navigate to the run detail view for the given run ID.
    case runDetail(id: UUID)
    /// Navigate to the home / default screen.
    case home
}

// MARK: - DeepLinkRouter

/// Pure value type that maps notification payloads to in-app navigation destinations.
/// Routing is deterministic: same input always produces the same output.
/// Spec ref: SPEC.md §29.6, Phase iOS6 deliverable 6
public struct DeepLinkRouter: Sendable {

    public init() {}

    /// Returns the navigation destination for the given notification payload.
    ///
    /// - `approval_requested` → `.approval(id: payload.requestId)`
    /// - `run_completed` / `run_failed` → `.runDetail(id: payload.requestId)`
    /// - Unknown types → `.home` (forward compatibility per T17)
    ///
    /// This method is generic so test types (e.g. local `NotificationPayload` structs)
    /// and production types can both be used without nominal type coupling.
    public func destination<P: Codable & Sendable>(for payload: P) -> DeepLinkDestination {
        let fields = extractFields(from: payload)
        switch fields.notificationType {
        case "approval_requested":
            return fields.requestId.map { .approval(id: $0) } ?? .home
        case "run_completed", "run_failed":
            return fields.requestId.map { .runDetail(id: $0) } ?? .home
        default:
            return .home
        }
    }

    // MARK: - Private helpers

    private struct _Fields {
        let notificationType: String
        let requestId: UUID?
    }

    /// Extracts routing fields via JSON round-trip, accepting any Codable payload type.
    private func extractFields<P: Codable>(from payload: P) -> _Fields {
        guard
            let data = try? JSONEncoder().encode(payload),
            let dict = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else {
            return _Fields(notificationType: "", requestId: nil)
        }
        let type_ = dict["notification_type"] as? String ?? ""
        let requestId: UUID?
        if let idStr = dict["request_id"] as? String {
            requestId = UUID(uuidString: idStr)
        } else {
            requestId = nil
        }
        return _Fields(notificationType: type_, requestId: requestId)
    }
}

