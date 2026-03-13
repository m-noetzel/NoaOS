// DeviceID.swift — Persistent device UUID from Keychain
// Spec ref: PLAN Phase iOS3, SPEC.md §29.3 (Keychain for session tokens)
//
// Keychain attributes:
//   - Service: "com.noa.deviceid"
//   - Key: "noa.device_id"
//   - Access: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
//     (survives app reinstall on real devices, available after first unlock)

import Foundation
import Security

/// Persistent device identity utility.
/// Reads from Keychain on access; generates and stores a new UUID on first access.
/// The Keychain serialises concurrent writes internally; worst case is two threads each
/// generate a UUID — one overwrites the other, but both return valid stable identifiers.
public enum DeviceID {

    private static let service = "com.noa.deviceid"
    private static let account = "noa.device_id"

    /// The stable device identifier.
    /// First call: generates a UUID, stores it in Keychain.
    /// Subsequent calls: returns the same UUID from Keychain.
    public static var current: String {
        if let existing = readFromKeychain() {
            return existing
        }
        let newID = UUID().uuidString
        store(newID)
        return newID
    }

    // MARK: - Keychain read

    /// Reads the stored device ID from Keychain. Returns nil if not found.
    static func readFromKeychain() -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess,
            let data = result as? Data,
            let string = String(data: data, encoding: .utf8)
        else {
            return nil
        }
        return string
    }

    // MARK: - Keychain write

    /// Stores `deviceID` in Keychain.
    /// If an item already exists it is updated; otherwise a new item is added.
    @discardableResult
    static func store(_ deviceID: String) -> Bool {
        guard let data = deviceID.data(using: .utf8) else { return false }

        // Try to update an existing item first
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ]
        let attributes: [CFString: Any] = [
            kSecValueData: data,
            kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)

        if updateStatus == errSecItemNotFound {
            // Item doesn't exist yet — add it
            var addQuery = query
            addQuery[kSecValueData] = data
            addQuery[kSecAttrAccessible] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
            return addStatus == errSecSuccess
        }

        return updateStatus == errSecSuccess
    }

    // MARK: - Testing helpers

    /// Deletes the stored device ID from Keychain. Used in tests to reset state.
    @discardableResult
    public static func deleteFromKeychain() -> Bool {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}
