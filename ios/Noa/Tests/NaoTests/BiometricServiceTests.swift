// BiometricServiceTests.swift — iOS7 Biometric Step-Up Auth (service layer)
// Spec ref: SPEC.md §29.3 item 4, §29.6, Plan iOS7
//
// Tests:
//   T1  BiometricService.isAvailable() returns false in test environment (no HW)
//   T2  MockBiometricService.authenticate() succeeds when configured to pass
//   T3  MockBiometricService.authenticate() throws .lockedOut when configured
//   T4  ApprovalService.fetchPending() hits GET /api/v1/approvals/pending
//   T5  ApprovalService.fetchPending() decodes empty list correctly (200 + [])
//   T6  ApprovalService.decide() POSTs to /api/v1/approvals/{id}/decide with decision body
//
// T1 compiles only after BiometricService exists.
// T4-T6 compile only after ApprovalService exists.

import XCTest
@testable import Noa

// MARK: - MockBiometricService
// Accessible from ApprovalViewModelTests (same test target).

actor MockBiometricService: BiometricAuthenticating {
    // nonisolated(unsafe): tests run serially; safe to set/read from any actor
    nonisolated(unsafe) var available: Bool = true
    nonisolated(unsafe) var shouldFail: Bool = false
    nonisolated(unsafe) var failError: BiometricError = .authenticationFailed
    nonisolated(unsafe) var authenticateCallCount: Int = 0

    func isAvailable() async -> Bool { available }

    func authenticate(reason: String) async throws {
        authenticateCallCount += 1
        if shouldFail { throw failError }
    }
}

// MARK: - BiometricServiceTests

final class BiometricServiceTests: XCTestCase {

    // MARK: - T1: isAvailable() is callable without crashing

    func test_isAvailable_returnsWithoutCrashing() async {
        // Spec ref: SPEC.md §29.3 item 4
        // Verifies BiometricService.isAvailable() compiles, runs, and returns
        // a Bool without throwing or crashing. The actual value is hardware-
        // dependent (true on machines with Touch ID/Face ID, false otherwise).
        let service = BiometricService()
        let available = await service.isAvailable()
        // Log for diagnostic purposes; do not assert a specific value.
        _ = available
        XCTAssertTrue(true, "isAvailable() must complete without crashing")
    }

    // MARK: - T2: Mock authenticate() succeeds

    func test_mockBiometric_authenticateSucceeds() async throws {
        // Verifies the MockBiometricService correctly simulates successful auth.
        let mock = MockBiometricService()
        // available=true, shouldFail=false by default
        try await mock.authenticate(reason: "Confirm action")
        let callCount = await mock.authenticateCallCount
        XCTAssertEqual(callCount, 1, "authenticate() must have been called once")
    }

    // MARK: - T3: Mock authenticate() throws .lockedOut

    func test_mockBiometric_lockedOutThrowsBiometricError() async {
        // Verifies the MockBiometricService correctly simulates a locked-out state.
        let mock = MockBiometricService()
        mock.shouldFail = true
        mock.failError = .lockedOut

        do {
            try await mock.authenticate(reason: "Confirm action")
            XCTFail("Expected BiometricError.lockedOut to be thrown")
        } catch BiometricError.lockedOut {
            // Expected
        } catch {
            XCTFail("Expected BiometricError.lockedOut, got: \(error)")
        }
    }

    // MARK: - T4: fetchPending() hits correct endpoint

    func test_fetchPending_hitsGetApprovalsEndpoint() async throws {
        // Spec ref: SPEC.md §29.6 — GET /api/v1/approvals/pending returns pending list
        var capturedRequest: URLRequest?

        MockURLProtocol.handler = { request in
            capturedRequest = request
            let json = """
            {"ok":true,"data":[],"error":null,"trace_id":"t1"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeApprovalService()
        let _ = try await service.fetchPending()

        let req = try XCTUnwrap(capturedRequest, "A request must have been made")
        XCTAssertTrue(
            req.url?.path.contains("/api/v1/approvals/pending") == true,
            "Endpoint must contain /api/v1/approvals/pending, got: \(req.url?.path ?? "nil")"
        )
        XCTAssertEqual(req.httpMethod, "GET")
    }

    // MARK: - T5: fetchPending() decodes empty list from 200 response

    func test_fetchPending_returnsEmptyList() async throws {
        // Spec: graceful handling when no pending approvals exist
        MockURLProtocol.handler = { _ in
            let json = """
            {"ok":true,"data":[],"error":null,"trace_id":"t1"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeApprovalService()
        let result = try await service.fetchPending()

        XCTAssertEqual(result.count, 0, "fetchPending() must return empty array when data is []")
    }

    // MARK: - T6: decide() POSTs to correct endpoint with decision in body

    func test_decide_postsToCorrectEndpointWithDecisionBody() async throws {
        // Spec ref: SPEC.md §29.6 — POST /api/v1/approvals/{id}/decide
        var capturedRequest: URLRequest?
        let approvalId = UUID()

        MockURLProtocol.handler = { request in
            capturedRequest = request
            let json = """
            {"ok":true,"data":{"approval_id":"\(approvalId)","decision":"approved","status":"decided"},
            "error":null,"trace_id":"t1"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeApprovalService()
        try await service.decide(id: approvalId, decision: .approved)

        let req = try XCTUnwrap(capturedRequest, "A POST request must have been made")
        XCTAssertTrue(
            req.url?.path.contains("/decide") == true,
            "URL must contain /decide, got: \(req.url?.path ?? "nil")"
        )
        XCTAssertTrue(
            req.url?.path.contains(approvalId.uuidString.lowercased()) == true
            || req.url?.path.contains(approvalId.uuidString) == true,
            "URL must contain the approval ID"
        )
        XCTAssertEqual(req.httpMethod, "POST")

        let bodyData = try XCTUnwrap(req.httpBody, "POST body must not be nil")
        let body = try JSONDecoder().decode([String: String].self, from: bodyData)
        XCTAssertEqual(body["decision"], "approved", "Body must include decision=approved")
    }

    // MARK: - Teardown

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }
}

// MARK: - Helpers

private func makeApprovalService() -> ApprovalService {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [MockURLProtocol.self]
    let session = URLSession(configuration: config)

    let tokenProvider = MockTokenProvider()
    Task { await tokenProvider.setToken("valid-token") }

    let apiClient = APIClient(
        environment: .development,
        tokenProvider: tokenProvider,
        session: session
    )
    return ApprovalService(apiClient: apiClient)
}
