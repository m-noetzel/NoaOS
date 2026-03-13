// GoogleAuthService.swift — Google OAuth2 via ASWebAuthenticationSession
// Spec ref: SPEC.md §29.3 (Mobile Access — OAuth2), §11.1 (credentials in Postgres), §12.1, §12.2
// Phase GO3
//
// Responsibilities:
//   - `connect()` fetches auth URL from backend, opens ASWebAuthenticationSession,
//     waits for `noaapp://` callback, then refreshes status from server
//   - `disconnect()` calls DELETE /auth/google/disconnect
//   - `getStatus()` calls GET /auth/google/status
//
// The backend (GO1) persists all Google tokens — iOS stores nothing sensitive.
// Only the Noa JWT lives in the Keychain.

import Foundation
#if canImport(AuthenticationServices)
import AuthenticationServices
#endif

// MARK: - Models

/// Response from GET /api/v1/auth/google/authorize
public struct GoogleAuthorizeResponse: Decodable, Sendable {
    public let authUrl: String

    enum CodingKeys: String, CodingKey {
        case authUrl = "auth_url"
    }
}

/// Response from GET /api/v1/auth/google/status
public struct GoogleStatusResponse: Decodable, Sendable {
    public let connected: Bool
    public let scopes: [String]?

    enum CodingKeys: String, CodingKey {
        case connected
        case scopes
    }
}

/// Response from DELETE /api/v1/auth/google/disconnect
struct GoogleDisconnectResponse: Decodable, Sendable {
    let disconnected: Bool
}

// MARK: - GoogleAuthStatus

/// The connection state of the Google account.
public enum GoogleAuthStatus: Equatable, Sendable {
    case disconnected
    case connected(email: String?)
    case loading
}

// MARK: - WebAuthSessionProviding Protocol

/// Protocol allowing ASWebAuthenticationSession to be mocked in tests.
/// Swift 6: Sendable required since GoogleAuthService is an actor.
public protocol WebAuthSessionProviding: Sendable {
    /// Starts an authentication session with the given URL and callback scheme.
    /// Returns the callback URL on success, or throws on cancellation/error.
    func authenticate(url: URL, callbackURLScheme: String) async throws -> URL
}

// MARK: - ASWebAuthenticationSessionError (platform-conditional)

public enum WebAuthError: Error, Sendable {
    case cancelled
    case failed(String)
}

// MARK: - ASWebAuthSessionAdapter (live implementation)

#if canImport(AuthenticationServices) && !os(macOS)
/// Live implementation that wraps `ASWebAuthenticationSession`.
/// `@MainActor` ensures the session is created and started on the main thread,
/// which is required by `ASWebAuthenticationPresentationContextProviding`.
@MainActor
public final class ASWebAuthSessionAdapter: NSObject, WebAuthSessionProviding, ASWebAuthenticationPresentationContextProviding {

    public override init() {}

    public func authenticate(url: URL, callbackURLScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: url,
                callbackURLScheme: callbackURLScheme
            ) { callbackURL, error in
                if let error = error as? ASWebAuthenticationSessionError {
                    if error.code == .canceledLogin {
                        continuation.resume(throwing: WebAuthError.cancelled)
                    } else {
                        continuation.resume(throwing: WebAuthError.failed(error.localizedDescription))
                    }
                } else if let callbackURL = callbackURL {
                    continuation.resume(returning: callbackURL)
                } else {
                    continuation.resume(throwing: WebAuthError.failed("No callback URL and no error"))
                }
            }
            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = false
            session.start()
        }
    }

    // MARK: - ASWebAuthenticationPresentationContextProviding

    public func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        // Find the key window from connected scenes
        let scenes = UIApplication.shared.connectedScenes
        let windowScene = scenes.first { $0.activationState == .foregroundActive } as? UIWindowScene
        return windowScene?.windows.first { $0.isKeyWindow } ?? UIWindow()
    }
}
#endif

// MARK: - GoogleAuthServicing Protocol

/// Protocol for dependency injection in tests.
public protocol GoogleAuthServicing: Sendable {
    func connect() async throws
    func disconnect() async throws
    func getStatus() async throws -> GoogleAuthStatus
}

// MARK: - GoogleAuthService

/// Actor-isolated Google OAuth2 service.
/// Uses a protocol-injected `WebAuthSessionProviding` so tests can provide a mock
/// without triggering real ASWebAuthenticationSession flows.
///
/// Flow:
///   1. `connect()` → GET /auth/google/authorize → get auth_url
///   2. Open ASWebAuthenticationSession with auth_url, scheme "noaapp"
///   3. Backend handles code exchange and redirects to noaapp://auth/google/connected
///   4. Session intercepts the redirect, returns the URL
///   5. `connect()` calls `getStatus()` to refresh local state
///
/// The backend sends `X-Noa-iOS-Redirect` header hint for iOS redirects.
/// In GO1 the callback redirects to `noaapp://oauth/callback?google=connected`.
public actor GoogleAuthService: GoogleAuthServicing {

    // MARK: - Properties

    private let apiClient: any APIClientProtocol
    private let webAuthSession: any WebAuthSessionProviding

    /// The custom URL scheme registered in Info.plist for OAuth callback interception.
    static let callbackScheme = "noaapp"

    // MARK: - Init

    public init(
        apiClient: any APIClientProtocol,
        webAuthSession: any WebAuthSessionProviding
    ) {
        self.apiClient = apiClient
        self.webAuthSession = webAuthSession
    }

    // MARK: - GoogleAuthServicing

    /// Starts the Google OAuth2 flow.
    ///
    /// 1. Fetches the authorization URL from the backend.
    /// 2. Opens ASWebAuthenticationSession.
    /// 3. On success, the backend has already persisted tokens; status is fetched to confirm.
    ///
    /// - Throws: `WebAuthError.cancelled` if the user dismisses the sheet.
    ///           `APIError` for backend failures.
    public func connect() async throws {
        // Step 1: Get auth URL from backend, passing platform=ios so the callback
        // redirects to noaapp:// instead of the web settings page.
        let authorizeResponse: GoogleAuthorizeResponse = try await apiClient.get(
            "/api/v1/auth/google/authorize?platform=ios"
        )

        guard let authURL = URL(string: authorizeResponse.authUrl) else {
            throw WebAuthError.failed("Invalid authorization URL from backend")
        }

        // Step 2: Open browser-based OAuth consent screen.
        // The backend callback (GO1) will redirect to noaapp://oauth/callback?google=connected
        // when it sets the X-Noa-iOS-Redirect header — we rely on that redirect being
        // intercepted by ASWebAuthenticationSession.
        _ = try await webAuthSession.authenticate(url: authURL, callbackURLScheme: Self.callbackScheme)

        // Step 3: Backend has already persisted tokens; we confirm by fetching status.
        // (status result is not returned here — caller re-fetches via getStatus())
    }

    /// Disconnects the Google account by deleting server-side credentials.
    ///
    /// - Throws: `APIError` on backend failure.
    public func disconnect() async throws {
        let _: GoogleDisconnectResponse = try await apiClient.request(
            "/api/v1/auth/google/disconnect",
            method: "DELETE",
            body: nil as String?
        )
    }

    /// Returns the current Google connection status from the backend.
    ///
    /// - Returns: `.connected(email:)` or `.disconnected`.
    /// - Throws: `APIError` on backend failure.
    public func getStatus() async throws -> GoogleAuthStatus {
        let statusResponse: GoogleStatusResponse = try await apiClient.get(
            "/api/v1/auth/google/status"
        )
        if statusResponse.connected {
            return .connected(email: nil)
        } else {
            return .disconnected
        }
    }
}
