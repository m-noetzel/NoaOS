// SharedDataManager.swift — App Group shared storage bridge (main app ↔ widget)
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Write the most recent thread snapshot (title + last message preview + date)
//     to the App Group UserDefaults so the widget extension can read it
//   - Read that snapshot back for the timeline provider
//   - Optionally trigger a WidgetKit timeline reload after writes
//
// App Group ID: group.com.noetzel.NoaApp
// This ID must match the App Groups entitlement in the app target and the
// widget extension target.

import Foundation

// MARK: - ThreadSnapshot

/// A lightweight snapshot of a thread's title and most recent message.
/// Stored in the App Group UserDefaults under a single JSON key.
public struct ThreadSnapshot: Codable, Sendable {
    public let threadTitle: String?
    public let lastMessagePreview: String?
    public let lastMessageDate: Date?

    public init(
        threadTitle: String?,
        lastMessagePreview: String?,
        lastMessageDate: Date?
    ) {
        self.threadTitle = threadTitle
        self.lastMessagePreview = lastMessagePreview
        self.lastMessageDate = lastMessageDate
    }
}

// MARK: - SharedDataManager

/// Writes and reads the last-thread snapshot to/from the App Group UserDefaults.
///
/// Usage in main app (e.g. ThreadListViewModel.loadThreads completion):
/// ```swift
/// SharedDataManager().saveLastThreadSnapshot(
///     threadTitle: thread.title,
///     lastMessagePreview: lastMessage?.content,
///     lastMessageDate: lastMessage?.createdAt
/// )
/// ```
///
/// Usage in widget:
/// ```swift
/// let snapshot = SharedDataManager().loadLastThreadSnapshot()
/// ```
public struct SharedDataManager: @unchecked Sendable {

    // MARK: - Constants

    /// The App Group identifier that must be registered in both the app and widget entitlements.
    public static let appGroupIdentifier = "group.com.noetzel.NoaApp"

    static let snapshotKey = "noa_last_thread_snapshot"

    // MARK: - Private

    /// The UserDefaults suite used for storage. Injected for testability;
    /// production code uses the App Group suite.
    private let userDefaults: UserDefaults?

    // MARK: - Init

    /// Production initialiser — uses the App Group shared suite.
    public init() {
        self.userDefaults = UserDefaults(suiteName: Self.appGroupIdentifier)
    }

    /// Testable initialiser — accepts any UserDefaults instance.
    public init(userDefaults: UserDefaults) {
        self.userDefaults = userDefaults
    }

    // MARK: - Write

    /// Saves a snapshot of the most recent thread to the App Group UserDefaults.
    ///
    /// Call this whenever the thread list is refreshed or a new message arrives
    /// so the widget always has fresh data to display.
    ///
    /// - Parameters:
    ///   - threadTitle: The title of the most recent thread.
    ///   - lastMessagePreview: A snippet of the most recent message (will be truncated to 200 chars).
    ///   - lastMessageDate: The creation date of the most recent message.
    public func saveLastThreadSnapshot(
        threadTitle: String?,
        lastMessagePreview: String?,
        lastMessageDate: Date?
    ) {
        // Truncate the preview to avoid bloating UserDefaults
        let truncatedPreview = lastMessagePreview.map { String($0.prefix(200)) }

        let snapshot = ThreadSnapshot(
            threadTitle: threadTitle,
            lastMessagePreview: truncatedPreview,
            lastMessageDate: lastMessageDate
        )

        guard let defaults = userDefaults else {
            // App Group not configured — this is expected in simulator debug builds
            // that don't have the entitlement. Return gracefully.
            return
        }

        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            let data = try encoder.encode(snapshot)
            defaults.set(data, forKey: Self.snapshotKey)
        } catch {
            // Encoding failure is non-fatal; widget will show stale data
            return
        }

        // Signal WidgetKit to reload the timeline so the widget updates promptly
        reloadWidgetTimelines()
    }

    // MARK: - Read

    /// Loads the most recent thread snapshot from the App Group UserDefaults.
    ///
    /// Returns nil if no snapshot has been saved yet (first launch or no threads).
    public func loadLastThreadSnapshot() -> ThreadSnapshot? {
        guard let defaults = userDefaults else {
            return nil
        }
        guard let data = defaults.data(forKey: Self.snapshotKey) else {
            return nil
        }
        do {
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            return try decoder.decode(ThreadSnapshot.self, from: data)
        } catch {
            return nil
        }
    }

    // MARK: - Widget reload

    /// Asks WidgetKit to invalidate the Noa widget's timeline so it refreshes
    /// from the newly written UserDefaults data.
    ///
    /// This is a no-op when WidgetKit is not available (e.g. macOS or simulator
    /// builds without the widget extension installed).
    private func reloadWidgetTimelines() {
        #if canImport(WidgetKit)
        // Import WidgetKit lazily via @_silgen_name is not needed — we can import
        // at file scope guarded by canImport. But SharedDataManager is compiled
        // as part of the main Noa target which supports macOS 14 too. We use
        // a conditional import inside the method body to avoid the hard dependency.
        WidgetKitReloader.reload()
        #endif
    }
}

// MARK: - WidgetKitReloader

/// Thin wrapper so the WidgetCenter call is isolated behind canImport.
/// This prevents a linker error when compiling for a target without WidgetKit.
#if canImport(WidgetKit)
import WidgetKit

private enum WidgetKitReloader {
    static func reload() {
        WidgetCenter.shared.reloadAllTimelines()
    }
}
#endif
