// RunModels.swift — Run, RunEvent, RunStatus, RiskTier, PrivacyMode
// Spec ref: SPEC.md §22.1, §22.2

import Foundation

// MARK: - RunStatus

/// Lifecycle states of a Run. Mirrors VALID_STATUSES in noa/runs/schemas.py.
public enum RunStatus: String, Codable, Sendable {
    case pending
    case running
    case awaitingApproval = "awaiting_approval"
    case completed
    case failed
    case cancelled
}

// MARK: - RiskTier

/// Risk classification of a Run. Mirrors VALID_RISK_TIERS in noa/runs/schemas.py.
/// NOTE: If the backend adds new values, decoding falls back gracefully via `unknown`.
public enum RiskTier: String, Codable, Sendable {
    case low
    case medium
    case high
    /// Forward-compatibility catch-all for future backend values.
    case unknown

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let rawValue = try container.decode(String.self)
        self = RiskTier(rawValue: rawValue) ?? .unknown
    }
}

// MARK: - PrivacyMode

/// Domain routing mode for a Run.
public enum PrivacyMode: String, Codable, Sendable {
    case `private`
    case external
}

// MARK: - Run

/// A run (task execution session). Mirrors RunRead Pydantic schema.
/// Spec ref: SPEC.md §22.1
public struct Run: Codable, Sendable, Identifiable {
    public let id: UUID
    public let threadId: UUID
    public let userId: UUID
    public let status: RunStatus
    public let riskTier: RiskTier
    public let privacyMode: PrivacyMode
    public let summary: String?
    public let createdAt: Date
    public let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case threadId = "thread_id"
        case userId = "user_id"
        case status
        case riskTier = "risk_tier"
        case privacyMode = "privacy_mode"
        case summary
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    public init(
        id: UUID,
        threadId: UUID,
        userId: UUID,
        status: RunStatus,
        riskTier: RiskTier,
        privacyMode: PrivacyMode,
        summary: String?,
        createdAt: Date,
        updatedAt: Date
    ) {
        self.id = id
        self.threadId = threadId
        self.userId = userId
        self.status = status
        self.riskTier = riskTier
        self.privacyMode = privacyMode
        self.summary = summary
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

// MARK: - RunEvent

/// A single event emitted during a Run. Mirrors EventRead Pydantic schema.
/// Spec ref: SPEC.md §22.2
public struct RunEvent: Codable, Sendable, Identifiable {
    public let id: UUID
    public let runId: UUID
    /// Raw event type string from the backend (e.g. "token_stream", "approval_requested").
    public let eventType: String
    public let timestamp: Date
    /// Free-form payload; structure varies by event type.
    public let payload: [String: AnyCodable]

    enum CodingKeys: String, CodingKey {
        case id
        case runId = "run_id"
        case eventType = "event_type"
        case timestamp
        case payload
    }

    public init(
        id: UUID,
        runId: UUID,
        eventType: String,
        timestamp: Date,
        payload: [String: AnyCodable]
    ) {
        self.id = id
        self.runId = runId
        self.eventType = eventType
        self.timestamp = timestamp
        self.payload = payload
    }

    /// The parsed SSE event type, or nil for unknown/future types.
    public var type: SSEEventType? {
        SSEEventType(rawValue: eventType)
    }
}
