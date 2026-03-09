// OfflineQueueService.swift — File-based FIFO offline request queue
// Spec ref: SPEC.md §29.3 item 6, §25.4, §36.3 item 6
// Phase: iOS9

import Foundation

// MARK: - OfflineQueuing protocol

/// Protocol for queuing write requests when the device is offline.
/// Concrete types: `OfflineQueueService` (production), mock in tests.
public protocol OfflineQueuing: Sendable {
    /// Appends a request to the end of the FIFO queue and persists it.
    func enqueue(_ request: QueuedRequest) async
    /// Removes and returns the front item, or `nil` if the queue is empty.
    func dequeue() async -> QueuedRequest?
    /// Returns (without removing) the front item.
    func peek() async -> QueuedRequest?
    /// Total number of queued requests.
    var count: Int { get async }
    /// Increments `retryCount` for the item with the given id.
    /// If `retryCount` reaches `maxRetries`, the item is removed.
    func markFailed(id: String) async
    /// Removes all queued requests.
    func clear() async
    /// Executes all queued requests in FIFO order by calling `executor` for each.
    /// Successfully executed items are dequeued; the executor runs serially.
    func drain(executor: @escaping @Sendable (QueuedRequest) async throws -> Void) async
}

// MARK: - OfflineQueueService

/// Actor-isolated, file-based FIFO queue for offline HTTP write requests.
///
/// Requests are persisted to a JSON file in the app's Documents directory.
/// On drain, each request is passed to `executor` (APIClient replay logic).
/// Failed items are retried up to `maxRetries` times; afterwards they are dropped.
///
/// Spec constants (§29.3 item 6):
/// - Max retries: 5
/// - Backoff: 1s, 2s, 4s, 8s, 16s (applied by the caller between drain invocations)
public actor OfflineQueueService: OfflineQueuing {

    // MARK: - Spec constants

    /// Maximum number of retry attempts before a queued request is discarded.
    public static let maxRetries = 5

    /// Exponential backoff delays in seconds between retry attempts.
    /// Index maps to attempt number (0 = first retry → 1s, …, 4 = fifth retry → 16s).
    public static let backoffIntervals: [TimeInterval] = [1.0, 2.0, 4.0, 8.0, 16.0]

    // MARK: - Private state

    private var queue: [QueuedRequest] = []
    private let fileURL: URL

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - Init

    /// Creates a queue backed by the given file URL.
    /// If omitted, defaults to `<Documents>/noa_offline_queue.json`.
    public init(fileURL: URL? = nil) {
        if let fileURL {
            self.fileURL = fileURL
        } else {
            let docs = FileManager.default.urls(
                for: .documentDirectory, in: .userDomainMask
            ).first!
            self.fileURL = docs.appendingPathComponent("noa_offline_queue.json")
        }
        // Load persisted queue synchronously during init (actor initializer is not async)
        if let data = try? Data(contentsOf: self.fileURL),
           let loaded = try? Self.decoder.decode([QueuedRequest].self, from: data) {
            self.queue = loaded
        }
    }

    // MARK: - OfflineQueuing

    public var count: Int { queue.count }

    public func enqueue(_ request: QueuedRequest) {
        queue.append(request)
        persist()
    }

    public func dequeue() -> QueuedRequest? {
        guard !queue.isEmpty else { return nil }
        let item = queue.removeFirst()
        persist()
        return item
    }

    public func peek() -> QueuedRequest? {
        queue.first
    }

    public func markFailed(id: String) {
        guard let index = queue.firstIndex(where: { $0.id == id }) else { return }
        let updated = queue[index].withIncrementedRetry()
        if updated.retryCount >= Self.maxRetries {
            queue.remove(at: index)
        } else {
            // Move to the end so other items get a chance while this one waits
            queue.remove(at: index)
            queue.append(updated)
        }
        persist()
    }

    public func clear() {
        queue.removeAll()
        persist()
    }

    public func drain(
        executor: @escaping @Sendable (QueuedRequest) async throws -> Void
    ) async {
        // Snapshot count to avoid processing items added during this drain pass
        let initialCount = queue.count
        var processed = 0

        while processed < initialCount, !queue.isEmpty {
            guard let item = queue.first else { break }
            queue.removeFirst()
            processed += 1
            persist()

            do {
                try await executor(item)
                // Success — item was already removed above
            } catch {
                // Failure — re-queue with incremented retry count if budget remains
                let failed = item.withIncrementedRetry()
                if failed.retryCount < Self.maxRetries {
                    queue.append(failed)
                }
                persist()
            }
        }
    }

    // MARK: - Persistence

    private func persist() {
        guard let data = try? Self.encoder.encode(queue) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
