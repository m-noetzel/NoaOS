// APIClientProtocol.swift — Protocol for dependency injection in tests
// Spec ref: PLAN Phase iOS3, QA M7 (wiring completeness)

import Foundation

/// Token provider protocol — decouples APIClient from Keychain implementation (iOS4).
/// Allows tests to inject mock token providers without touching Keychain.
public protocol TokenProviding: Sendable {
    /// Returns the current access token, or nil if the user is unauthenticated.
    func accessToken() async -> String?
    /// Attempts to refresh the token using the stored refresh token.
    /// Returns the new access token on success, or throws on failure.
    func refreshAccessToken() async throws -> String
}

/// HTTP client protocol for dependency injection in tests and SwiftUI previews.
public protocol APIClientProtocol: Sendable {
    /// Performs a generic HTTP request and decodes the response body as `T`.
    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T

    /// Returns `true` if the client has a valid (non-nil) access token available.
    /// Used to guard API calls that must not be made when the user is unauthenticated.
    /// Default implementation returns `false`; override in concrete clients.
    func isAuthenticated() async -> Bool
}

public extension APIClientProtocol {
    /// Convenience: GET request.
    func get<T: Decodable & Sendable>(_ endpoint: String) async throws -> T {
        try await request(endpoint, method: "GET", body: nil as String?)
    }

    /// Convenience: POST request with a body.
    func post<T: Decodable & Sendable, B: Encodable & Sendable>(_ endpoint: String, body: B) async throws -> T {
        try await request(endpoint, method: "POST", body: body)
    }

    /// Convenience: POST request without a body.
    func post<T: Decodable & Sendable>(_ endpoint: String) async throws -> T {
        try await request(endpoint, method: "POST", body: nil as String?)
    }

    /// Default: unauthenticated. Concrete clients (e.g. APIClient) override this.
    func isAuthenticated() async -> Bool { return false }
}
