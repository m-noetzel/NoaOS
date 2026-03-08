// ApiResponse.swift — Standard response envelope
// Spec ref: SPEC.md §25.3 — All API responses follow a consistent envelope.
// Shape: {"ok": bool, "data": T?, "error": {"code": str, "message": str}?, "trace_id": str}

import Foundation

/// The error payload nested inside an `ApiResponse` when `ok == false`.
public struct ApiErrorPayload: Codable, Sendable {
    /// Machine-readable error code (e.g. "AUTH_TOKEN_EXPIRED").
    public let code: String
    /// Human-readable error message.
    public let message: String

    public init(code: String, message: String) {
        self.code = code
        self.message = message
    }
}

/// Generic API response envelope matching the backend's §25.3 contract.
/// Every endpoint returns this shape.
public struct ApiResponse<T: Decodable>: Decodable, @unchecked Sendable {
    /// `true` on success, `false` on error.
    public let ok: Bool
    /// The payload on success; `nil` on error.
    public let data: T?
    /// The error detail on failure; `nil` on success.
    public let error: ApiErrorPayload?
    /// Trace identifier for debugging (present on both success and error).
    public let traceId: String?

    enum CodingKeys: String, CodingKey {
        case ok
        case data
        case error
        case traceId = "trace_id"
    }

    public init(ok: Bool, data: T?, error: ApiErrorPayload?, traceId: String?) {
        self.ok = ok
        self.data = data
        self.error = error
        self.traceId = traceId
    }
}

/// Typed errors surfaced by `APIClient` to callers.
public enum APIError: Error, Sendable {
    /// HTTP 401 — token expired and refresh also failed.
    case unauthorized
    /// HTTP 403 — authenticated but not permitted.
    case forbidden
    /// HTTP 404 — resource not found.
    case notFound
    /// HTTP 429 — too many requests.
    case rateLimited(retryAfter: TimeInterval?)
    /// HTTP 4xx/5xx with a parsed error body.
    case serverError(code: String, message: String)
    /// Network-level failure (DNS, connection refused, timeout, etc.).
    case networkError(underlying: Error)
    /// Response body could not be decoded.
    case decodingError(underlying: Error)
    /// Unexpected state.
    case unknown(statusCode: Int)
}
