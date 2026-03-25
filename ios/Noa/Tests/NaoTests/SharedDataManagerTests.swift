// SharedDataManagerTests.swift — IS1: Tests for App Group shared data bridge
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Tests:
//   T1  saveLastThreadSnapshot encodes and stores thread data
//   T2  loadLastThreadSnapshot decodes stored data
//   T3  Preview string truncated to 200 characters
//   T4  loadLastThreadSnapshot returns nil when no data stored
//   T5  saveLastThreadSnapshot with nil values round-trips correctly
//   T6  ThreadSnapshot JSON encoding uses iso8601 date strategy
//   T7  Multiple saves — latest write wins

import Testing
import Foundation
@testable import Noa

// MARK: - SharedDataManagerTests

@Suite("SharedDataManager — App Group shared storage")
struct SharedDataManagerTests {

    // Use an in-memory substitute: inject a real UserDefaults with a test suite name
    // so tests don't pollute the real App Group defaults and don't require
    // the App Groups entitlement to be provisioned.
    private static let testSuiteName = "group.com.noetzel.NoaApp.tests"

    private func makeManager() -> (SharedDataManager, UserDefaults) {
        let defaults = UserDefaults(suiteName: Self.testSuiteName)!
        // Clear previous test data
        defaults.removePersistentDomain(forName: Self.testSuiteName)
        let manager = SharedDataManager(userDefaults: defaults)
        return (manager, defaults)
    }

    // T1 — save stores non-nil data under the snapshot key
    @Test("save writes data to UserDefaults")
    func test_saveWritesData() {
        let (manager, defaults) = makeManager()
        manager.saveLastThreadSnapshot(
            threadTitle: "My thread",
            lastMessagePreview: "Hello from Noa",
            lastMessageDate: Date(timeIntervalSince1970: 1_700_000_000)
        )
        let raw = defaults.data(forKey: "noa_last_thread_snapshot")
        #expect(raw != nil)
    }

    // T2 — load decodes the stored snapshot
    @Test("load returns saved snapshot")
    func test_loadReturnsSavedSnapshot() {
        let (manager, _) = makeManager()
        let savedDate = Date(timeIntervalSince1970: 1_700_000_000)
        manager.saveLastThreadSnapshot(
            threadTitle: "Test thread",
            lastMessagePreview: "Last message",
            lastMessageDate: savedDate
        )
        let loaded = manager.loadLastThreadSnapshot()
        #expect(loaded != nil)
        #expect(loaded?.threadTitle == "Test thread")
        #expect(loaded?.lastMessagePreview == "Last message")
        // Date round-trip: iso8601 has 1-second precision
        let diff = abs((loaded?.lastMessageDate?.timeIntervalSince1970 ?? 0) - savedDate.timeIntervalSince1970)
        #expect(diff < 1.0)
    }

    // T3 — preview text is truncated to 200 characters
    @Test("long preview is truncated to 200 characters")
    func test_previewTruncatedTo200Chars() {
        let (manager, _) = makeManager()
        let longText = String(repeating: "a", count: 500)
        manager.saveLastThreadSnapshot(
            threadTitle: "Thread",
            lastMessagePreview: longText,
            lastMessageDate: nil
        )
        let loaded = manager.loadLastThreadSnapshot()
        #expect(loaded?.lastMessagePreview?.count == 200)
    }

    // T4 — load returns nil when nothing has been saved
    @Test("load returns nil when no snapshot stored")
    func test_loadReturnsNilWhenEmpty() {
        let (manager, _) = makeManager()
        let result = manager.loadLastThreadSnapshot()
        #expect(result == nil)
    }

    // T5 — nil title and nil preview round-trip correctly
    @Test("nil fields round-trip through save/load")
    func test_nilFieldsRoundTrip() {
        let (manager, _) = makeManager()
        manager.saveLastThreadSnapshot(
            threadTitle: nil,
            lastMessagePreview: nil,
            lastMessageDate: nil
        )
        let loaded = manager.loadLastThreadSnapshot()
        #expect(loaded != nil)
        #expect(loaded?.threadTitle == nil)
        #expect(loaded?.lastMessagePreview == nil)
        #expect(loaded?.lastMessageDate == nil)
    }

    // T6 — ThreadSnapshot JSON uses iso8601 date encoding
    @Test("ThreadSnapshot encodes date as iso8601 string")
    func test_threadSnapshotDateEncoding() throws {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let snapshot = ThreadSnapshot(
            threadTitle: "title",
            lastMessagePreview: "preview",
            lastMessageDate: date
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(snapshot)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let dateStr = json?["lastMessageDate"] as? String
        #expect(dateStr != nil)
        #expect(dateStr?.contains("2023") == true)  // 1_700_000_000 is in Nov 2023
    }

    // T7 — second save overwrites the first
    @Test("second save overwrites first")
    func test_secondSaveOverwritesFirst() {
        let (manager, _) = makeManager()
        manager.saveLastThreadSnapshot(
            threadTitle: "Old thread",
            lastMessagePreview: "Old message",
            lastMessageDate: nil
        )
        manager.saveLastThreadSnapshot(
            threadTitle: "New thread",
            lastMessagePreview: "New message",
            lastMessageDate: nil
        )
        let loaded = manager.loadLastThreadSnapshot()
        #expect(loaded?.threadTitle == "New thread")
        #expect(loaded?.lastMessagePreview == "New message")
    }
}
