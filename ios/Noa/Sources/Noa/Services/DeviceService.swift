// DeviceService.swift — APNs device token registration with backend
// Spec ref: SPEC.md §29.5, Phase iOS6 deliverable 3
//
// Responsibilities:
//   - POST /api/v1/devices/push-token on APNs token receipt
//   - DELETE /api/v1/devices/push-token on logout
//   - Hex-encode the raw token data (no angle brackets)
//   - Guard registration behind authentication check (no call when unauthenticated)
//   - Track local registration state (isTokenRegistered)

import Foundation

// MARK: - Request/response types

private struct RegisterTokenBody: Encodable, Sendable {
    let deviceId: String
    let platform: String
    let pushToken: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case platform
        case pushToken = "push_token"
    }
}

private struct UnregisterTokenBody: Encodable, Sendable {
    let deviceId: String
    let pushToken: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case pushToken = "push_token"
    }
}

private struct _VoidResponse: Decodable, Sendable {}

// MARK: - DeviceService

/// Actor-isolated service for managing device push token registration.
/// Spec ref: SPEC.md §29.5
public actor DeviceService {

    // MARK: - Properties

    private let apiClient: any APIClientProtocol
    /// The raw token data currently registered (nil if not registered).
    private var registeredTokenData: Data?

    /// `true` when a device token has been successfully registered with the backend.
    public var isTokenRegistered: Bool {
        registeredTokenData != nil
    }

    // MARK: - Init

    public init(apiClient: any APIClientProtocol) {
        self.apiClient = apiClient
    }

    // MARK: - Token registration

    /// Registers the given APNs token data with the backend.
    ///
    /// Skips the API call silently if the user is not authenticated (no access token).
    /// Spec ref: SPEC.md §29.5
    ///
    /// - Parameter tokenData: Raw bytes from `didRegisterForRemoteNotificationsWithDeviceToken`.
    /// - Throws: `APIError` on network or server errors. Token is NOT marked as registered on failure.
    public func registerToken(tokenData: Data) async throws {
        // Guard: do not send device token when unauthenticated.
        guard await apiClient.isAuthenticated() else { return }

        let hexToken = Self.hexEncode(tokenData)
        let body = RegisterTokenBody(
            deviceId: DeviceID.current,
            platform: "ios",
            pushToken: hexToken
        )

        let _: _VoidResponse = try await apiClient.request(
            "/api/v1/devices/push-token",
            method: "POST",
            body: body
        )

        // Only mark as registered after a successful response.
        registeredTokenData = tokenData
    }

    // MARK: - Token unregistration

    /// Unregisters the device token from the backend (call on logout).
    ///
    /// Sends the stored token data in the DELETE body.
    /// Clears local registration state on success.
    /// Spec ref: SPEC.md §29.5 — failure to unregister = privacy violation.
    ///
    /// - Throws: `APIError` if the network or server call fails.
    public func unregisterToken() async throws {
        guard let tokenData = registeredTokenData else { return }

        let hexToken = Self.hexEncode(tokenData)
        let body = UnregisterTokenBody(
            deviceId: DeviceID.current,
            pushToken: hexToken
        )

        let _: _VoidResponse = try await apiClient.request(
            "/api/v1/devices/push-token",
            method: "DELETE",
            body: body
        )

        // Clear local state after successful unregistration.
        registeredTokenData = nil
    }

    // MARK: - Test helpers

    /// Sets the currently registered token data without making a network call.
    /// Used in tests to simulate a previously registered state.
    public func setRegisteredToken(_ tokenData: Data) {
        registeredTokenData = tokenData
    }

    // MARK: - Hex encoding

    /// Encodes raw `Data` as a lowercase hex string without angle brackets or spaces.
    ///
    /// This is the correct way to convert APNs token data — `Data.description`
    /// produces format like `<aabbcc dd>` which is not accepted by backends.
    ///
    /// - Parameter data: The raw bytes to encode.
    /// - Returns: Lowercase hex string (e.g. `"aabbccdd"`).
    public static func hexEncode(_ data: Data) -> String {
        data.map { String(format: "%02x", $0) }.joined()
    }
}
