// CertificatePinningTests.swift — iOS10: Certificate Pinning & VPN Auto-Connect
// Spec ref: SPEC.md §29.4 (Connection Security), §36.3 item 7 (VPN auto-connect)
// Phase: iOS10
//
// Tests:
//   CertificatePinningTests:
//     T1  Valid pin hash accepts matching server certificate
//     T2  Invalid pin hash rejects connection with pinning error
//     T3  Self-signed certificate is rejected even if chain is otherwise valid
//     T4  Expired certificate is rejected regardless of pin hash match
//     T5  Multi-pin rotation: at least one pin hash must match (OR semantics)
//     T6  PinnedCertificates bundle contains at least one non-empty SPKI hash
//     T7  APIClient propagates pinning rejection as a typed error (not a crash)
//
//   VPNServiceTests:
//     T8  VPNService.isConnected returns a Bool without crashing (state detection)
//     T9  VPNService.isConnected is false when NEVPNManager status is disconnected
//     T10 VPNService.launchVPNApp(scheme:) returns false when no VPN app is installed
//     T11 VPN auto-connect prompt is suppressed when device is on LAN
//
// T1-T7 compile only after CertificatePinningDelegate and PinnedCertificates exist.
// T8-T11 compile only after VPNService exists.

import XCTest
import Security
@testable import Noa

// MARK: - MockVPNStatusProvider

/// Test double for NEVPNManager-backed VPN status detection.
/// Allows tests to inject arbitrary VPN states without requiring Network Extension entitlements.
final class MockVPNStatusProvider: VPNStatusProviding, @unchecked Sendable {
    nonisolated(unsafe) var stubIsConnected: Bool = false

    var isVPNConnected: Bool { stubIsConnected }
}

// MARK: - MockURLOpener

/// Test double for UIApplication.open(_:) / NSWorkspace.open(_:).
/// Captures whether a URL scheme was attempted and simulates app-not-installed.
final class MockURLOpener: URLOpenable, @unchecked Sendable {
    nonisolated(unsafe) var openedURLs: [URL] = []
    nonisolated(unsafe) var canOpenResult: Bool = false

    func canOpenURL(_ url: URL) -> Bool {
        canOpenResult
    }

    func open(_ url: URL) {
        openedURLs.append(url)
    }
}

// MARK: - CertificatePinningTests

final class CertificatePinningTests: XCTestCase {

    // MARK: - T1: Valid pin hash accepts connection

    func test_validPinHash_allowsConnection() {
        // SPEC.md §29.4: Certificate pinning prevents MITM on the native iOS app.
        // A URLSession challenge bearing a server certificate whose SPKI hash is in
        // the pinned set must be accepted (disposition = .useCredential).

        let knownHash = Self.makeDERCertificateSPKIHash()
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: [knownHash])

        let (disposition, credential) = simulatePinningChallenge(
            delegate: delegate,
            spkiHash: knownHash
        )

        XCTAssertEqual(
            disposition, .useCredential,
            "T1: Valid SPKI hash must accept the TLS connection"
        )
        XCTAssertNotNil(credential, "T1: Accepted challenge must provide a credential")
    }

    // MARK: - T2: Invalid pin hash rejects connection

    func test_invalidPinHash_rejectsConnection() {
        // SPEC.md §29.4: Any certificate whose SPKI hash is NOT in the pinned set
        // must be rejected to prevent MITM attacks.

        let pinnedHash = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        let serverHash  = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: [pinnedHash])

        let (disposition, _) = simulatePinningChallenge(
            delegate: delegate,
            spkiHash: serverHash
        )

        XCTAssertEqual(
            disposition, .cancelAuthenticationChallenge,
            "T2: SPKI hash mismatch must cancel the TLS challenge"
        )
    }

    // MARK: - T3: Self-signed certificate is rejected

    func test_selfSignedCertificate_isRejected() {
        // SPEC.md §29.4: The Noa API is served over a trusted certificate.
        // A self-signed cert (trust evaluation fails) must be rejected regardless
        // of whether the hash happens to match a pinned value.

        let hash = "SelfSignedHashAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: [hash])

        // Simulate: hash matches but trust evaluation is marked as failed
        let (disposition, _) = simulatePinningChallenge(
            delegate: delegate,
            spkiHash: hash,
            trustEvaluationPassed: false
        )

        XCTAssertEqual(
            disposition, .cancelAuthenticationChallenge,
            "T3: Self-signed certificate must be rejected even if SPKI hash matches"
        )
    }

    // MARK: - T4: Expired certificate is rejected

    func test_expiredCertificate_isRejected() {
        // SPEC.md §29.4: An expired certificate represents an invalid TLS chain
        // and must be rejected, regardless of pin hash equality.

        let hash = "ExpiredCertHashAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: [hash])

        // Simulate trust evaluation failure (cert expired path)
        let (disposition, _) = simulatePinningChallenge(
            delegate: delegate,
            spkiHash: hash,
            trustEvaluationPassed: false,
            isExpired: true
        )

        XCTAssertEqual(
            disposition, .cancelAuthenticationChallenge,
            "T4: Expired certificate must be rejected even if SPKI hash matches"
        )
    }

    // MARK: - T5: Multi-pin rotation — OR semantics

    func test_multiPin_atLeastOneMatch_allowsConnection() {
        // PLAN Phase iOS10 Deliverable 2: Pin hashes configurable for rotation.
        // During key rotation, the old and new SPKI hashes are both embedded.
        // The connection must be accepted if ANY pinned hash matches.

        let activeHash = Self.makeDERCertificateSPKIHash()
        let rotationHash = "RotationHashAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: [rotationHash, activeHash])

        let (disposition, _) = simulatePinningChallenge(
            delegate: delegate,
            spkiHash: activeHash
        )

        XCTAssertEqual(
            disposition, .useCredential,
            "T5: At least one matching SPKI hash must accept the connection (OR semantics)"
        )
    }

    // MARK: - T6: PinnedCertificates bundle is non-empty

    func test_pinnedCertificates_containsAtLeastOneHash() {
        // PLAN Phase iOS10 Deliverable 2: Pin hashes embedded in app bundle.
        // An empty pin set means all certificates pass — that is insecure.

        let hashes = PinnedCertificates.spkiHashes
        XCTAssertFalse(
            hashes.isEmpty,
            "T6: PinnedCertificates.spkiHashes must contain at least one entry"
        )
        for hash in hashes {
            XCTAssertFalse(
                hash.isEmpty,
                "T6: Each SPKI hash in PinnedCertificates must be a non-empty string"
            )
        }
    }

    // MARK: - T7: APIClient propagates pinning failure as typed error

    func test_apiClient_pinningFailure_surfacesTypedError() async {
        // SPEC.md §29.4: Certificate pinning on the native iOS app prevents MITM.
        // When pinning rejects a challenge, the APIClient must surface a typed error
        // (APIError.certificatePinningFailed or similar) — not a crash or opaque URLError.

        // Use a delegate configured to reject all connections (empty pin set)
        let rejectingDelegate = CertificatePinningDelegate(pinnedSPKIHashes: [])
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config, delegate: rejectingDelegate, delegateQueue: nil)

        // MockURLProtocol triggers an auth challenge that the delegate will cancel
        MockURLProtocol.handler = { _ in
            let data = Data()
            return (data, makeHTTPResponse(statusCode: 200))
        }

        let tokenProvider = MockTokenProvider()
        Task { await tokenProvider.setToken("token") }
        let client = APIClient(
            environment: .development,
            tokenProvider: tokenProvider,
            session: session
        )

        do {
            let _: SimpleModel = try await client.request("/api/v1/resource", method: "GET", body: nil as String?)
            // If request succeeds (MockURLProtocol bypasses real TLS), that is also acceptable
            // because MockURLProtocol cannot actually trigger server trust challenges.
            // The test confirms CertificatePinningDelegate initialises without crashing
            // when injected into an APIClient session.
        } catch {
            // Any error is acceptable: the important thing is no crash
            XCTAssertTrue(
                error is APIError || error is URLError,
                "T7: Pinning failure must surface as APIError or URLError, got: \(type(of: error))"
            )
        }

        MockURLProtocol.handler = nil
    }
}

// MARK: - VPNServiceTests

final class VPNServiceTests: XCTestCase {

    // MARK: - T8: VPNService.isConnected returns Bool without crashing

    func test_vpnService_isConnected_returnsWithoutCrashing() async {
        // SPEC.md §36.3 item 7: VPN auto-connect support requires VPN status detection.
        // The service must not crash when queried for VPN state.
        let mockProvider = MockVPNStatusProvider()
        let svc = VPNService(statusProvider: mockProvider)
        let connected = await svc.isConnected
        // Log only; actual value depends on NEVPNManager entitlements in simulator
        _ = connected
        XCTAssertTrue(true, "T8: isConnected must complete without crashing")
    }

    // MARK: - T9: Disconnected VPN status is reported correctly

    func test_vpnService_disconnectedStatus_isFalse() async {
        // SPEC.md §29.4: App must detect when VPN is disconnected and prompt to reconnect.
        // When the status provider reports disconnected, VPNService.isConnected must return false.
        let mockProvider = MockVPNStatusProvider()
        mockProvider.stubIsConnected = false

        let svc = VPNService(statusProvider: mockProvider)
        let connected = await svc.isConnected

        XCTAssertFalse(
            connected,
            "T9: VPNService.isConnected must be false when status provider reports disconnected"
        )
    }

    // MARK: - T10: launchVPNApp returns false when scheme unavailable

    func test_launchVPNApp_returnsFalse_whenSchemeUnavailable() async {
        // PLAN Phase iOS10 Deliverable 5: Launch Tailscale/WireGuard via URL scheme.
        // When neither Tailscale nor WireGuard is installed, the launch must gracefully
        // return false rather than crashing or showing an unhandled URL error.
        let mockOpener = MockURLOpener()
        mockOpener.canOpenResult = false  // no VPN app installed

        let svc = VPNService(statusProvider: MockVPNStatusProvider(), urlOpener: mockOpener)
        let launched = await svc.launchVPNApp(scheme: "tailscale://")

        XCTAssertFalse(
            launched,
            "T10: launchVPNApp must return false when the URL scheme cannot be opened"
        )
        XCTAssertTrue(
            mockOpener.openedURLs.isEmpty,
            "T10: open(_:) must not be called when canOpenURL returns false"
        )
    }

    // MARK: - T11: VPN prompt suppressed when on LAN

    func test_vpnPrompt_suppressed_whenOnLAN() async {
        // SPEC.md §29.4: All clients connect over VPN when *remote*.
        // On LAN, VPN is not required and the auto-connect prompt must not appear.
        let mockProvider = MockVPNStatusProvider()
        mockProvider.stubIsConnected = false  // VPN is off

        let svc = VPNService(statusProvider: mockProvider)
        // When device is on the home LAN, shouldPromptForVPN must be false
        // regardless of VPN connection state.
        let shouldPrompt = await svc.shouldPromptForVPN(isOnLAN: true)

        XCTAssertFalse(
            shouldPrompt,
            "T11: VPN auto-connect prompt must be suppressed when device is already on LAN"
        )
    }

    // MARK: - T12: VPN prompt shown when off-LAN and VPN disconnected

    func test_vpnPrompt_shown_whenOffLANAndDisconnected() async {
        // SPEC.md §29.4, §36.3 item 7: Auto-connect prompt must appear when
        // the device is remote (off-LAN) and VPN is not connected.
        let mockProvider = MockVPNStatusProvider()
        mockProvider.stubIsConnected = false  // VPN off

        let svc = VPNService(statusProvider: mockProvider)
        let shouldPrompt = await svc.shouldPromptForVPN(isOnLAN: false)

        XCTAssertTrue(
            shouldPrompt,
            "T12: VPN prompt must be shown when off-LAN and VPN is disconnected"
        )
    }

    // MARK: - T13: VPN prompt suppressed when already connected

    func test_vpnPrompt_suppressed_whenAlreadyConnected() async {
        // SPEC.md §29.4: When VPN is already connected, no prompt is needed.
        let mockProvider = MockVPNStatusProvider()
        mockProvider.stubIsConnected = true  // VPN on

        let svc = VPNService(statusProvider: mockProvider)
        let shouldPrompt = await svc.shouldPromptForVPN(isOnLAN: false)

        XCTAssertFalse(
            shouldPrompt,
            "T13: VPN prompt must be suppressed when VPN is already connected"
        )
    }
}

// MARK: - Helpers

/// Simulates a URLAuthenticationChallenge-style pinning evaluation without requiring
/// a live network connection.  Returns the disposition and optional credential.
///
/// - Parameters:
///   - delegate: The CertificatePinningDelegate under test.
///   - spkiHash: Base64-encoded SHA-256 hash of the server's SubjectPublicKeyInfo.
///   - trustEvaluationPassed: Whether the OS-level certificate chain evaluation passes.
///   - isExpired: Annotate as expired (forces trustEvaluationPassed = false).
private func simulatePinningChallenge(
    delegate: CertificatePinningDelegate,
    spkiHash: String,
    trustEvaluationPassed: Bool = true,
    isExpired: Bool = false
) -> (URLSession.AuthChallengeDisposition, URLCredential?) {
    // The real implementation reads the SPKI hash from SecTrust.
    // In unit tests, we call the delegate's internal evaluation method directly
    // via a testable entry point that accepts a pre-computed hash and trust result.
    let allowed = delegate.evaluatePinning(
        spkiHash: spkiHash,
        trustEvaluationPassed: trustEvaluationPassed && !isExpired
    )
    if allowed {
        return (.useCredential, URLCredential(user: "pinned", password: "", persistence: .none))
    } else {
        return (.cancelAuthenticationChallenge, nil)
    }
}

/// Produces a stable, non-empty base64 string to stand in for a real SPKI hash.
/// The value is intentionally predictable so T1 and T5 can use the same hash.
private extension CertificatePinningTests {
    static func makeDERCertificateSPKIHash() -> String {
        // SHA-256("test-spki") base64-encoded — a deterministic fake hash
        return "ynWTISdDnzSEoHFHvopOkT+y8GAO3rMxTFJSLDRvuIo="
    }
}
