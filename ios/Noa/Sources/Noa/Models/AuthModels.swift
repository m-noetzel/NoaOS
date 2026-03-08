// AuthModels.swift — Authentication-related model types
// Spec ref: SPEC.md §5.1–5.4, §29.3

import Foundation

/// Request body for POST /api/v1/auth/login.
public struct LoginRequest: Codable, Sendable {
    public let username: String
    public let password: String

    public init(username: String, password: String) {
        self.username = username
        self.password = password
    }
}

/// Successful authentication token response.
public struct AuthTokens: Codable, Sendable {
    /// Short-lived JWT bearer token.
    public let accessToken: String
    /// Long-lived refresh token.
    public let refreshToken: String
    /// Always "bearer".
    public let tokenType: String
    /// Seconds until `accessToken` expires.
    public let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
    }

    public init(
        accessToken: String,
        refreshToken: String,
        tokenType: String,
        expiresIn: Int
    ) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.tokenType = tokenType
        self.expiresIn = expiresIn
    }
}

/// Request body for POST /api/v1/auth/refresh.
public struct RefreshRequest: Codable, Sendable {
    public let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }

    public init(refreshToken: String) {
        self.refreshToken = refreshToken
    }
}
