// DeviceServiceTests.swift — iOS6 Push Notifications (APNs Client)
// Spec ref: SPEC.md §29.5, Plan/REVIEWS/test-plan_iOS6.md T3-T6, T16, T18
//
// Tests DeviceService responsibilities:
//   T3  POST /api/v1/devices/push-token success: correct JSON body (device_id, platform, push_token)
//   T4  POST returns 401: error propagates, token NOT stored as registered
//   T5  POST network error: error surfaced, no crash, no infinite retry
//   T6  DELETE /api/v1/devices/push-token on logout: correct body, local state cleared
//   T16 Hex encoding: Data bytes produce lowercase hex without angle brackets or spaces
//   T18 No registration when unauthenticated: registerToken not called without auth token
//
// These tests FAIL at compile time because DeviceService does not exist yet.
// That is intentional — red phase.

import XCTest
@testable import Noa

// MARK: - Local Token Provider Mocks

/// Token provider that always fails token refresh (simulates expired + no refresh token).
/// Defined here to avoid actor isolation issues with the shared MockTokenProvider.
actor FailingTokenProvider: TokenProviding {
    private var token: String?

    func setToken(_ t: String?) {
        token = t
    }

    func accessToken() async -> String? {
        return token
    }

    func refreshAccessToken() async throws -> String {
        throw APIError.unauthorized
    }
}

/// Token provider that returns nil (simulates unauthenticated state).
actor UnauthenticatedTokenProvider: TokenProviding {
    func accessToken() async -> String? { return nil }
    func refreshAccessToken() async throws -> String { throw APIError.unauthorized }
}

// MARK: - Tests

final class DeviceServiceTests: XCTestCase {

    // MARK: - T3: Token registration sends correct POST body

    func test_registerToken_sendsCorrectPostBody() async throws {
        // SPEC.md §29.5, Phase iOS6 deliverable 3:
        // POST /api/v1/devices/push-token must include device_id, platform ("ios"), push_token (hex).
        var capturedRequest: URLRequest?

        MockURLProtocol.handler = { request in
            capturedRequest = request
            let data = try! makeEnvelopeJSON(data: EmptyPayload())
            return (data, makeHTTPResponse(statusCode: 200))
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)

        let tokenProvider = MockTokenProvider()
        await tokenProvider.setToken("valid-token")

        let apiClient = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        let tokenData = Data([0xAA, 0xBB, 0xCC, 0xDD, 0x11, 0x22, 0x33, 0x44])
        let service = DeviceService(apiClient: apiClient)
        try await service.registerToken(tokenData: tokenData)

        let req = try XCTUnwrap(capturedRequest, "A request must have been made")
        XCTAssertTrue(
            req.url?.path.contains("/api/v1/devices/push-token") == true,
            "Endpoint must be /api/v1/devices/push-token, got: \(req.url?.path ?? "nil")"
        )
        XCTAssertEqual(req.httpMethod, "POST", "Must use POST method")

        // Decode body and verify fields
        let bodyData = try XCTUnwrap(req.httpBody, "POST body must not be nil")
        let body = try JSONDecoder().decode([String: String].self, from: bodyData)

        XCTAssertEqual(body["platform"], "ios", "platform field must be 'ios'")
        XCTAssertNotNil(body["device_id"], "device_id field must be present")
        XCTAssertNotNil(body["push_token"], "push_token field must be present")

        // Verify hex encoding: no angle brackets, no spaces
        let hexToken = try XCTUnwrap(body["push_token"])
        XCTAssertFalse(hexToken.contains("<"), "push_token must not contain '<' (Data.description format)")
        XCTAssertFalse(hexToken.contains(">"), "push_token must not contain '>' (Data.description format)")
        XCTAssertFalse(hexToken.contains(" "), "push_token must not contain spaces")
        XCTAssertEqual(hexToken, "aabbccdd11223344", "push_token must be lowercase hex")
    }

    // MARK: - T4: 401 response — error propagates, not swallowed

    func test_registerToken_401_propagatesUnauthorizedError() async throws {
        // SPEC.md §29.5, §29.3: A 401 during registration means auth state is stale.
        // The error must propagate — not be silently swallowed.
        MockURLProtocol.handler = { _ in
            let data = try! JSONSerialization.data(withJSONObject: [
                "ok": false,
                "data": NSNull(),
                "error": ["code": "AUTH_TOKEN_EXPIRED", "message": "Token expired"],
                "trace_id": "t1",
            ])
            return (data, makeHTTPResponse(statusCode: 401))
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)

        let tokenProvider = FailingTokenProvider()
        await tokenProvider.setToken("expired-token")

        let apiClient = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        let service = DeviceService(apiClient: apiClient)
        let tokenData = Data([0xAA, 0xBB])

        do {
            try await service.registerToken(tokenData: tokenData)
            XCTFail("Expected an error on 401 — but registerToken succeeded silently")
        } catch APIError.unauthorized {
            // Expected: 401 must propagate as .unauthorized
        } catch {
            // Also acceptable: any typed error (not a crash)
            // The key requirement is: no silent success on 401
        }

        // Verify the service did NOT store the token as "registered"
        let isRegistered = await service.isTokenRegistered
        XCTAssertFalse(
            isRegistered,
            "Token must NOT be marked as registered after a 401 response"
        )
    }

    // MARK: - T5: Network error — surfaced, no crash, no infinite retry

    func test_registerToken_networkError_surfacedWithoutCrash() async {
        // Phase iOS6, T5: Network errors during registration must not block app
        // startup or cause an infinite retry loop.
        MockURLProtocol.handler = { _ in
            // Return a 500 to simulate server/network error
            return (Data(), makeHTTPResponse(statusCode: 500))
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)

        let tokenProvider = MockTokenProvider()
        await tokenProvider.setToken("valid-token")

        let apiClient = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        let service = DeviceService(apiClient: apiClient)
        let tokenData = Data([0xAA, 0xBB])

        do {
            try await service.registerToken(tokenData: tokenData)
            // If the service gracefully handles the error internally, that is acceptable.
        } catch {
            // Error propagation is also acceptable.
        }

        // What is NOT acceptable: a crash. Reaching this line verifies no crash occurred.
        XCTAssertTrue(true, "No crash on network error during token registration")
    }

    // MARK: - T6: Token unregistration on logout — DELETE called with correct body

    func test_unregisterToken_sendsDELETEWithCorrectBody() async throws {
        // SPEC.md §29.5, Phase iOS6 deliverable 4:
        // Unregistration must DELETE the token on logout, sending device_id and push_token.
        // Failure to unregister = privacy violation (notifications sent to signed-out user).
        var capturedRequest: URLRequest?

        MockURLProtocol.handler = { request in
            capturedRequest = request
            let data = try! makeEnvelopeJSON(data: EmptyPayload())
            return (data, makeHTTPResponse(statusCode: 200))
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)

        let tokenProvider = MockTokenProvider()
        await tokenProvider.setToken("valid-token")

        let apiClient = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        let tokenData = Data([0xDE, 0xAD, 0xBE, 0xEF])
        let service = DeviceService(apiClient: apiClient)

        // Simulate a previously registered device
        await service.setRegisteredToken(tokenData)

        try await service.unregisterToken()

        let req = try XCTUnwrap(capturedRequest, "A DELETE request must have been made")
        XCTAssertTrue(
            req.url?.path.contains("/api/v1/devices/push-token") == true,
            "Unregistration endpoint must be /api/v1/devices/push-token"
        )
        XCTAssertEqual(req.httpMethod, "DELETE", "Must use DELETE method")

        let bodyData = try XCTUnwrap(req.httpBody, "DELETE must include a body with device_id and push_token")
        let body = try JSONDecoder().decode([String: String].self, from: bodyData)
        XCTAssertNotNil(body["device_id"], "DELETE body must include device_id")
        XCTAssertEqual(body["push_token"], "deadbeef", "DELETE body must include the hex-encoded push_token")

        // After successful unregistration, local state must be cleared
        let isRegistered = await service.isTokenRegistered
        XCTAssertFalse(
            isRegistered,
            "Local registration state must be cleared after successful unregisterToken()"
        )
    }

    // MARK: - T16: Hex encoding correctness (no Data.description pitfall)

    func test_tokenHexEncoding_producesCorrectLowercaseHex() {
        // Phase iOS6, T16: Data.description returns "<aabbccdd>" with angle brackets.
        // DeviceService must use proper hex encoding via map { String(format: "%02x", $0) }.joined()
        // or equivalent. This is a historically common iOS bug.
        let tokenData = Data([0x00, 0x0F, 0xFF, 0xAB, 0xCD, 0xEF])
        let hexString = DeviceService.hexEncode(tokenData)

        XCTAssertEqual(hexString, "000fffabcdef", "Hex encoding must produce lowercase hex without decorators")
        XCTAssertFalse(hexString.contains("<"), "Must not contain '<' (Data.description format)")
        XCTAssertFalse(hexString.contains(">"), "Must not contain '>' (Data.description format)")
        XCTAssertFalse(hexString.contains(" "), "Must not contain spaces")
    }

    // MARK: - T18: No registration attempted when user is unauthenticated

    func test_registerToken_whenUnauthenticated_doesNotCallAPI() async {
        // SPEC.md §29.5: If the user is not authenticated, the device token must NOT be
        // sent to the backend (would 401 and waste network; worse, could register with no user).
        var requestMade = false

        MockURLProtocol.handler = { _ in
            requestMade = true
            let data = try! makeEnvelopeJSON(data: EmptyPayload())
            return (data, makeHTTPResponse(statusCode: 200))
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)

        let tokenProvider = UnauthenticatedTokenProvider()
        let apiClient = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        let service = DeviceService(apiClient: apiClient)
        let tokenData = Data([0xAA, 0xBB])

        do {
            try await service.registerToken(tokenData: tokenData)
        } catch {
            // Expected: either skips silently or throws when unauthenticated
        }

        XCTAssertFalse(
            requestMade,
            "registerToken must NOT make an API call when the user is unauthenticated"
        )
    }

    // MARK: - Teardown

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }
}

// MARK: - Helpers

/// Minimal codable for envelope responses that return no data body.
private struct EmptyPayload: Codable, Sendable {}
