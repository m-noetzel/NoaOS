// Environment.swift — NoaEnvironment configuration
// Spec ref: PLAN Phase iOS3, ARCH_INVARIANTS.md L11 (no hardcoded secrets)

import Foundation

/// Application environment configuration.
/// Only base URLs and non-sensitive settings are stored here.
/// No API keys, secrets, or credentials are embedded.
public enum NoaEnvironment: Sendable {
    /// Local development backend (http://localhost:8000).
    case development
    /// Production backend — URL read from Info.plist key `NOA_BASE_URL`.
    /// Falls back to a clear error rather than a silent empty string.
    case production

    /// The base URL for this environment's API.
    public var baseURL: URL {
        switch self {
        case .development:
            // swiftlint:disable:next force_unwrapping
            return URL(string: "http://localhost:8000")!
        case .production:
            guard
                let urlString = Bundle.main.object(forInfoDictionaryKey: "NOA_BASE_URL") as? String,
                !urlString.isEmpty,
                let url = URL(string: urlString)
            else {
                // Fail loud: an empty base URL causes every request to fail silently.
                preconditionFailure(
                    "Production environment requires NOA_BASE_URL set in Info.plist. "
                        + "Do not fall back to localhost in production builds."
                )
            }
            return url
        }
    }

    /// The environment the app is currently running in.
    /// Override by setting `NOA_ENVIRONMENT=production` in the scheme's environment variables.
    public static var current: NoaEnvironment {
        #if DEBUG
        return .development
        #else
        return .production
        #endif
    }
}
