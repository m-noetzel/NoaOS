// QueuedRequest.swift — Persistent model for offline-queued HTTP requests
// Spec ref: SPEC.md §29.3 item 6, §25.4
// Phase: iOS9

import Foundation

/// A Codable model representing a write request that was queued while offline.
///
/// Each request carries its own idempotency key so the backend can safely de-duplicate
/// when the same request is retried after network restore (SPEC.md §25.4).
public struct QueuedRequest: Codable, Sendable {

    /// Idempotency key — doubles as the stable identifier for this queued entry.
    /// UUIDs are used so the same key is sent on every retry.
    public let id: String

    /// Relative API endpoint (e.g. "/api/v1/threads/123/messages").
    public let endpoint: String

    /// HTTP method ("POST", "PUT", "PATCH").
    public let method: String

    /// Pre-encoded JSON body, or nil for body-less requests.
    public let bodyData: Data?

    /// Number of failed attempts so far. Starts at 0; dropped when it reaches `maxRetries`.
    public let retryCount: Int

    /// Timestamp when the request was first queued (preserved across retries).
    public let enqueuedAt: Date

    // MARK: - Init

    /// Creates a new queued request, typically when the network is unavailable.
    public init(
        endpoint: String,
        method: String,
        bodyData: Data?,
        idempotencyKey: String = UUID().uuidString
    ) {
        self.id = idempotencyKey
        self.endpoint = endpoint
        self.method = method
        self.bodyData = bodyData
        self.retryCount = 0
        self.enqueuedAt = Date()
    }

    /// Internal copy constructor used by `withIncrementedRetry()`.
    private init(copying other: QueuedRequest, retryCount: Int) {
        self.id = other.id
        self.endpoint = other.endpoint
        self.method = other.method
        self.bodyData = other.bodyData
        self.retryCount = retryCount
        self.enqueuedAt = other.enqueuedAt
    }

    /// Returns a new `QueuedRequest` with `retryCount` incremented by 1.
    /// The idempotency key and all other fields are preserved.
    public func withIncrementedRetry() -> QueuedRequest {
        QueuedRequest(copying: self, retryCount: retryCount + 1)
    }
}
