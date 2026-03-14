// SettingsViewModel.swift — Observable settings state management
// Spec ref: SPEC.md §29.3 (Mobile Access — OAuth2), §12.1, §12.2
// Phase GO3
//
// Manages Google OAuth2 connection status and user-initiated connect/disconnect actions.
// Uses @Observable (Swift Observation framework, iOS 17+).

import Foundation
import Observation

// MARK: - Backend connection status (iOS-H5)

/// Connection state for the backend health check.
public enum BackendConnectionStatus: Sendable {
    case unknown
    case checking
    case reachable
    case unreachable(String)
}

/// Protocol for making health check HTTP requests.
/// Allows test doubles to replace the real URLSession without subclassing.
public protocol HealthCheckProviding: Sendable {
    func checkHealth(url: URL) async throws -> Int
}

/// Default implementation using URLSession.
public struct URLSessionHealthChecker: HealthCheckProviding {
    private let session: URLSession

    public init(session: URLSession = .shared) {
        self.session = session
    }

    public func checkHealth(url: URL) async throws -> Int {
        var request = URLRequest(url: url)
        request.timeoutInterval = 5
        let (_, response) = try await session.data(for: request)
        return (response as? HTTPURLResponse)?.statusCode ?? 0
    }
}

// MARK: - SettingsViewModel

/// Observable settings state for SwiftUI binding.
/// @MainActor ensures all UI state mutations happen on the main thread.
@Observable
@MainActor
public final class SettingsViewModel {

    // MARK: - Published state

    /// Current Google account connection status.
    public var googleStatus: GoogleAuthStatus = .loading
    /// Non-nil when an error should be shown to the user.
    public var errorMessage: String?
    /// `true` while a connect or disconnect request is in flight.
    public var isLoading: Bool = false
    /// `true` when the disconnect confirmation sheet should be visible.
    public var showDisconnectConfirmation: Bool = false

    // MARK: - iOS-H5: Backend connection status

    /// The base URL the app is connecting to.
    public var backendURL: String {
        NoaEnvironment.current.baseURL.absoluteString
    }

    /// Current connection status for the backend health check.
    public var backendStatus: BackendConnectionStatus = .unknown

    // MARK: - Private

    private let googleAuthService: any GoogleAuthServicing
    /// Optional biometric guard for the connect action (medium-risk per spec §29.3).
    /// When nil, connect proceeds without biometric prompt.
    private let biometricService: (any BiometricAuthenticating)?
    /// Health checker for pings — separate from APIClient so it works pre-auth.
    private let healthChecker: any HealthCheckProviding

    // MARK: - Init

    public init(
        googleAuthService: any GoogleAuthServicing,
        biometricService: (any BiometricAuthenticating)? = nil,
        healthChecker: (any HealthCheckProviding)? = nil
    ) {
        self.googleAuthService = googleAuthService
        self.biometricService = biometricService
        self.healthChecker = healthChecker ?? URLSessionHealthChecker()
    }

    // MARK: - iOS-H5: Backend health check

    /// Ping the backend health endpoint and update `backendStatus`.
    ///
    /// Uses `/health` which does not require authentication so it works
    /// even before login (useful for diagnosing connection issues).
    public func checkBackendHealth() async {
        backendStatus = .checking
        let base = NoaEnvironment.current.baseURL
        guard let url = URL(string: "/health", relativeTo: base)?.absoluteURL else {
            backendStatus = .unreachable("Invalid backend URL")
            return
        }
        do {
            let statusCode = try await healthChecker.checkHealth(url: url)
            if statusCode == 200 {
                backendStatus = .reachable
            } else {
                backendStatus = .unreachable("Unexpected response (HTTP \(statusCode))")
            }
        } catch {
            backendStatus = .unreachable(error.localizedDescription)
        }
    }

    // MARK: - Public actions

    /// Loads the current Google connection status from the backend.
    ///
    /// Called on `onAppear` of SettingsView and after connect/disconnect.
    public func loadStatus() async {
        isLoading = true
        errorMessage = nil
        do {
            googleStatus = try await googleAuthService.getStatus()
        } catch {
            googleStatus = .disconnected
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    /// Starts the Google OAuth2 connect flow via ASWebAuthenticationSession.
    ///
    /// Requires biometric confirmation first when a `biometricService` is injected
    /// (spec §29.3 — connecting Google is a medium-risk action).
    /// On success, re-fetches status to reflect the new connected state.
    /// On user cancellation (`.cancelled` error or biometric denial), silently ignores.
    public func connectGoogle() async {
        isLoading = true
        errorMessage = nil
        do {
            // Biometric gate: verify identity before opening the OAuth browser sheet
            if let bio = biometricService, await bio.isAvailable() {
                try await bio.authenticate(reason: "Confirm your identity to connect your Google account")
            }
            try await googleAuthService.connect()
            // Re-fetch status to confirm the backend persisted the tokens
            googleStatus = try await googleAuthService.getStatus()
        } catch let webError as WebAuthError {
            // User cancelled OAuth sheet — not an error to surface
            if case .cancelled = webError {
                // Silently ignore
            } else {
                errorMessage = "Connection failed. Please try again."
            }
        } catch let bioError as BiometricError {
            // User cancelled biometric prompt — not an error to surface
            if case .userCancelled = bioError {
                // Silently ignore
            } else {
                errorMessage = "Biometric authentication failed."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    /// Disconnects the Google account.
    ///
    /// Called after the user confirms via the disconnect confirmation sheet.
    public func disconnectGoogle() async {
        isLoading = true
        errorMessage = nil
        showDisconnectConfirmation = false
        do {
            try await googleAuthService.disconnect()
            googleStatus = .disconnected
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
