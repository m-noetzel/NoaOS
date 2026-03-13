// KeychainService.swift — Keychain CRUD wrapper
// Spec ref: SPEC.md §29.3, Phase iOS4 deliverables 1 & 2
//
// Static helpers for saving, reading, and deleting string values in the
// system Keychain using Security framework primitives.

import Foundation
import Security

/// Namespace for Keychain access using Security framework.
public enum KeychainService {

    // MARK: - Constants

    /// Keychain accessibility level used for all stored tokens.
    /// `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` ensures tokens are:
    ///  - inaccessible while device is locked (before first unlock after boot)
    ///  - NOT backed up to iCloud (device-only)
    ///
    /// Spec ref: SPEC.md §29.3 deliverable 2.
    public static let accessibility: String =
        kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String

    // MARK: - Public API

    /// Saves (or overwrites) a string value in the Keychain.
    ///
    /// - Parameters:
    ///   - value: UTF-8 string to store.
    ///   - service: Keychain service identifier (e.g. `"com.noa.tokens"`).
    ///   - account: Keychain account label (e.g. `"access_token"`).
    /// - Returns: `true` on success.
    @discardableResult
    public static func save(value: String, service: String, account: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        // Try to update an existing item first.
        let query = baseQuery(service: service, account: account)
        let update: [CFString: Any] = [kSecValueData: data]
        let updateStatus = SecItemUpdate(query as CFDictionary, update as CFDictionary)

        if updateStatus == errSecSuccess {
            return true
        }

        // Item does not exist yet — add it.
        var addQuery = baseQuery(service: service, account: account)
        addQuery[kSecValueData] = data
        addQuery[kSecAttrAccessible] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        return addStatus == errSecSuccess
    }

    /// Reads a string value from the Keychain.
    ///
    /// - Returns: The stored string, or `nil` if not found.
    public static func read(service: String, account: String) -> String? {
        var query = baseQuery(service: service, account: account)
        query[kSecReturnData] = true
        query[kSecMatchLimit] = kSecMatchLimitOne

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8)
        else { return nil }

        return string
    }

    /// Deletes a Keychain entry.
    ///
    /// - Returns: `true` if the item was deleted or was not present; `false` on unexpected error.
    @discardableResult
    public static func delete(service: String, account: String) -> Bool {
        let query = baseQuery(service: service, account: account)
        let status = SecItemDelete(query as CFDictionary)
        // errSecItemNotFound is treated as success (idempotent delete).
        return status == errSecSuccess || status == errSecItemNotFound
    }

    // MARK: - Private

    private static func baseQuery(service: String, account: String) -> [CFString: Any] {
        [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ]
    }
}
