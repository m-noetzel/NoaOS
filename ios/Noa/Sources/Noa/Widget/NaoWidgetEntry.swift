// NaoWidgetEntry.swift — WidgetKit timeline entry for the Noa home screen widget
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Carry the snapshot of the most recent thread for display by NaoWidgetView
//   - Conform to TimelineEntry (date drives when the widget refreshes)

#if canImport(WidgetKit)
import WidgetKit
import Foundation

// MARK: - NaoWidgetEntry

/// A single timeline entry representing a snapshot of the last thread.
public struct NaoWidgetEntry: TimelineEntry {
    /// The date at which this entry should be displayed.
    public let date: Date

    /// Title of the most recent thread, or nil if no threads exist.
    public let threadTitle: String?

    /// A short preview of the most recent message in the thread.
    public let lastMessagePreview: String?

    /// When the last message was created (used for relative timestamps in the view).
    public let lastMessageDate: Date?

    public init(
        date: Date,
        threadTitle: String?,
        lastMessagePreview: String?,
        lastMessageDate: Date?
    ) {
        self.date = date
        self.threadTitle = threadTitle
        self.lastMessagePreview = lastMessagePreview
        self.lastMessageDate = lastMessageDate
    }

    /// A placeholder entry used when no data is available yet.
    public static var placeholder: NaoWidgetEntry {
        NaoWidgetEntry(
            date: .now,
            threadTitle: "My first thread",
            lastMessagePreview: "How can I help you today?",
            lastMessageDate: .now
        )
    }

    /// An empty entry when no threads have been saved to shared storage.
    public static var empty: NaoWidgetEntry {
        NaoWidgetEntry(
            date: .now,
            threadTitle: nil,
            lastMessagePreview: nil,
            lastMessageDate: nil
        )
    }
}
#endif
