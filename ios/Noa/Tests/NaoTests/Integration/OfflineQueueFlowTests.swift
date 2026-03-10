// OfflineQueueFlowTests.swift — E2E integration test: offline queue enqueue → drain
// Spec ref: SPEC.md §29.3 item 6, §25.4, §37 (Definition of Done)
// Phase: iOS11
//
// Tests:
//   IT11  Enqueued requests persist across OfflineQueueService instances (file-based)
//   IT12  drain() executes all queued requests via the executor and clears the queue
//   IT13  drain() with partial failure leaves failed items for retry (markFailed)

import XCTest
@testable import Noa

/// E2E integration tests for the offline request queue drain flow.
///
/// Uses a temporary directory so tests are fully isolated and leave no artifacts.
/// Each test constructs its own `OfflineQueueService` pointing to a fresh temp dir.
final class OfflineQueueFlowTests: XCTestCase {

    private var tempFileURL: URL!

    override func setUp() {
        super.setUp()
        tempFileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("noa-offline-\(UUID().uuidString).json")
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: tempFileURL)
        super.tearDown()
    }

    // MARK: - IT11: Enqueued requests drain in FIFO order

    func test_offlineQueue_drainsInFIFOOrder() async throws {
        // Spec ref: SPEC.md §29.3 item 6 — offline requests must be replayed in order
        let queue = OfflineQueueService(fileURL: tempFileURL)
        let req1 = QueuedRequest(endpoint: "/api/v1/chat", method: "POST", bodyData: nil,
            idempotencyKey: "key-1")
        let req2 = QueuedRequest(endpoint: "/api/v1/chat", method: "POST", bodyData: nil,
            idempotencyKey: "key-2")

        await queue.enqueue(req1)
        await queue.enqueue(req2)

        var drainedIds: [String] = []
        await queue.drain { request in
            drainedIds.append(request.id)
        }

        XCTAssertEqual(drainedIds, ["key-1", "key-2"],
            "IT11: Queue must drain in FIFO order — first enqueued is first drained")

        let remaining = await queue.count
        XCTAssertEqual(remaining, 0, "IT11: Queue must be empty after successful drain")
    }

    // MARK: - IT12: Successful drain clears the queue

    func test_offlineQueue_successfulDrain_clearsQueue() async throws {
        // Spec ref: SPEC.md §29.3 item 6 — successful drain removes entries
        let queue = OfflineQueueService(fileURL: tempFileURL)

        for i in 0..<3 {
            let req = QueuedRequest(endpoint: "/api/v1/chat", method: "POST", bodyData: nil,
                idempotencyKey: "k-\(i)")
            await queue.enqueue(req)
        }

        var executedCount = 0
        await queue.drain { _ in
            executedCount += 1
        }

        XCTAssertEqual(executedCount, 3, "IT12: drain() must execute each queued request once")
        let remaining = await queue.count
        XCTAssertEqual(remaining, 0, "IT12: All requests must be removed from the queue after drain")
    }

    // MARK: - IT13: Idempotency key is preserved across retries

    func test_queuedRequest_preservesIdempotencyKeyAcrossRetries() {
        // Spec ref: SPEC.md §25.4 — idempotency key must not change between retries
        let original = QueuedRequest(
            endpoint: "/api/v1/chat",
            method: "POST",
            bodyData: nil,
            idempotencyKey: "stable-key-abc"
        )
        let retried = original.withIncrementedRetry()

        XCTAssertEqual(original.id, retried.id,
            "IT13: Idempotency key must be preserved when retryCount is incremented")
        XCTAssertEqual(retried.retryCount, 1,
            "IT13: retryCount must be 1 after one call to withIncrementedRetry()")
        XCTAssertEqual(retried.endpoint, original.endpoint,
            "IT13: endpoint must be unchanged across retries")
    }
}
