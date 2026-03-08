// DeviceIDTests.swift — DeviceID persistence and Keychain tests
// Spec ref: PLAN Phase iOS3, SPEC.md §29.3
// Test plan: test-plan_iOS3.md T22-T23

import XCTest
@testable import Noa

final class DeviceIDTests: XCTestCase {

    override func setUp() {
        super.setUp()
        // Start each test with a clean Keychain state
        DeviceID.deleteFromKeychain()
    }

    override func tearDown() {
        // Clean up after each test
        DeviceID.deleteFromKeychain()
        super.tearDown()
    }

    // MARK: - T22: Device ID generated and persisted

    func test_deviceID_generatedAndPersisted() {
        // Spec ref: PLAN Phase iOS3, T22
        // First call: generates a UUID and stores it in Keychain.
        let firstID = DeviceID.current

        // Must be a valid UUID format
        XCTAssertNotNil(UUID(uuidString: firstID), "DeviceID must be a valid UUID string")
        XCTAssertEqual(firstID.count, 36, "UUID string must be 36 characters")

        // Second call: must return the SAME UUID (not generate a new one)
        let secondID = DeviceID.current
        XCTAssertEqual(
            firstID, secondID,
            "DeviceID must return the same UUID on subsequent calls (Keychain persistence)"
        )
    }

    // MARK: - T23: Device ID survives "app reinstall" simulation

    func test_deviceID_survivesAppReinstallSimulation() {
        // Spec ref: PLAN Phase iOS3, T23
        // Keychain persists across app deletion on real devices.
        // Simulate by: generate ID -> delete UserDefaults (not Keychain) -> read ID again.

        let originalID = DeviceID.current

        // Simulate app reinstall: clear UserDefaults (Keychain persists)
        UserDefaults.standard.removeObject(forKey: "noa.device_id")
        UserDefaults.standard.synchronize()

        // The DeviceID stored in Keychain must survive this reset
        let retrievedID = DeviceID.current
        XCTAssertEqual(
            originalID, retrievedID,
            "DeviceID must survive app reinstall simulation — it must use Keychain, not UserDefaults"
        )
    }

    // MARK: - Valid UUID format

    func test_deviceID_isValidUUIDFormat() {
        let id = DeviceID.current
        let parts = id.split(separator: "-")
        XCTAssertEqual(parts.count, 5, "UUID must have exactly 4 dash separators")
        XCTAssertEqual(id.count, 36, "UUID string must be 36 characters")
    }

    // MARK: - Uniqueness across "devices"

    func test_deviceID_uniquenessAcrossDevices() {
        // If we delete the Keychain entry, a fresh UUID is generated.
        // Two fresh UUIDs must never be equal.
        let id1 = DeviceID.current
        DeviceID.deleteFromKeychain()
        let id2 = DeviceID.current

        XCTAssertNotEqual(id1, id2, "Two independently generated device IDs must be unique")
    }

    // MARK: - Keychain is actually used (not UserDefaults)

    func test_deviceID_usesKeychain_notUserDefaults() {
        // Generate a device ID
        let id = DeviceID.current

        // Verify it is NOT stored in UserDefaults
        let userDefaultsValue = UserDefaults.standard.string(forKey: "noa.device_id")
        XCTAssertNil(userDefaultsValue, "DeviceID must NOT use UserDefaults — Keychain only")

        // Verify it IS in Keychain (via our internal read helper)
        let keychainValue = DeviceID.readFromKeychain()
        XCTAssertEqual(keychainValue, id, "DeviceID must be readable from Keychain")
    }
}
