// ApprovalService.swift — Approval API calls (fetch pending, decide)
// Spec ref: SPEC.md §29.6, §23.2, Phase iOS7 deliverable 2
//
// Endpoints:
//   GET  /api/v1/approvals/pending         → [Approval]
//   POST /api/v1/approvals/{id}/decide     → void (decision recorded)

import Foundation

// MARK: - ApprovalServicing

/// Protocol for dependency injection in tests.
public protocol ApprovalServicing: Sendable {
    /// Fetches all pending approvals for the current user.
    func fetchPending() async throws -> [Approval]
    /// Submits an approve or deny decision for the given approval.
    func decide(id: UUID, decision: ApprovalStatus) async throws
}

// MARK: - Response types

/// Decodable for the decide endpoint response body (fields are not consumed).
private struct _DecisionResponse: Decodable, Sendable {}

// MARK: - ApprovalService

/// Actor-isolated service for approval API operations.
/// Spec ref: SPEC.md §29.6
public actor ApprovalService: ApprovalServicing {

    private let apiClient: any APIClientProtocol

    public init(apiClient: any APIClientProtocol) {
        self.apiClient = apiClient
    }

    // MARK: - ApprovalServicing

    /// Fetches pending approvals for the authenticated user.
    /// GET /api/v1/approvals/pending
    public func fetchPending() async throws -> [Approval] {
        try await apiClient.get("/api/v1/approvals/pending")
    }

    /// Submits an approval decision.
    /// POST /api/v1/approvals/{id}/decide
    ///
    /// - Parameters:
    ///   - id: The approval UUID.
    ///   - decision: `.approved` or `.denied`.
    public func decide(id: UUID, decision: ApprovalStatus) async throws {
        let body = ApprovalDecision(decision: decision)
        let _: _DecisionResponse = try await apiClient.request(
            "/api/v1/approvals/\(id.uuidString.lowercased())/decide",
            method: "POST",
            body: body
        )
    }
}
