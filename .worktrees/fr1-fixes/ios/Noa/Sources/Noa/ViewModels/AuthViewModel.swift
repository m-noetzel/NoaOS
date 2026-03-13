// AuthViewModel.swift — Observable auth state management
// Spec ref: SPEC.md §5.1–5.4, §29.3, Phase iOS4 deliverable 4 & 7
//
// Manages authentication state, exposes login/logout actions for LoginView,
// and handles automatic token refresh when the app returns to the foreground.

import Foundation
import Observation

/// Auto-refresh threshold: refresh if token expires within this many seconds.
private let autoRefreshThresholdSeconds: TimeInterval = 60

// MARK: - AuthViewModel

/// Observable auth state for SwiftUI binding.
/// Not MainActor-isolated so it can be constructed and tested freely;
/// SwiftUI's Observation framework handles UI-thread delivery automatically.
@Observable
@MainActor
public final class AuthViewModel {

    // MARK: - Published state

    /// `true` when a valid access token is present in the Keychain.
    public var isAuthenticated: Bool = false
    /// Non-nil after a failed login attempt; cleared on the next successful login.
    public var errorMessage: String?

    // MARK: - Private state

    private let authService: AuthService
    /// Expiry date of the current access token (set after login/refresh).
    var tokenExpiresAt: Date?

    // MARK: - Init

    public init(authService: AuthService) {
        self.authService = authService
        // Check Keychain synchronously on init for immediate state.
        let hasToken = KeychainService.read(
            service: authService.keychainNamespace,
            account: "access_token"
        ) != nil
        isAuthenticated = hasToken
        // On cold start, set expiry to the past so handleAppForeground() will
        // trigger a token refresh — the stored token may have expired.
        tokenExpiresAt = hasToken ? .distantPast : nil
    }

    // MARK: - Public actions

    /// Logs in with the given credentials. Throws on failure.
    /// Prefer `loginAttempt` for UI bindings that should not propagate errors.
    public func login(username: String, password: String) async throws {
        try await authService.login(username: username, password: password)
        let expiry = await authService.tokenExpiry()
        isAuthenticated = true
        errorMessage = nil
        tokenExpiresAt = expiry
    }

    /// Non-throwing login wrapper. Sets `errorMessage` on failure.
    public func loginAttempt(username: String, password: String) async {
        do {
            try await login(username: username, password: password)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Logs out the current user and clears Keychain state.
    public func logout() async throws {
        try await authService.logout()
        isAuthenticated = false
        tokenExpiresAt = nil
    }

    /// Called when an API request receives an unrecoverable 401 (refresh also failed).
    ///
    /// Sets `isAuthenticated = false` so that `AuthGuard` transitions to `LoginView`.
    /// This is the iOS-H3 fix: previously a stale-token 401 would leave the app showing
    /// the main UI while all API calls silently failed.
    public func handleUnauthorized() {
        isAuthenticated = false
        tokenExpiresAt = nil
    }

    /// Called when the app enters the foreground.
    /// Refreshes the access token if it will expire within the threshold.
    public func handleAppForeground() async {
        guard isAuthenticated,
              let expiry = tokenExpiresAt,
              expiry.timeIntervalSinceNow <= autoRefreshThresholdSeconds
        else { return }

        do {
            try await authService.refresh()
            let newExpiry = await authService.tokenExpiry()
            tokenExpiresAt = newExpiry
        } catch {
            // On refresh failure, mark unauthenticated so AuthGuard shows LoginView.
            isAuthenticated = false
        }
    }
}
