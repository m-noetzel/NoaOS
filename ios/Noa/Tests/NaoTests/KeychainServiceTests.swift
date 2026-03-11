// KeychainServiceTests.swift — Behavioural tests for iOS4: Keychain Storage & Auth Flow
// Spec refs: SPEC.md §5.1–5.4, §29.3 (Keychain for session tokens),
//            §29.4 (Connection Security)
// Phase plan: PHASE_DETAILS.md Phase iOS4
//
// Tests are INTENTIONALLY FAILING before implementation (red phase).
// They define the contract; implementation must satisfy them.

import XCTest
@testable import Noa

// MARK: - KeychainService Tests
// ---------------------------------------------------------------------------
// SPEC.md §29.3: "Secure Storage: Keychain for session tokens"
// Phase iOS4 deliverable 1: KeychainService wrapping Security framework
//   (SecItemAdd/Update/Delete/CopyMatching)
// Phase iOS4 deliverable 2: Token storage with
//   kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
// ---------------------------------------------------------------------------

final class KeychainServiceTests: XCTestCase {

    // Keychain service key used for test isolation
    private let testService = "com.noa.tests.keychain"
    private let testAccount = "ios4-test-account"

    override func setUp() {
        super.setUp()
        // Ensure clean state before each test
        KeychainService.delete(service: testService, account: testAccount)
    }

    override func tearDown() {
        KeychainService.delete(service: testService, account: testAccount)
        super.tearDown()
    }

    // MARK: - T1: Store and retrieve a string value

    func test_save_thenRead_returnsStoredValue() throws {
        // SPEC.md §29.3: Session tokens must be stored in and retrieved from Keychain.
        let value = "access-token-abc123"

        let saved = KeychainService.save(value: value, service: testService, account: testAccount)
        XCTAssertTrue(saved, "KeychainService.save must return true on success")

        let retrieved = KeychainService.read(service: testService, account: testAccount)
        XCTAssertEqual(retrieved, value, "read() must return the exact string that was saved")
    }

    // MARK: - T2: Overwrite an existing Keychain entry

    func test_save_overwritesExistingValue() {
        // PHASE iOS4: KeychainService must support update (SecItemUpdate) so that
        // token refresh writes the new access token without errSecDuplicateItem.
        let firstToken = "first-access-token"
        let secondToken = "updated-access-token"

        KeychainService.save(value: firstToken, service: testService, account: testAccount)
        let overwritten = KeychainService.save(value: secondToken, service: testService, account: testAccount)

        XCTAssertTrue(overwritten, "Overwrite must succeed (no errSecDuplicateItem)")

        let retrieved = KeychainService.read(service: testService, account: testAccount)
        XCTAssertEqual(retrieved, secondToken, "After overwrite, read must return the new value")
    }

    // MARK: - T3: Delete removes the entry

    func test_delete_removesStoredValue() {
        // SPEC.md §5.4: Logout invalidates all tokens — KeychainService.delete must clear tokens.
        KeychainService.save(value: "token-to-delete", service: testService, account: testAccount)

        let deleted = KeychainService.delete(service: testService, account: testAccount)
        XCTAssertTrue(deleted, "delete must return true when an item is successfully removed")

        let retrieved = KeychainService.read(service: testService, account: testAccount)
        XCTAssertNil(retrieved, "After deletion, read must return nil")
    }

    // MARK: - T4: Read on non-existent key returns nil

    func test_read_returnsNil_whenNotFound() {
        // PHASE iOS4: AuthViewModel.isAuthenticated checks if token is present;
        // nil from read() signals unauthenticated state.
        let result = KeychainService.read(service: "com.noa.tests.nonexistent", account: "missing")
        XCTAssertNil(result, "read on a non-existent Keychain entry must return nil, not crash")
    }

    // MARK: - T5: Delete on non-existent entry succeeds silently

    func test_delete_onMissingEntry_succeedsOrReturnsTrue() {
        // PHASE iOS4: Calling logout when already logged out must not crash.
        // errSecItemNotFound is a harmless condition and must not propagate as failure.
        let result = KeychainService.delete(service: "com.noa.tests.absent", account: "ghost")
        // Either true (interpreted as "no item = already gone") or false is acceptable
        // per implementation; what must NOT happen is an uncaught exception.
        // We assert this does not crash by reaching this line.
        _ = result
    }

    // MARK: - T6: Stored token uses device-only accessibility attribute

    func test_storedToken_usesAfterFirstUnlockThisDeviceOnly() {
        // SPEC.md §29.3 / Phase iOS4 deliverable 2:
        // "Token storage with kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly"
        // This attribute ensures tokens are inaccessible while device is locked
        // AND are NOT backed up to iCloud (device-only).
        // We verify that KeychainService exposes the accessibility level used.
        XCTAssertEqual(
            KeychainService.accessibility,
            kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String,
            "KeychainService must use kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly — not kSecAttrAccessibleAlways or iCloud-backed variants"
        )
    }

    // MARK: - T7: Stored value survives delete of a different account

    func test_storedValue_notDeletedByDifferentAccount() {
        // PHASE iOS4: Access token and refresh token use distinct Keychain accounts.
        // Deleting one must not affect the other.
        let accessAccount = "access_token"
        let refreshAccount = "refresh_token"

        KeychainService.save(value: "access-abc", service: testService, account: accessAccount)
        KeychainService.save(value: "refresh-xyz", service: testService, account: refreshAccount)

        KeychainService.delete(service: testService, account: accessAccount)

        let refreshStillPresent = KeychainService.read(service: testService, account: refreshAccount)
        XCTAssertEqual(
            refreshStillPresent, "refresh-xyz",
            "Deleting access_token account must not remove the refresh_token account"
        )

        // Clean up
        KeychainService.delete(service: testService, account: refreshAccount)
        KeychainService.delete(service: testService, account: accessAccount)
    }
}

// MARK: - AuthService Tests
// ---------------------------------------------------------------------------
// SPEC.md §5.3: Authentication flow (login → tokens, refresh → new tokens)
// SPEC.md §5.4: Revocation (logout clears all tokens)
// Phase iOS4 deliverables 3 & 4: AuthService + AuthViewModel
// ---------------------------------------------------------------------------

/// Fake APIClient that captures login/refresh/logout calls and returns controlled responses.
/// Used to test AuthService behaviour without making real network requests.
actor FakeAuthAPIClient: APIClientProtocol {

    enum FakeMode {
        case loginSuccess(accessToken: String, refreshToken: String, expiresIn: Int)
        case loginFailure
        case refreshSuccess(accessToken: String, refreshToken: String, expiresIn: Int)
        case refreshFailure
    }

    var mode: FakeMode = .loginSuccess(accessToken: "at", refreshToken: "rt", expiresIn: 900)
    var loginCallCount = 0
    var refreshCallCount = 0
    var logoutCallCount = 0

    func setMode(_ m: FakeMode) {
        mode = m
    }

    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        if endpoint.hasSuffix("/auth/login") {
            loginCallCount += 1
            switch mode {
            case .loginSuccess(let at, let rt, let exp):
                let tokens = AuthTokens(
                    accessToken: at,
                    refreshToken: rt,
                    tokenType: "bearer",
                    expiresIn: exp
                )
                guard let result = tokens as? T else {
                    throw APIError.decodingError(underlying: NSError(domain: "FakeAuthAPIClient", code: 0))
                }
                return result
            case .loginFailure:
                throw APIError.unauthorized
            default:
                throw APIError.unauthorized
            }
        }
        if endpoint.hasSuffix("/auth/refresh") {
            refreshCallCount += 1
            switch mode {
            case .refreshSuccess(let at, let rt, let exp):
                let tokens = AuthTokens(
                    accessToken: at,
                    refreshToken: rt,
                    tokenType: "bearer",
                    expiresIn: exp
                )
                guard let result = tokens as? T else {
                    throw APIError.decodingError(underlying: NSError(domain: "FakeAuthAPIClient", code: 0))
                }
                return result
            case .refreshFailure:
                throw APIError.unauthorized
            default:
                throw APIError.unauthorized
            }
        }
        if endpoint.hasSuffix("/auth/logout") {
            logoutCallCount += 1
            // Logout returns EmptyResponse; cast it out
            if let result = EmptyResponse() as? T {
                return result
            }
            throw APIError.decodingError(underlying: NSError(domain: "FakeAuthAPIClient", code: 1))
        }
        throw APIError.notFound
    }
}

/// Minimal empty response type for logout endpoint.
struct EmptyResponse: Decodable, Sendable {}

final class AuthServiceTests: XCTestCase {

    // Use a dedicated Keychain service namespace so tests don't pollute production data
    private let keychainService = "com.noa.tests.auth"

    override func tearDown() {
        // Clear test Keychain entries
        KeychainService.delete(service: keychainService, account: "access_token")
        KeychainService.delete(service: keychainService, account: "refresh_token")
        super.tearDown()
    }

    // MARK: - T8: Successful login stores access and refresh tokens in Keychain

    func test_login_success_storesTokensInKeychain() async throws {
        // SPEC.md §5.3: POST /api/v1/auth/login → 200 { access_token (15min), refresh_token (7d) }
        // Phase iOS4 deliverable 3: "AuthService handling login, refresh, logout with Keychain persistence"
        let fake = FakeAuthAPIClient()
        await fake.setMode(.loginSuccess(accessToken: "at-stored", refreshToken: "rt-stored", expiresIn: 900))

        let svc = AuthService(apiClient: fake, keychainService: keychainService)
        try await svc.login(username: "alice", password: "secret")

        let storedAccess = KeychainService.read(service: keychainService, account: "access_token")
        let storedRefresh = KeychainService.read(service: keychainService, account: "refresh_token")

        XCTAssertEqual(storedAccess, "at-stored", "login must persist the access_token to Keychain")
        XCTAssertEqual(storedRefresh, "rt-stored", "login must persist the refresh_token to Keychain")
    }

    // MARK: - T9: Failed login leaves Keychain empty

    func test_login_failure_doesNotStoreTokens() async {
        // SPEC.md §5.3: On authentication failure, no tokens should be stored.
        // Phase iOS4 deliverable 3: failure clears (or never writes) Keychain state.
        let fake = FakeAuthAPIClient()
        await fake.setMode(.loginFailure)

        let svc = AuthService(apiClient: fake, keychainService: keychainService)

        do {
            try await svc.login(username: "alice", password: "wrong")
            XCTFail("login with wrong credentials must throw")
        } catch {
            // Expected
        }

        let storedAccess = KeychainService.read(service: keychainService, account: "access_token")
        let storedRefresh = KeychainService.read(service: keychainService, account: "refresh_token")

        XCTAssertNil(storedAccess, "Failed login must not store access_token in Keychain")
        XCTAssertNil(storedRefresh, "Failed login must not store refresh_token in Keychain")
    }

    // MARK: - T10: Token refresh replaces both tokens in Keychain

    func test_refresh_rotatesBothTokens() async throws {
        // SPEC.md §5.2: "Token refresh uses rotating refresh tokens (old token invalidated on use)"
        // Phase iOS4 deliverable 3: "refresh rotates"
        // First: seed old tokens
        KeychainService.save(value: "old-at", service: keychainService, account: "access_token")
        KeychainService.save(value: "old-rt", service: keychainService, account: "refresh_token")

        let fake = FakeAuthAPIClient()
        await fake.setMode(.refreshSuccess(accessToken: "new-at", refreshToken: "new-rt", expiresIn: 900))

        let svc = AuthService(apiClient: fake, keychainService: keychainService)
        try await svc.refresh()

        let newAccess = KeychainService.read(service: keychainService, account: "access_token")
        let newRefresh = KeychainService.read(service: keychainService, account: "refresh_token")

        XCTAssertEqual(newAccess, "new-at", "After refresh, access_token must be the new token")
        XCTAssertEqual(newRefresh, "new-rt", "After refresh, refresh_token must be rotated to new token")
    }

    // MARK: - T11: Logout clears both tokens from Keychain

    func test_logout_clearsAllKeychainTokens() async throws {
        // SPEC.md §5.4: "Logout invalidates all tokens for that session"
        // Phase iOS4 deliverable 3: "logout clears"
        KeychainService.save(value: "at-to-clear", service: keychainService, account: "access_token")
        KeychainService.save(value: "rt-to-clear", service: keychainService, account: "refresh_token")

        let fake = FakeAuthAPIClient()
        let svc = AuthService(apiClient: fake, keychainService: keychainService)
        try await svc.logout()

        let access = KeychainService.read(service: keychainService, account: "access_token")
        let refresh = KeychainService.read(service: keychainService, account: "refresh_token")

        XCTAssertNil(access, "logout must delete access_token from Keychain")
        XCTAssertNil(refresh, "logout must delete refresh_token from Keychain")
    }

    // MARK: - T12: accessToken() returns stored Keychain value

    func test_accessToken_returnsKeychainValue() async throws {
        // SPEC.md §5.3: The access token must be retrievable for Bearer header injection.
        // Phase iOS4: AuthService conforms to TokenProviding so APIClient can use it.
        KeychainService.save(value: "live-access-token", service: keychainService, account: "access_token")

        let fake = FakeAuthAPIClient()
        let svc = AuthService(apiClient: fake, keychainService: keychainService)

        let token = await svc.accessToken()
        XCTAssertEqual(token, "live-access-token", "accessToken() must read from Keychain")
    }

    // MARK: - T13: accessToken() returns nil when not logged in

    func test_accessToken_returnsNil_whenNoToken() async {
        // SPEC.md §5.3: Unauthenticated state must be detectable (nil access token).
        let fake = FakeAuthAPIClient()
        let svc = AuthService(apiClient: fake, keychainService: keychainService)

        let token = await svc.accessToken()
        XCTAssertNil(token, "accessToken() returns nil when no token is in Keychain")
    }

    // MARK: - T14: AuthService conforms to TokenProviding

    func test_authService_conformsToTokenProviding() {
        // Phase iOS4 / SPEC.md §29.3: AuthService provides tokens to APIClient.
        // TokenProviding protocol was designed in iOS3 specifically for iOS4.
        let fake = FakeAuthAPIClient()
        let svc = AuthService(apiClient: fake, keychainService: keychainService)

        // If AuthService conforms to TokenProviding, this cast will succeed.
        let asProvider: (any TokenProviding)? = svc as? (any TokenProviding)
        XCTAssertNotNil(asProvider, "AuthService must conform to TokenProviding so APIClient can use it for Bearer token injection")
    }
}

// MARK: - AuthViewModel Tests
// ---------------------------------------------------------------------------
// Phase iOS4 deliverable 4: AuthViewModel (@Observable) managing auth state
// Phase iOS4 deliverable 7: Automatic token refresh on app foreground
// ---------------------------------------------------------------------------

final class AuthViewModelTests: XCTestCase {

    private let keychainService = "com.noa.tests.authvm"

    override func tearDown() {
        KeychainService.delete(service: keychainService, account: "access_token")
        KeychainService.delete(service: keychainService, account: "refresh_token")
        super.tearDown()
    }

    // MARK: - T15: Initial state is unauthenticated when no token in Keychain

    @MainActor
    func test_initialState_isUnauthenticated_whenNoKeychain() {
        // Phase iOS4 deliverable 4: "AuthViewModel managing auth state"
        // AuthGuard uses isAuthenticated to decide which view to show.
        let fake = FakeAuthAPIClient()
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        XCTAssertFalse(vm.isAuthenticated, "With no Keychain token, isAuthenticated must be false on init")
    }

    // MARK: - T16: After login, isAuthenticated becomes true

    @MainActor
    func test_afterLogin_isAuthenticated_becomesTrue() async throws {
        // Phase iOS4 deliverable 4: Auth state transitions on successful login.
        let fake = FakeAuthAPIClient()
        await fake.setMode(.loginSuccess(accessToken: "at", refreshToken: "rt", expiresIn: 900))
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        try await vm.login(username: "user@example.com", password: "hunter2")

        XCTAssertTrue(vm.isAuthenticated, "After successful login, isAuthenticated must be true")
    }

    // MARK: - T17: Failed login populates errorMessage

    @MainActor
    func test_failedLogin_populatesErrorMessage() async {
        // Phase iOS4 deliverable 4: "AuthViewModel … error display"
        // LoginView binds to vm.errorMessage; it must be non-nil after failure.
        let fake = FakeAuthAPIClient()
        await fake.setMode(.loginFailure)
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        await vm.loginAttempt(username: "alice", password: "wrong")

        XCTAssertNotNil(vm.errorMessage, "After a failed login, errorMessage must be set for display in LoginView")
        XCTAssertFalse(vm.isAuthenticated, "After a failed login, isAuthenticated must remain false")
    }

    // MARK: - T18: After logout, isAuthenticated becomes false

    @MainActor
    func test_afterLogout_isAuthenticated_becomesFalse() async throws {
        // SPEC.md §5.4: Logout invalidates all tokens.
        // AuthViewModel must reflect this by setting isAuthenticated = false.
        let fake = FakeAuthAPIClient()
        await fake.setMode(.loginSuccess(accessToken: "at", refreshToken: "rt", expiresIn: 900))
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        try await vm.login(username: "user", password: "pass")
        XCTAssertTrue(vm.isAuthenticated)

        try await vm.logout()
        XCTAssertFalse(vm.isAuthenticated, "After logout, isAuthenticated must become false")
    }

    // MARK: - T19: Auto-refresh triggers when token is near expiry

    @MainActor
    func test_autoRefresh_triggersWhenTokenNearExpiry() async throws {
        // Phase iOS4 deliverable 7: "Automatic token refresh on app foreground (if access token near expiry)"
        // If expiresIn is <= 60 seconds, foreground check must trigger refresh.
        let fake = FakeAuthAPIClient()
        // Login with a token expiring in 30 seconds (near-expiry)
        await fake.setMode(.loginSuccess(accessToken: "expiring-at", refreshToken: "rt", expiresIn: 30))
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        try await vm.login(username: "user", password: "pass")

        // Now set the refresh to succeed with new tokens
        await fake.setMode(.refreshSuccess(accessToken: "fresh-at", refreshToken: "fresh-rt", expiresIn: 900))

        // Simulate app foreground event
        await vm.handleAppForeground()

        let refreshCount = await fake.refreshCallCount
        XCTAssertGreaterThanOrEqual(refreshCount, 1, "handleAppForeground must trigger token refresh when token is near expiry (≤60s remaining)")
    }

    // MARK: - T20: App foreground with valid token does NOT refresh

    @MainActor
    func test_appForeground_withFreshToken_doesNotRefresh() async throws {
        // Phase iOS4 deliverable 7: Refresh is conditional — only triggers if near expiry.
        // This prevents unnecessary API calls every time the user switches apps.
        let fake = FakeAuthAPIClient()
        // Token valid for 15 minutes (900 seconds) — well within threshold
        await fake.setMode(.loginSuccess(accessToken: "fresh-at", refreshToken: "rt", expiresIn: 900))
        let authSvc = AuthService(apiClient: fake, keychainService: keychainService)
        let vm = AuthViewModel(authService: authSvc)

        try await vm.login(username: "user", password: "pass")

        // Foreground with a fresh token should NOT refresh
        await fake.setMode(.refreshSuccess(accessToken: "new-at", refreshToken: "new-rt", expiresIn: 900))
        await vm.handleAppForeground()

        let refreshCount = await fake.refreshCallCount
        XCTAssertEqual(refreshCount, 0, "handleAppForeground must NOT trigger refresh when token has >60s remaining")
    }
}
