// ServiceFactory.swift — Composition root for production service wiring
// Spec ref: SPEC.md §29.4 (Connection Security), Phase iOS11 MV4
//
// Responsibilities:
//   - Create URLSession instances with CertificatePinningDelegate in production builds
//   - Create URLSession instances without pinning in DEBUG builds (avoids localhost TLS issues)
//   - Provide factory methods for APIClient and VoiceService wired to the pinned session
//
// Usage:
//   let client = ServiceFactory.makeAPIClient(tokenProvider: myTokenProvider)
//   let voice  = ServiceFactory.makeVoiceService(tokenProvider: myTokenProvider)
//
// The SSEClient is not created here because it is constructed per-endpoint by ChatViewModel
// with an injected session; callers that need pinning should pass `ServiceFactory.makePinnedSession()`.

import Foundation

// MARK: - ServiceFactory

/// Static composition root that wires certificate-pinned URLSessions into production services.
///
/// In `#if DEBUG` builds the pinning delegate is omitted so that the simulator and
/// local-backend development work without TLS certificates.
/// In non-DEBUG (Release/Archive) builds every outbound URLSession is backed by
/// `CertificatePinningDelegate` initialised with `PinnedCertificates.spkiHashes`.
///
/// Spec ref: SPEC.md §29.4
public enum ServiceFactory {

    // MARK: - URLSession

    /// Creates a URLSession appropriate for the current build configuration.
    ///
    /// - In **Release** builds: the session's delegate is `CertificatePinningDelegate`
    ///   configured with `PinnedCertificates.spkiHashes`.  All connections that do not
    ///   present a certificate whose SPKI hash is in the pinned set are rejected.
    /// - In **DEBUG** builds: a plain session with no delegate is returned so that the
    ///   simulator and local Noa backend (HTTP on localhost:8000) function normally.
    ///
    /// - Parameter configuration: The `URLSessionConfiguration` to use.
    ///   Defaults to `.default` with a 30-second request timeout.
    /// - Returns: A configured `URLSession`.
    public static func makePinnedSession(
        configuration: URLSessionConfiguration? = nil
    ) -> URLSession {
        let config = configuration ?? {
            let c = URLSessionConfiguration.default
            c.timeoutIntervalForRequest = 30
            c.timeoutIntervalForResource = 30
            return c
        }()

        #if DEBUG
        // No pinning in debug: localhost uses plain HTTP, no real server certificate.
        return URLSession(configuration: config)
        #else
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: PinnedCertificates.spkiHashes)
        return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
        #endif
    }

    /// Creates a URLSession tuned for long-running voice uploads, with pinning in Release builds.
    ///
    /// - Returns: A `URLSession` with a 120-second request timeout and a 150-second resource timeout.
    public static func makePinnedVoiceSession() -> URLSession {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120   // transcription may take up to 2 min
        config.timeoutIntervalForResource = 150  // > backend timeout so server-side 504 surfaces first

        #if DEBUG
        return URLSession(configuration: config)
        #else
        let delegate = CertificatePinningDelegate(pinnedSPKIHashes: PinnedCertificates.spkiHashes)
        return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
        #endif
    }

    // MARK: - APIClient

    /// Creates a production `APIClient` using a certificate-pinned URLSession.
    ///
    /// - Parameters:
    ///   - environment: The `NoaEnvironment` to target. Defaults to `.current`.
    ///   - tokenProvider: The `TokenProviding` instance used for Bearer auth injection.
    ///   - networkMonitor: Optional `NetworkMonitoring` for offline detection.
    ///   - offlineQueue: Optional `OfflineQueuing` for write-request queuing when offline.
    /// - Returns: A fully wired `APIClient`.
    public static func makeAPIClient(
        environment: NoaEnvironment = .current,
        tokenProvider: any TokenProviding,
        networkMonitor: (any NetworkMonitoring)? = nil,
        offlineQueue: (any OfflineQueuing)? = nil
    ) -> APIClient {
        APIClient(
            environment: environment,
            tokenProvider: tokenProvider,
            session: makePinnedSession(),
            networkMonitor: networkMonitor,
            offlineQueue: offlineQueue
        )
    }

    // MARK: - VoiceService

    /// Creates a production `VoiceService` using a certificate-pinned URLSession.
    ///
    /// - Parameters:
    ///   - environment: The `NoaEnvironment` to target. Defaults to `.current`.
    ///   - tokenProvider: The `TokenProviding` instance used for Bearer auth injection.
    /// - Returns: A fully wired `VoiceService`.
    public static func makeVoiceService(
        environment: NoaEnvironment = .current,
        tokenProvider: any TokenProviding
    ) -> VoiceService {
        VoiceService(
            environment: environment,
            tokenProvider: tokenProvider,
            session: makePinnedVoiceSession()
        )
    }
}
