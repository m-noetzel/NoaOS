// NaoWidgetProvider.swift — WidgetKit TimelineProvider for the Noa widget
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Provide placeholder, snapshot, and timeline entries to WidgetKit
//   - Read the most recent thread data from the App Group shared UserDefaults
//     written by SharedDataManager (main app → widget data bridge)
//
// Design note: The widget cannot make network calls in its provider. All data
// must come from the shared UserDefaults that the main app writes to. This is
// the standard WidgetKit pattern for widgets that display app-sourced data.

#if canImport(WidgetKit)
import WidgetKit
import Foundation

// MARK: - NaoWidgetProvider

public struct NaoWidgetProvider: TimelineProvider {

    let sharedDataManager: SharedDataManager

    public init(sharedDataManager: SharedDataManager = SharedDataManager()) {
        self.sharedDataManager = sharedDataManager
    }

    // MARK: - TimelineProvider

    public func placeholder(in context: Context) -> NaoWidgetEntry {
        .placeholder
    }

    public func getSnapshot(
        in context: Context,
        completion: @escaping (NaoWidgetEntry) -> Void
    ) {
        let entry = buildEntry()
        completion(entry)
    }

    public func getTimeline(
        in context: Context,
        completion: @escaping (Timeline<NaoWidgetEntry>) -> Void
    ) {
        let entry = buildEntry()
        // Refresh every 15 minutes so the widget stays reasonably up-to-date
        // without draining battery. The main app also triggers a reload via
        // WidgetCenter.shared.reloadAllTimelines() after new messages arrive.
        let nextRefresh = Calendar.current.date(byAdding: .minute, value: 15, to: .now) ?? .now
        let timeline = Timeline(entries: [entry], policy: .after(nextRefresh))
        completion(timeline)
    }

    // MARK: - Internal

    /// Builds a timeline entry from the current shared data snapshot.
    /// Internal (not private) so that test extensions can call it directly.
    func buildEntry() -> NaoWidgetEntry {
        guard let data = sharedDataManager.loadLastThreadSnapshot() else {
            return .empty
        }
        return NaoWidgetEntry(
            date: .now,
            threadTitle: data.threadTitle,
            lastMessagePreview: data.lastMessagePreview,
            lastMessageDate: data.lastMessageDate
        )
    }
}
#endif
