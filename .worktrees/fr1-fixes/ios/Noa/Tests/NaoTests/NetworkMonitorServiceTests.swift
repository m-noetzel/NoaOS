// NetworkMonitorServiceTests.swift — Unit tests for NetworkMonitorService
// Spec ref: SPEC.md §29.3 item 6
// Phase: iOS9

import XCTest
@testable import Noa

// MARK: - Mock Path Monitor

/// Testable stand-in for NWPathMonitor that fires connectivity changes on demand.
final class MockPathMonitor: NWPathMonitorInterface, @unchecked Sendable {

    // nonisolated(unsafe): tests are single-threaded per case; set/read before/after async ops.
    nonisolated(unsafe) private var handler: (@Sendable (Bool) -> Void)?
    nonisolated(unsafe) var startCallCount = 0
    nonisolated(unsafe) var cancelCallCount = 0
    nonisolated(unsafe) var _currentIsConnected: Bool = false

    var currentIsConnected: Bool { _currentIsConnected }

    func start(queue: DispatchQueue, handler: @escaping @Sendable (Bool) -> Void) {
        startCallCount += 1
        self.handler = handler
    }

    func cancel() {
        cancelCallCount += 1
    }

    /// Fires the registered path update handler, simulating a real connectivity change.
    func simulateConnectivityChange(_ connected: Bool) {
        _currentIsConnected = connected
        handler?(connected)
    }
}

// MARK: - Tests

final class NetworkMonitorServiceTests: XCTestCase {

    // MARK: - T1: Initial state is disconnected before path monitor fires

    func test_initialState_isDisconnected() async {
        // A fresh service must report disconnected until the path monitor fires.
        let mock = MockPathMonitor()
        let svc = NetworkMonitorService(pathMonitor: mock)
        let connected = await svc.isConnected
        XCTAssertFalse(connected, "Service must start in disconnected state")
    }

    // MARK: - T2: Connectivity change (connected) updates state

    func test_connectivityChange_updatesConnectedState() async throws {
        let mock = MockPathMonitor()
        let svc = NetworkMonitorService(pathMonitor: mock)

        let expectation = XCTestExpectation(description: "onChange fires with connected=true")
        await svc.startMonitoring { connected in
            if connected { expectation.fulfill() }
        }

        mock.simulateConnectivityChange(true)
        await fulfillment(of: [expectation], timeout: 1.0)

        let connected = await svc.isConnected
        XCTAssertTrue(connected, "isConnected must be true after path becomes satisfied")
    }

    // MARK: - T3: Connectivity change (disconnected) updates state

    func test_connectivityChange_updatesDisconnectedState() async throws {
        let mock = MockPathMonitor()
        let svc = NetworkMonitorService(pathMonitor: mock)

        // Start connected
        await svc.startMonitoring { _ in }
        mock.simulateConnectivityChange(true)
        try await Task.sleep(nanoseconds: 20_000_000) // 20ms — let actor update settle

        // Now disconnect
        let expectation = XCTestExpectation(description: "onChange fires with connected=false")
        await svc.startMonitoring { connected in
            if !connected { expectation.fulfill() }
        }
        mock.simulateConnectivityChange(false)
        await fulfillment(of: [expectation], timeout: 1.0)

        let connected = await svc.isConnected
        XCTAssertFalse(connected, "isConnected must be false after path becomes unsatisfied")
    }

    // MARK: - T4: stopMonitoring is idempotent (no crash on double-stop)

    func test_stopMonitoring_isIdempotent() async {
        let mock = MockPathMonitor()
        let svc = NetworkMonitorService(pathMonitor: mock)
        await svc.startMonitoring { _ in }

        await svc.stopMonitoring()
        await svc.stopMonitoring() // second call must not crash or deadlock
        // Reaching here == test passes
        XCTAssertGreaterThanOrEqual(
            mock.cancelCallCount, 1,
            "cancel() must be called at least once on stopMonitoring()"
        )
    }
}
