// OfflineQueueServiceTests.swift — Unit tests for OfflineQueueService
// Spec ref: SPEC.md §29.3 item 6, §25.4, §36.3 item 6
// Phase: iOS9

import XCTest
@testable import Noa

final class OfflineQueueServiceTests: XCTestCase {

    private var tempDir: URL!
    private var queueFile: URL!

    override func setUp() async throws {
        try await super.setUp()
        tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        queueFile = tempDir.appendingPathComponent("offline_queue.json")
    }

    override func tearDown() async throws {
        try? FileManager.default.removeItem(at: tempDir)
        try await super.tearDown()
    }

    private func makeQueue() -> OfflineQueueService {
        OfflineQueueService(fileURL: queueFile)
    }

    private func makeRequest(
        endpoint: String = "/api/v1/test",
        method: String = "POST"
    ) -> QueuedRequest {
        QueuedRequest(endpoint: endpoint, method: method, bodyData: nil)
    }

    // MARK: - T1: Enqueue increments count

    func test_enqueue_incrementsCount() async {
        // Spec ref: SPEC.md §29.3 item 6 — persistent FIFO queue
        let svc = makeQueue()
        await svc.enqueue(makeRequest())
        let count = await svc.count
        XCTAssertEqual(count, 1)
    }

    // MARK: - T2: Dequeue returns FIFO order

    func test_dequeue_returnsFIFOOrder() async {
        // Spec ref: §29.3 item 6 — FIFO semantics
        let svc = makeQueue()
        let reqA = QueuedRequest(endpoint: "/a", method: "POST", bodyData: nil)
        let reqB = QueuedRequest(endpoint: "/b", method: "POST", bodyData: nil)
        await svc.enqueue(reqA)
        await svc.enqueue(reqB)

        let first = await svc.dequeue()
        XCTAssertEqual(first?.endpoint, "/a", "First dequeue must return first-enqueued item")

        let second = await svc.dequeue()
        XCTAssertEqual(second?.endpoint, "/b")
    }

    // MARK: - T3: Dequeue from empty queue returns nil

    func test_dequeue_emptyQueue_returnsNil() async {
        let svc = makeQueue()
        let result = await svc.dequeue()
        XCTAssertNil(result, "Dequeue on empty queue must return nil")
    }

    // MARK: - T4: Persistence survives re-init (restart simulation)

    func test_persistence_survivesReinit() async {
        // Spec ref: §29.3 item 6 — file-based persistent storage
        let svc = makeQueue()
        let req = makeRequest()
        await svc.enqueue(req)

        // Simulate app restart — same file, fresh in-memory state
        let svc2 = makeQueue()
        let count = await svc2.count
        XCTAssertEqual(count, 1, "Queue must persist across re-initialization")

        let loaded = await svc2.dequeue()
        XCTAssertEqual(loaded?.id, req.id, "Persisted request id must match original")
    }

    // MARK: - T5: Idempotency key is preserved

    func test_idempotencyKey_preserved() async {
        // Spec ref: SPEC.md §25.4 — idempotency key must survive serialization
        let svc = makeQueue()
        let req = QueuedRequest(
            endpoint: "/api/v1/chat",
            method: "POST",
            bodyData: nil,
            idempotencyKey: "fixed-key-abc"
        )
        await svc.enqueue(req)

        let dequeued = await svc.dequeue()
        XCTAssertEqual(
            dequeued?.id, "fixed-key-abc",
            "Idempotency key must be preserved through enqueue → persist → dequeue"
        )
    }

    // MARK: - T6: markFailed increments retry count

    func test_markFailed_incrementsRetryCount() async {
        let svc = makeQueue()
        let req = makeRequest()
        await svc.enqueue(req)

        await svc.markFailed(id: req.id)

        let item = await svc.peek()
        XCTAssertEqual(item?.retryCount, 1, "markFailed must increment retryCount by 1")
    }

    // MARK: - T7: Item is dropped after maxRetries failures

    func test_markFailed_dropsAfterMaxRetries() async {
        // Spec ref: §29.3 item 6 — max 5 retries
        let svc = makeQueue()
        let req = makeRequest()
        await svc.enqueue(req)

        for _ in 0..<OfflineQueueService.maxRetries {
            await svc.markFailed(id: req.id)
        }

        let count = await svc.count
        XCTAssertEqual(count, 0, "Item must be dropped after \(OfflineQueueService.maxRetries) failures")
    }

    // MARK: - T8: clear() empties the queue

    func test_clear_emptiesQueue() async {
        let svc = makeQueue()
        await svc.enqueue(makeRequest())
        await svc.enqueue(makeRequest())

        await svc.clear()

        let count = await svc.count
        XCTAssertEqual(count, 0, "clear() must remove all queued requests")
    }

    // MARK: - T9: drain executes items in FIFO order

    func test_drain_executesInFIFOOrder() async {
        // Spec ref: §29.3 item 6 — auto-drain on connectivity restore
        let svc = makeQueue()
        let reqA = QueuedRequest(endpoint: "/a", method: "POST", bodyData: nil)
        let reqB = QueuedRequest(endpoint: "/b", method: "POST", bodyData: nil)
        let reqC = QueuedRequest(endpoint: "/c", method: "POST", bodyData: nil)
        await svc.enqueue(reqA)
        await svc.enqueue(reqB)
        await svc.enqueue(reqC)

        // Swift 6: use @unchecked Sendable wrapper to collect results from the @Sendable executor.
        // drain() calls its executor serially, so mutation is safe in practice.
        final class Collector: @unchecked Sendable { var items: [String] = [] }
        let collector = Collector()
        await svc.drain { request in
            collector.items.append(request.endpoint)
        }

        XCTAssertEqual(collector.items, ["/a", "/b", "/c"], "Drain must execute requests in FIFO order")
        let count = await svc.count
        XCTAssertEqual(count, 0, "Queue must be empty after successful drain")
    }

    // MARK: - T10: Backoff intervals match spec

    func test_backoffIntervals_matchSpec() {
        // Spec ref: §29.3 item 6 — 1s, 2s, 4s, 8s, 16s exponential backoff
        XCTAssertEqual(
            OfflineQueueService.backoffIntervals, [1.0, 2.0, 4.0, 8.0, 16.0],
            "Backoff intervals must match spec: 1, 2, 4, 8, 16 seconds"
        )
        XCTAssertEqual(OfflineQueueService.maxRetries, 5, "Max retries must be 5")
    }
}
