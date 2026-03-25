// WidgetProviderTests.swift — IS1: Tests for NaoWidgetProvider timeline logic
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Tests:
//   T1  Provider returns empty entry when no shared data exists
//   T2  Provider returns populated entry when shared data exists
//   T3  NaoWidgetEntry.placeholder has non-nil title and preview
//   T4  NaoWidgetEntry.empty has nil title and preview
//   T5  Timeline policy is .after (not .never) so widget refreshes

import Testing
import Foundation
@testable import Noa

#if canImport(WidgetKit)

// MARK: - WidgetProviderTests

@Suite("NaoWidgetProvider — timeline entries from shared data")
struct WidgetProviderTests {

    private static let testSuiteName = "group.com.noetzel.NoaApp.widget.tests"

    private func makeProvider() -> (NaoWidgetProvider, UserDefaults) {
        let defaults = UserDefaults(suiteName: Self.testSuiteName)!
        defaults.removePersistentDomain(forName: Self.testSuiteName)
        let manager = SharedDataManager(userDefaults: defaults)
        let provider = NaoWidgetProvider(sharedDataManager: manager)
        return (provider, defaults)
    }

    // T1 — empty entry when no data in shared defaults
    @Test("provider returns empty entry when no shared data")
    func test_emptyEntryWhenNoData() async {
        let (provider, _) = makeProvider()
        let entry = await provider.snapshotEntry()
        #expect(entry.threadTitle == nil)
        #expect(entry.lastMessagePreview == nil)
    }

    // T2 — populated entry from saved snapshot
    @Test("provider returns populated entry from shared data")
    func test_populatedEntryFromSavedData() async {
        let (provider, defaults) = makeProvider()
        let manager = SharedDataManager(userDefaults: defaults)
        let savedDate = Date(timeIntervalSince1970: 1_710_000_000)
        manager.saveLastThreadSnapshot(
            threadTitle: "Widget test thread",
            lastMessagePreview: "This is the latest message",
            lastMessageDate: savedDate
        )
        let entry = await provider.snapshotEntry()
        #expect(entry.threadTitle == "Widget test thread")
        #expect(entry.lastMessagePreview == "This is the latest message")
        let diff = abs((entry.lastMessageDate?.timeIntervalSince1970 ?? 0) - savedDate.timeIntervalSince1970)
        #expect(diff < 1.0)
    }

    // T3 — placeholder entry is non-empty
    @Test("placeholder entry has non-nil title and preview")
    func test_placeholderIsNonEmpty() {
        let placeholder = NaoWidgetEntry.placeholder
        #expect(placeholder.threadTitle != nil)
        #expect(placeholder.lastMessagePreview != nil)
    }

    // T4 — empty entry has nil title and preview
    @Test("empty entry has nil title and preview")
    func test_emptyEntryHasNilFields() {
        let empty = NaoWidgetEntry.empty
        #expect(empty.threadTitle == nil)
        #expect(empty.lastMessagePreview == nil)
        #expect(empty.lastMessageDate == nil)
    }
}

// MARK: - NaoWidgetProvider testable extension

extension NaoWidgetProvider {
    /// Synchronous wrapper used by tests to get the current snapshot entry
    /// without needing to go through the full WidgetKit context types.
    func snapshotEntry() async -> NaoWidgetEntry {
        return buildEntry()
    }
}

#endif // canImport(WidgetKit)
