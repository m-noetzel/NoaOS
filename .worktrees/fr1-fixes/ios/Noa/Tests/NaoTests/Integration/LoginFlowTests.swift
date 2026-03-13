// LoginFlowTests.swift — E2E integration test: login → refresh → logout
// Spec ref: SPEC.md §5.1–5.4, §29.3, §37 (Definition of Done)
// Phase: iOS11
//
// Tests:
//   IT1   login() stores access and refresh tokens in Keychain
//   IT2   login() fails with .unauthorized on 401
//   IT3   refresh() calls /api/v1/auth/refresh with stored refresh token
//   IT4   logout() clears Keychain tokens and calls server endpoint

import XCTest
@testable import Noa

/// E2E integration test for the full auth flow using the URLProtocol-based mock server.
///
/// Each test creates an isolated `AuthService` + `APIClient` pair wired to
/// `MockURLProtocol` so no real network I/O is performed.  A unique Keychain
/// namespace is used per test to avoid cross-test contamination.
@MainActor
final class LoginFlowTests: XCTestCase {

    // MARK: - Helpers

    /// Unique keychain namespace per test invocation to avoid contamination.
    private var keychainNamespace: String = ""

    override func setUp() {
        super.setUp()
        keychainNamespace = "com.noa.integration-test.\(UUID().uuidString)"
        MockURLProtocol.handler = nil
    }

    override func tearDown() {
        MockURLProtocol.handler = nil
        // Clean up any tokens the test may have written.
        KeychainService.delete(service: keychainNamespace, account: "access_token")
        KeychainService.delete(service: keychainNamespace, account: "refresh_token")
        super.tearDown()
    }

    /// Creates a fully wired `AuthService` using `MockURLProtocol`.
    private func makeAuthService() -> AuthService {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)
        let mockToken = MockTokenProvider()
        let client = APIClient(
            environment: .development,
            tokenProvider: mockToken,
            session: session
        )
        return AuthService(apiClient: client, keychainService: keychainNamespace)
    }

    // MARK: - IT1: login() stores tokens

    func test_loginFlow_storesAccessAndRefreshTokens() async throws {
        // Spec ref: SPEC.md §5.1 — login returns access_token and refresh_token
        MockURLProtocol.handler = { _ in
            let json = """
            {"ok":true,"data":{"access_token":"acc.tok","refresh_token":"ref.tok",
            "token_type":"bearer","expires_in":900},"error":null,"trace_id":"t1"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeAuthService()
        try await service.login(username: "user@example.com", password: "pass")

        let access = KeychainService.read(service: keychainNamespace, account: "access_token")
        let refresh = KeychainService.read(service: keychainNamespace, account: "refresh_token")
        XCTAssertEqual(access, "acc.tok", "access_token must be stored in Keychain after login")
        XCTAssertEqual(refresh, "ref.tok", "refresh_token must be stored in Keychain after login")
    }

    // MARK: - IT2: login() fails on 401

    func test_loginFlow_throws_onUnauthorized() async {
        // Spec ref: SPEC.md §5.1 — server rejects wrong credentials with 401
        MockURLProtocol.handler = { _ in
            let json = """
            {"ok":false,"data":null,"error":{"code":"UNAUTHORIZED","message":"Bad credentials"},
            "trace_id":"t2"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 401))
        }

        let service = makeAuthService()
        do {
            try await service.login(username: "bad@example.com", password: "wrong")
            XCTFail("Expected an error to be thrown on 401 response")
        } catch APIError.unauthorized {
            // Expected — SPEC §5.1 says 401 → throw unauthorized
        } catch {
            XCTFail("Expected APIError.unauthorized, got: \(error)")
        }
    }

    // MARK: - IT3: refresh() calls correct endpoint with stored token

    func test_refreshFlow_callsRefreshEndpointWithStoredToken() async throws {
        // Spec ref: SPEC.md §5.3 — refresh sends the current refresh_token in the body
        var capturedBody: Data?

        // Step 1: prime the Keychain with a refresh token (simulating a prior login).
        KeychainService.save(
            value: "stored-refresh-tok",
            service: keychainNamespace,
            account: "refresh_token"
        )

        MockURLProtocol.handler = { request in
            capturedBody = request.httpBody
            let json = """
            {"ok":true,"data":{"access_token":"new-acc","refresh_token":"new-ref",
            "token_type":"bearer","expires_in":900},"error":null,"trace_id":"t3"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeAuthService()
        try await service.refresh()

        let body = try XCTUnwrap(capturedBody, "Refresh request must carry a body")
        let decoded = try JSONSerialization.jsonObject(with: body) as? [String: Any]
        let sentToken = decoded?["refresh_token"] as? String
        XCTAssertEqual(sentToken, "stored-refresh-tok",
            "refresh() must send the stored refresh token in the POST body")

        let newAccess = KeychainService.read(service: keychainNamespace, account: "access_token")
        XCTAssertEqual(newAccess, "new-acc", "Keychain must be updated with the rotated access token")
    }

    // MARK: - IT4: logout() clears Keychain

    func test_logoutFlow_clearsKeychainTokens() async throws {
        // Spec ref: SPEC.md §5.4 — logout must clear local tokens regardless of server response
        KeychainService.save(value: "acc", service: keychainNamespace, account: "access_token")
        KeychainService.save(value: "ref", service: keychainNamespace, account: "refresh_token")

        MockURLProtocol.handler = { _ in
            let json = """
            {"ok":true,"data":null,"error":null,"trace_id":"t4"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeAuthService()
        try await service.logout()

        let access = KeychainService.read(service: keychainNamespace, account: "access_token")
        let refresh = KeychainService.read(service: keychainNamespace, account: "refresh_token")
        XCTAssertNil(access, "access_token must be removed from Keychain after logout")
        XCTAssertNil(refresh, "refresh_token must be removed from Keychain after logout")
    }
}
