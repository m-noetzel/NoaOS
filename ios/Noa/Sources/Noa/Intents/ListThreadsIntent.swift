// ListThreadsIntent.swift — Siri Shortcut / App Intent to list recent Noa threads
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Expose a "List Recent Noa Threads" App Intent
//   - Return the titles of the most recent threads as a string
//   - Usable in the Shortcuts app to show thread titles as a menu or notification

#if canImport(AppIntents)
import AppIntents
import Foundation

// MARK: - ListThreadsIntent

/// Lists the titles of the user's most recent Noa threads.
///
/// Available as: "List Noa Threads" in Siri and the Shortcuts app.
/// Returns a formatted string of the most recent thread titles.
@available(iOS 16.0, *)
public struct ListThreadsIntent: AppIntent {

    public static let title: LocalizedStringResource = "List Noa Threads"
    public static let description = IntentDescription(
        "Show your most recent Noa conversation threads."
    )

    // MARK: - Parameters

    /// How many threads to show. Defaults to 5.
    @Parameter(
        title: "Number of Threads",
        description: "The number of recent threads to list (1-20)."
    )
    public var count: Int

    // MARK: - Init

    public init() {
        count = 5
    }

    public init(count: Int = 5) {
        self.count = max(1, min(20, count))
    }

    // MARK: - Perform

    public func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let tokenProvider = SharedIntentTokenProvider()
        guard await tokenProvider.accessToken() != nil else {
            throw ListThreadsIntentError.notAuthenticated
        }

        let client = ServiceFactory.makeAPIClient(
            environment: .current,
            tokenProvider: tokenProvider
        )

        let threads: [ThreadListItem] = try await client.get("/api/v1/threads")
        let limited = threads.prefix(max(1, count))

        if limited.isEmpty {
            return .result(value: "You have no threads yet. Open Noa to start chatting.")
        }

        let titles = limited.enumerated().map { index, thread in
            "\(index + 1). \(thread.title ?? "Untitled thread")"
        }.joined(separator: "\n")

        return .result(value: titles)
    }
}

// MARK: - Supporting types

@available(iOS 16.0, *)
private enum ListThreadsIntentError: Error, LocalizedError {
    case notAuthenticated

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "You must be signed in to Noa to use this shortcut."
        }
    }
}

/// Lightweight thread model for decoding the list endpoint.
private struct ThreadListItem: Decodable, Sendable {
    let id: UUID
    let title: String?

    enum CodingKeys: String, CodingKey {
        case id
        case title
    }
}
#endif
