// SharedIntentTokenProvider.swift — Shared Keychain token reader for App Intents
// Spec ref: Phase IS1
//
// App Intents run in a separate process from the main app, so they cannot
// access the main app's actor-isolated AuthService. This minimal token
// provider reads the stored access token directly from the shared Keychain.

#if canImport(AppIntents)
import Foundation

/// Shared Keychain-based token provider for all App Intent processes.
/// Extracts the stored access token from the Keychain service entry.
///
/// Used by `SendMessageIntent` and `ListThreadsIntent`.
struct SharedIntentTokenProvider: TokenProviding, Sendable {
    func accessToken() async -> String? {
        return Self.readKeychainToken(service: "com.noetzel.NoaApp.accessToken")
    }

    func refreshAccessToken() async throws -> String {
        // Intents don't support interactive token refresh — surface a
        // "not authenticated" error so the user opens the main app.
        struct NotAuthenticated: Error, LocalizedError {
            var errorDescription: String? {
                "You must be signed in to Noa to use this shortcut."
            }
        }
        throw NotAuthenticated()
    }

    private static func readKeychainToken(service: String) -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess,
              let data = item as? Data,
              let token = String(data: data, encoding: .utf8)
        else {
            return nil
        }
        return token
    }
}
#endif
