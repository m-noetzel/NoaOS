// ServiceFactoryTests.swift — MV4: ServiceFactory composition root
// Spec ref: SPEC.md §29.4, Phase iOS11 MV4
//
// Tests:
//   SF1  makePinnedSession() returns a URLSession (not nil)
//   SF2  makePinnedVoiceSession() returns a URLSession (not nil)
//   SF3  makePinnedSession() in DEBUG has no CertificatePinningDelegate attached
//   SF4  makeAPIClient() returns an APIClient without crashing
//   SF5  makeVoiceService() returns a VoiceService without crashing
//   SF6  Multiple calls to makePinnedSession() return distinct URLSession instances
//   SF7  PinnedCertificates.spkiHashes is non-empty (prerequisite for production pinning)

import XCTest
@testable import Noa

final class ServiceFactoryTests: XCTestCase {

    // MARK: - SF1: makePinnedSession returns a URLSession

    func test_makePinnedSession_returnsURLSession() {
        // SPEC.md §29.4: Every outbound URLSession in production must use certificate pinning.
        // ServiceFactory.makePinnedSession() must return a non-nil, valid URLSession.
        let session = ServiceFactory.makePinnedSession()
        // URLSession is always non-nil — this exercises the code path without crashing.
        XCTAssertNotNil(session, "SF1: makePinnedSession() must return a valid URLSession")
    }

    // MARK: - SF2: makePinnedVoiceSession returns a URLSession

    func test_makePinnedVoiceSession_returnsURLSession() {
        // VoiceService uploads can take up to 2 minutes — a dedicated session with longer
        // timeouts must be returned without crashing.
        let session = ServiceFactory.makePinnedVoiceSession()
        XCTAssertNotNil(session, "SF2: makePinnedVoiceSession() must return a valid URLSession")
    }

    // MARK: - SF3: DEBUG session has no CertificatePinningDelegate

    func test_makePinnedSession_inDebug_hasNoPinningDelegate() {
        // SPEC.md §29.4 + development ergonomics: The local Noa backend uses plain HTTP on
        // localhost:8000.  In DEBUG builds, the session must NOT attach CertificatePinningDelegate
        // so that simulator + localhost development works without TLS certificates.
        #if DEBUG
        let session = ServiceFactory.makePinnedSession()
        XCTAssertNil(
            session.delegate as? CertificatePinningDelegate,
            "SF3: DEBUG session must not use CertificatePinningDelegate (localhost is plain HTTP)"
        )
        #else
        // In Release builds, the delegate IS a CertificatePinningDelegate — tested separately.
        XCTAssertTrue(true, "SF3: skipped in Release build")
        #endif
    }

    // MARK: - SF4: makeAPIClient does not crash

    func test_makeAPIClient_doesNotCrash() {
        // SPEC.md §29.4: The factory must assemble a fully wired APIClient backed by a
        // pinned (or DEBUG-safe) URLSession.  The call must not throw or crash.
        let tokenProvider = StubTokenProvider()
        let client = ServiceFactory.makeAPIClient(
            environment: .development,
            tokenProvider: tokenProvider
        )
        // APIClient is an actor; we can only assert it was constructed (non-nil).
        // Functional behaviour is covered by APIClientTests.
        XCTAssertNotNil(client, "SF4: makeAPIClient() must return a valid APIClient")
    }

    // MARK: - SF5: makeVoiceService does not crash

    func test_makeVoiceService_doesNotCrash() {
        // SPEC.md §29.4: The factory must assemble a VoiceService backed by a pinned
        // (or DEBUG-safe) URLSession with the correct timeout configuration.
        let tokenProvider = StubTokenProvider()
        let service = ServiceFactory.makeVoiceService(
            environment: .development,
            tokenProvider: tokenProvider
        )
        XCTAssertNotNil(service, "SF5: makeVoiceService() must return a valid VoiceService")
    }

    // MARK: - SF6: Each call returns a distinct URLSession

    func test_makePinnedSession_returnsFreshInstance() {
        // ServiceFactory must not cache sessions — each call returns its own instance
        // so that callers can manage the session lifetime independently.
        let s1 = ServiceFactory.makePinnedSession()
        let s2 = ServiceFactory.makePinnedSession()
        XCTAssertFalse(
            s1 === s2,
            "SF6: makePinnedSession() must return a new URLSession on each call"
        )
    }

    // MARK: - SF7: PinnedCertificates has at least one non-empty hash

    func test_pinnedCertificates_nonEmpty() {
        // SPEC.md §29.4: An empty pin set would cause all Release connections to be rejected.
        // Production builds depend on PinnedCertificates.spkiHashes being populated.
        let hashes = PinnedCertificates.spkiHashes
        XCTAssertFalse(
            hashes.isEmpty,
            "SF7: PinnedCertificates.spkiHashes must contain at least one entry"
        )
        for hash in hashes {
            XCTAssertFalse(
                hash.isEmpty,
                "SF7: Each entry in PinnedCertificates.spkiHashes must be a non-empty string"
            )
        }
    }
}

// MARK: - StubTokenProvider

/// Minimal TokenProviding stub for ServiceFactory construction tests.
/// Reuses the pattern from APIClientTests (MockTokenProvider) but is local to this file
/// to avoid duplicating a shared type that would cause a compile-time ambiguity.
private actor StubTokenProvider: TokenProviding {
    func accessToken() async -> String? { nil }
    func refreshAccessToken() async throws -> String {
        throw URLError(.userAuthenticationRequired)
    }
}
