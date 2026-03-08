// ApprovalModels.swift — Approval, ApprovalDecision
// Spec ref: SPEC.md §29.6

import Foundation

// MARK: - ApprovalStatus

/// Decision status for an approval request.
public enum ApprovalStatus: String, Codable, Sendable {
    case pending
    case approved
    case denied
}

// MARK: - Approval

/// A pending or decided approval request. Mirrors the backend Approval schema.
/// Spec ref: SPEC.md §29.6
public struct Approval: Codable, Sendable, Identifiable {
    public let id: UUID
    public let runId: UUID
    public let userId: UUID
    public let riskTier: RiskTier
    /// Human-readable description of the action requiring approval. May be nil.
    public let previewText: String?
    /// Current decision state.
    public let decision: ApprovalStatus
    /// Domain (e.g. "external") for the action requiring approval.
    public let domain: String
    public let requestedAt: Date
    /// Date the decision was made; nil while still pending.
    public let decidedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case runId = "run_id"
        case userId = "user_id"
        case riskTier = "risk_tier"
        case previewText = "preview_text"
        case decision
        case domain
        case requestedAt = "requested_at"
        case decidedAt = "decided_at"
    }

    public init(
        id: UUID,
        runId: UUID,
        userId: UUID,
        riskTier: RiskTier,
        previewText: String?,
        decision: ApprovalStatus,
        domain: String,
        requestedAt: Date,
        decidedAt: Date?
    ) {
        self.id = id
        self.runId = runId
        self.userId = userId
        self.riskTier = riskTier
        self.previewText = previewText
        self.decision = decision
        self.domain = domain
        self.requestedAt = requestedAt
        self.decidedAt = decidedAt
    }
}

// MARK: - ApprovalDecision

/// Request body for POST /api/v1/approvals/{id}/decide.
public struct ApprovalDecision: Codable, Sendable {
    /// "approved" or "denied".
    public let decision: ApprovalStatus

    public init(decision: ApprovalStatus) {
        self.decision = decision
    }
}
