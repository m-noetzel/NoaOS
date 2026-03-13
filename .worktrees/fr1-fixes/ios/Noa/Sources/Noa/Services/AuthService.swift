// AuthService.swift — Authentication operations with Keychain persistence
// Spec ref: SPEC.md §5.1–5.4, §29.3, Phase iOS4 deliverable 3
//
// Handles login, token refresh, and logout, persisting tokens to the
// Keychain. Conforms to `TokenProviding` so `APIClient` can use it for
// automatic Bearer token injection and 401-triggered refresh.

import Foundation

/// Placeholder decodable for endpoints that return an empty body.
private struct _EmptyBody: Decodable, Sendable {}

// MARK: - AuthService

/// Actor-isolated auth service. Thread-safe by default.
public actor AuthService: TokenProviding {

    // MARK: - Keychain account labels

    private static let accessTokenAccount = "access_token"
    private static let refreshTokenAccount = "refresh_token"

    // MARK: - Properties

    private let apiClient: any APIClientProtocol
    /// The Keychain service namespace (e.g. `"com.noa.tokens"`).
    /// `let` on an actor is nonisolated — safe to read from any context.
    let keychainNamespace: String
    /// Seconds remaining until the access token is considered near-expiry.
    private var tokenExpiresAt: Date?

    // MARK: - Init

    public init(apiClient: any APIClientProtocol, keychainService: String) {
        self.apiClient = apiClient
        self.keychainNamespace = keychainService
    }

    // MARK: - Public API

    /// Authenticates with the server and stores the resulting tokens in the Keychain.
    ///
    /// - Parameters:
    ///   - username: The user's email address.
    ///   - password: The user's password.
    /// - Throws: `APIError` on authentication failure. No tokens are stored on failure.
    public func login(username: String, password: String) async throws {
        let body = LoginRequest(
            email: username,
            password: password,
            deviceId: DeviceID.current
        )
        let tokens: AuthTokens = try await apiClient.request(
            "/api/v1/auth/login",
            method: "POST",
            body: body
        )
        storeTokens(tokens)
    }

    /// Refreshes the access token using the stored refresh token.
    ///
    /// On success, both tokens are rotated and stored in the Keychain.
    /// - Throws: `APIError.unauthorized` if the refresh token is missing or rejected.
    public func refresh() async throws {
        guard let refreshToken = KeychainService.read(
            service: keychainNamespace,
            account: Self.refreshTokenAccount
        ) else {
            throw APIError.unauthorized
        }
        let body = RefreshRequest(refreshToken: refreshToken, deviceId: DeviceID.current)
        let tokens: AuthTokens = try await apiClient.request(
            "/api/v1/auth/refresh",
            method: "POST",
            body: body
        )
        storeTokens(tokens)
    }

    /// Logs out the current session: calls the server and clears Keychain tokens.
    public func logout() async throws {
        // Best-effort server call — clear tokens regardless of result.
        _ = try? await apiClient.request("/api/v1/auth/logout", method: "POST", body: nil as String?) as _EmptyBody
        clearTokens()
    }

    /// Returns the current access token from the Keychain, or `nil` if unauthenticated.
    public func accessToken() async -> String? {
        KeychainService.read(service: keychainNamespace, account: Self.accessTokenAccount)
    }

    /// Returns the date at which the current access token expires, or `nil` if not set.
    public func tokenExpiry() async -> Date? {
        tokenExpiresAt
    }

    // MARK: - TokenProviding

    /// Refreshes the access token (used by `APIClient` on 401).
    /// - Returns: The new access token string.
    public func refreshAccessToken() async throws -> String {
        try await refresh()
        guard let token = KeychainService.read(
            service: keychainNamespace,
            account: Self.accessTokenAccount
        ) else {
            throw APIError.unauthorized
        }
        return token
    }

    // MARK: - Private

    private func storeTokens(_ tokens: AuthTokens) {
        KeychainService.save(
            value: tokens.accessToken,
            service: keychainNamespace,
            account: Self.accessTokenAccount
        )
        KeychainService.save(
            value: tokens.refreshToken,
            service: keychainNamespace,
            account: Self.refreshTokenAccount
        )
        tokenExpiresAt = Date().addingTimeInterval(TimeInterval(tokens.expiresIn))
    }

    private func clearTokens() {
        KeychainService.delete(service: keychainNamespace, account: Self.accessTokenAccount)
        KeychainService.delete(service: keychainNamespace, account: Self.refreshTokenAccount)
        tokenExpiresAt = nil
    }
}
