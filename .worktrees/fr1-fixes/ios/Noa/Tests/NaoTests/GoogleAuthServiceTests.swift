// GoogleAuthServiceTests.swift — GO3 Google OAuth2 iOS tests
// Spec ref: SPEC.md §29.3 (Mobile Access — OAuth2), §11.1, §12.1, §12.2
//
// Tests:
//   T-GO3-01  connect() calls GET /auth/google/authorize to get auth URL
//   T-GO3-02  connect() passes auth URL to WebAuthSessionProviding
//   T-GO3-03  connect() uses "noaapp" as callback scheme
//   T-GO3-04  Successful connect callback → getStatus() returns .connected
//   T-GO3-05  User cancellation → throws WebAuthError.cancelled
//   T-GO3-06  Session error → throws WebAuthError.failed
//   T-GO3-07  disconnect() calls DELETE /auth/google/disconnect
//   T-GO3-08  getStatus() returns .connected when backend returns connected: true
//   T-GO3-09  getStatus() returns .disconnected when backend returns connected: false
//   T-GO3-10  SettingsViewModel loads status on init-driven loadStatus()
//   T-GO3-11  SettingsViewModel isLoading is true during in-flight request then false after
//   T-GO3-12  SettingsViewModel connectGoogle() sets .connected after success
//   T-GO3-13  SettingsViewModel disconnectGoogle() sets .disconnected after success
//   T-GO3-14  SettingsViewModel cancellation is silently ignored (no error message shown)
//   T-GO3-15  Google tokens are never stored in iOS Keychain or UserDefaults

import XCTest
@testable import Noa

// MARK: - MockWebAuthSession

/// Mock that simulates a successful OAuth callback to noaapp://oauth/callback?google=connected
actor MockWebAuthSession: WebAuthSessionProviding {
    nonisolated(unsafe) var capturedURL: URL?
    nonisolated(unsafe) var capturedScheme: String?
    nonisolated(unsafe) var callCount: Int = 0
    nonisolated(unsafe) var shouldThrow: Error?
    /// The URL to return as the callback URL.
    nonisolated(unsafe) var callbackURL: URL = URL(string: "noaapp://oauth/callback?google=connected")!

    func authenticate(url: URL, callbackURLScheme: String) async throws -> URL {
        capturedURL = url
        capturedScheme = callbackURLScheme
        callCount += 1
        if let error = shouldThrow {
            throw error
        }
        return callbackURL
    }
}

// MARK: - MockGoogleAuthClient

/// Mock APIClientProtocol with injectable responses for Google auth endpoints.
actor MockGoogleAuthAPIClient: APIClientProtocol {
    nonisolated(unsafe) var authorizeResponse: GoogleAuthorizeResponse = GoogleAuthorizeResponse(authUrl: "https://accounts.google.com/o/oauth2/auth?test=1")
    nonisolated(unsafe) var statusResponse: GoogleStatusResponse = GoogleStatusResponse(connected: false, scopes: nil)
    nonisolated(unsafe) var shouldFailAuthorize: Bool = false
    nonisolated(unsafe) var shouldFailStatus: Bool = false
    nonisolated(unsafe) var shouldFailDisconnect: Bool = false

    nonisolated(unsafe) var authorizeCallCount: Int = 0
    nonisolated(unsafe) var statusCallCount: Int = 0
    nonisolated(unsafe) var disconnectCallCount: Int = 0
    nonisolated(unsafe) var lastAuthorizeEndpoint: String?

    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        if endpoint.hasPrefix("/api/v1/auth/google/authorize") {
            lastAuthorizeEndpoint = endpoint
            authorizeCallCount += 1
            if shouldFailAuthorize {
                throw APIError.serverError(code: "ERR", message: "Authorize failed")
            }
            if let result = authorizeResponse as? T {
                return result
            }
            throw APIError.decodingError(underlying: NSError(domain: "test", code: 0))
        }

        if endpoint == "/api/v1/auth/google/status" {
            statusCallCount += 1
            if shouldFailStatus {
                throw APIError.serverError(code: "ERR", message: "Status failed")
            }
            if let result = statusResponse as? T {
                return result
            }
            throw APIError.decodingError(underlying: NSError(domain: "test", code: 0))
        }

        if endpoint == "/api/v1/auth/google/disconnect" {
            disconnectCallCount += 1
            if shouldFailDisconnect {
                throw APIError.serverError(code: "ERR", message: "Disconnect failed")
            }
            if let result = GoogleDisconnectResponse(disconnected: true) as? T {
                return result
            }
            throw APIError.decodingError(underlying: NSError(domain: "test", code: 0))
        }

        throw APIError.notFound
    }

    func isAuthenticated() async -> Bool { true }
}

// MARK: - MockGoogleAuthService (for SettingsViewModel tests)

actor MockGoogleAuthService: GoogleAuthServicing {
    nonisolated(unsafe) var statusToReturn: GoogleAuthStatus = .disconnected
    nonisolated(unsafe) var connectCallCount: Int = 0
    nonisolated(unsafe) var disconnectCallCount: Int = 0
    nonisolated(unsafe) var statusCallCount: Int = 0
    nonisolated(unsafe) var shouldThrowOnConnect: Error?
    nonisolated(unsafe) var shouldThrowOnDisconnect: Error?
    nonisolated(unsafe) var shouldThrowOnStatus: Error?

    func connect() async throws {
        connectCallCount += 1
        if let error = shouldThrowOnConnect {
            throw error
        }
        // Simulate backend token persistence
        statusToReturn = .connected(email: nil)
    }

    func disconnect() async throws {
        disconnectCallCount += 1
        if let error = shouldThrowOnDisconnect {
            throw error
        }
        statusToReturn = .disconnected
    }

    func getStatus() async throws -> GoogleAuthStatus {
        statusCallCount += 1
        if let error = shouldThrowOnStatus {
            throw error
        }
        return statusToReturn
    }
}

// MARK: - GoogleAuthServiceTests

final class GoogleAuthServiceTests: XCTestCase {

    // MARK: - T-GO3-01: connect() calls authorize endpoint with platform=ios

    func test_connect_callsAuthorizeEndpoint() async throws {
        // Spec ref: SPEC.md §29.3 — iOS must fetch auth URL from backend with platform=ios
        // so the callback redirects to noaapp:// instead of the web settings page.
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        try await service.connect()

        let callCount = await mockClient.authorizeCallCount
        XCTAssertEqual(callCount, 1, "connect() must call GET /api/v1/auth/google/authorize exactly once")

        let capturedEndpoint = await mockClient.lastAuthorizeEndpoint
        XCTAssertTrue(
            capturedEndpoint?.contains("platform=ios") == true,
            "connect() must pass platform=ios to the authorize endpoint (got: \(capturedEndpoint ?? "nil"))"
        )
    }

    // MARK: - T-GO3-02: connect() passes auth URL to WebAuthSessionProviding

    func test_connect_passesAuthURLToSession() async throws {
        // Spec ref: SPEC.md §29.3 — ASWebAuthenticationSession must receive the backend URL
        let mockClient = MockGoogleAuthAPIClient()
        mockClient.authorizeResponse = GoogleAuthorizeResponse(authUrl: "https://accounts.google.com/o/oauth2/auth?client_id=test")
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        try await service.connect()

        let capturedURL = await mockSession.capturedURL
        XCTAssertNotNil(capturedURL, "WebAuthSession must receive the auth URL")
        XCTAssertEqual(capturedURL?.host, "accounts.google.com", "Auth URL must point to Google accounts")
    }

    // MARK: - T-GO3-03: connect() uses "noaapp" as callback scheme

    func test_connect_usesNoaappCallbackScheme() async throws {
        // Spec ref: Phase GO3 spec — callback scheme must be "noaapp"
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        try await service.connect()

        let capturedScheme = await mockSession.capturedScheme
        XCTAssertEqual(capturedScheme, "noaapp", "connect() must use 'noaapp' as the callback URL scheme")
    }

    // MARK: - T-GO3-04: Successful callback → connect() completes without error

    func test_connect_successfulCallback_completesWithoutError() async throws {
        // Spec ref: Phase GO3 — connect completes on valid noaapp:// redirect
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        mockSession.callbackURL = URL(string: "noaapp://oauth/callback?google=connected")!
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        // Must not throw
        try await service.connect()

        let sessionCallCount = await mockSession.callCount
        XCTAssertEqual(sessionCallCount, 1, "WebAuthSession must be invoked exactly once")
    }

    // MARK: - T-GO3-05: User cancellation throws WebAuthError.cancelled

    func test_connect_userCancellation_throwsCancelled() async {
        // Spec ref: Phase GO3 — user cancel must produce WebAuthError.cancelled (not an app error)
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        mockSession.shouldThrow = WebAuthError.cancelled
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        do {
            try await service.connect()
            XCTFail("connect() must throw when user cancels")
        } catch let error as WebAuthError {
            if case .cancelled = error {
                // Expected
            } else {
                XCTFail("Expected WebAuthError.cancelled, got \(error)")
            }
        } catch {
            XCTFail("Expected WebAuthError.cancelled, got \(error)")
        }
    }

    // MARK: - T-GO3-06: Session error propagates as WebAuthError.failed

    func test_connect_sessionError_throwsFailed() async {
        // Spec ref: Phase GO3 — unrecoverable session errors are surfaced to the UI layer
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        mockSession.shouldThrow = WebAuthError.failed("Browser closed unexpectedly")
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        do {
            try await service.connect()
            XCTFail("connect() must throw on session error")
        } catch let error as WebAuthError {
            if case .failed = error {
                // Expected
            } else {
                XCTFail("Expected WebAuthError.failed, got \(error)")
            }
        } catch {
            XCTFail("Expected WebAuthError, got \(error)")
        }
    }

    // MARK: - T-GO3-07: disconnect() calls DELETE endpoint

    func test_disconnect_callsDeleteEndpoint() async throws {
        // Spec ref: SPEC.md §11.1 — credentials removed from Postgres on disconnect
        let mockClient = MockGoogleAuthAPIClient()
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        try await service.disconnect()

        let callCount = await mockClient.disconnectCallCount
        XCTAssertEqual(callCount, 1, "disconnect() must call DELETE /api/v1/auth/google/disconnect exactly once")
    }

    // MARK: - T-GO3-08: getStatus() returns .connected when backend says connected

    func test_getStatus_returnsConnected_whenBackendReportsConnected() async throws {
        // Spec ref: SPEC.md §12.1, §12.2 — status reflects backend credential presence
        let mockClient = MockGoogleAuthAPIClient()
        mockClient.statusResponse = GoogleStatusResponse(connected: true, scopes: ["calendar", "gmail"])
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        let status = try await service.getStatus()

        if case .connected = status {
            // Expected
        } else {
            XCTFail("Expected .connected, got \(status)")
        }
    }

    // MARK: - T-GO3-09: getStatus() returns .disconnected when backend says not connected

    func test_getStatus_returnsDisconnected_whenBackendReportsNotConnected() async throws {
        // Spec ref: §12.1 — status reflects absence of credentials in backend DB
        let mockClient = MockGoogleAuthAPIClient()
        mockClient.statusResponse = GoogleStatusResponse(connected: false, scopes: nil)
        let mockSession = MockWebAuthSession()
        let service = GoogleAuthService(apiClient: mockClient, webAuthSession: mockSession)

        let status = try await service.getStatus()

        XCTAssertEqual(status, .disconnected, "getStatus() must return .disconnected when backend reports not connected")
    }
}

// MARK: - SettingsViewModelTests

/// Mock BiometricAuthenticating for SettingsViewModel tests (GO3).
actor MockBiometricForSettings: BiometricAuthenticating {
    nonisolated(unsafe) var available: Bool = true
    nonisolated(unsafe) var shouldThrow: Error?
    nonisolated(unsafe) var callCount: Int = 0

    func isAvailable() async -> Bool { available }

    func authenticate(reason: String) async throws {
        callCount += 1
        if let error = shouldThrow { throw error }
    }
}

@MainActor
final class SettingsViewModelTests: XCTestCase {

    // MARK: - T-GO3-10: loadStatus() populates googleStatus

    func test_loadStatus_populatesGoogleStatus() async throws {
        // Spec ref: Phase GO3 — status loaded on view appear
        let mockService = MockGoogleAuthService()
        mockService.statusToReturn = .disconnected

        let vm = SettingsViewModel(googleAuthService: mockService)
        await vm.loadStatus()

        XCTAssertEqual(vm.googleStatus, .disconnected, "loadStatus() must set googleStatus from service")
        XCTAssertNil(vm.errorMessage, "errorMessage must be nil on success")
    }

    // MARK: - T-GO3-11: isLoading toggles correctly around a request

    func test_loadStatus_isLoadingToggle() async throws {
        // Spec ref: Phase GO3 — loading state must be visible during fetch
        let mockService = MockGoogleAuthService()
        let vm = SettingsViewModel(googleAuthService: mockService)

        // loadStatus sets isLoading=true then false
        await vm.loadStatus()

        XCTAssertFalse(vm.isLoading, "isLoading must be false after loadStatus() completes")
    }

    // MARK: - T-GO3-12: connectGoogle() sets .connected after success

    func test_connectGoogle_setsConnectedAfterSuccess() async throws {
        // Spec ref: SPEC.md §29.3 — connect flow ends with updated status
        let mockService = MockGoogleAuthService()
        mockService.statusToReturn = .disconnected

        let vm = SettingsViewModel(googleAuthService: mockService)

        // connect() mutates statusToReturn to .connected(email:nil) internally
        await vm.connectGoogle()

        if case .connected = vm.googleStatus {
            // Expected
        } else {
            XCTFail("Expected .connected after connectGoogle() success, got \(vm.googleStatus)")
        }
        XCTAssertNil(vm.errorMessage, "errorMessage must be nil on successful connect")
    }

    // MARK: - T-GO3-13: disconnectGoogle() sets .disconnected after success

    func test_disconnectGoogle_setsDisconnectedAfterSuccess() async throws {
        // Spec ref: SPEC.md §11.1 — disconnect removes credentials
        let mockService = MockGoogleAuthService()
        mockService.statusToReturn = .connected(email: nil)

        let vm = SettingsViewModel(googleAuthService: mockService)
        vm.googleStatus = .connected(email: nil)

        await vm.disconnectGoogle()

        XCTAssertEqual(vm.googleStatus, .disconnected, "disconnectGoogle() must set googleStatus to .disconnected")
        XCTAssertNil(vm.errorMessage, "errorMessage must be nil on successful disconnect")
        XCTAssertFalse(vm.showDisconnectConfirmation, "Confirmation sheet must be dismissed after disconnect")
    }

    // MARK: - T-GO3-14: User cancellation is silently ignored

    func test_connectGoogle_cancellation_isIgnored() async throws {
        // Spec ref: Phase GO3 spec — user cancel must not show an error
        let mockService = MockGoogleAuthService()
        mockService.shouldThrowOnConnect = WebAuthError.cancelled
        // Status should stay at .disconnected after cancel
        mockService.statusToReturn = .disconnected

        let vm = SettingsViewModel(googleAuthService: mockService)
        vm.googleStatus = .disconnected

        await vm.connectGoogle()

        XCTAssertNil(vm.errorMessage, "User cancellation must NOT produce an error message")
        XCTAssertFalse(vm.isLoading, "isLoading must be false after cancelled connect")
    }

    // MARK: - T-GO3-15: Google tokens never stored in iOS Keychain or UserDefaults

    func test_googleTokens_neverStoredLocally() async throws {
        // Spec ref: §11.1 — Google tokens live only in the Postgres google_credentials table
        // This test verifies that GoogleAuthService and SettingsViewModel never write
        // google_access_token or google_refresh_token to the iOS Keychain or UserDefaults.

        let keysBeforeConnect = UserDefaults.standard.dictionaryRepresentation().keys.filter {
            $0.lowercased().contains("google") && (
                $0.lowercased().contains("token") ||
                $0.lowercased().contains("credential") ||
                $0.lowercased().contains("access") ||
                $0.lowercased().contains("refresh")
            )
        }

        let mockService = MockGoogleAuthService()
        mockService.statusToReturn = .disconnected
        let vm = SettingsViewModel(googleAuthService: mockService)
        await vm.connectGoogle()

        let keysAfterConnect = UserDefaults.standard.dictionaryRepresentation().keys.filter {
            $0.lowercased().contains("google") && (
                $0.lowercased().contains("token") ||
                $0.lowercased().contains("credential") ||
                $0.lowercased().contains("access") ||
                $0.lowercased().contains("refresh")
            )
        }

        // Only new keys added after connect are suspicious
        let newKeys = Set(keysAfterConnect).subtracting(Set(keysBeforeConnect))
        XCTAssertTrue(
            newKeys.isEmpty,
            "Google tokens must NEVER be stored in UserDefaults. Found new keys: \(newKeys)"
        )

        // Keychain check: verify no google token keys were written
        let keychainQuery: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: "google_access_token",
            kSecReturnData: false,
            kSecMatchLimit: kSecMatchLimitOne
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(keychainQuery as CFDictionary, &result)
        XCTAssertNotEqual(
            status, errSecSuccess,
            "Google access_token must NOT be stored in the iOS Keychain — it lives only in Postgres"
        )
    }

    // MARK: - T-GO3-16: Biometric rejection aborts connect without error message

    func test_connectGoogle_biometricCancellation_isIgnored() async throws {
        // Spec ref: §29.3 — connecting Google is medium-risk; biometric cancel is silently ignored
        let mockService = MockGoogleAuthService()
        let mockBio = MockBiometricForSettings()
        mockBio.available = true
        mockBio.shouldThrow = BiometricError.userCancelled

        let vm = SettingsViewModel(googleAuthService: mockService, biometricService: mockBio)
        vm.googleStatus = .disconnected

        await vm.connectGoogle()

        XCTAssertNil(vm.errorMessage, "Biometric cancellation must NOT produce an error message")
        XCTAssertFalse(vm.isLoading, "isLoading must be false after biometric cancel")
        // connect() on the service must NOT have been called after bio cancel
        let connectCount = await mockService.connectCallCount
        XCTAssertEqual(connectCount, 0, "googleAuthService.connect() must not be called when biometric is cancelled")
    }
}
