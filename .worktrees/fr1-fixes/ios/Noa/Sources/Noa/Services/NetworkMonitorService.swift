// NetworkMonitorService.swift — NWPathMonitor wrapper for connectivity state
// Spec ref: SPEC.md §29.3 item 6
// Phase: iOS9

import Foundation
import Network

// MARK: - NWPathMonitorInterface (testability seam)

/// Abstraction over NWPathMonitor, allowing injection of a mock in tests.
/// Production code uses `RealNWPathMonitor`; tests inject `MockPathMonitor`.
public protocol NWPathMonitorInterface: Sendable {
    /// The current connectivity state (satisfied == connected).
    var currentIsConnected: Bool { get }
    /// Starts monitoring. The `handler` fires on every path update.
    func start(queue: DispatchQueue, handler: @escaping @Sendable (Bool) -> Void)
    /// Stops monitoring and releases system resources.
    func cancel()
}

// MARK: - Real NWPathMonitor wrapper

/// Production implementation wrapping `Network.NWPathMonitor`.
final class RealNWPathMonitor: NWPathMonitorInterface, @unchecked Sendable {

    private let monitor = NWPathMonitor()

    var currentIsConnected: Bool {
        monitor.currentPath.status == .satisfied
    }

    func start(queue: DispatchQueue, handler: @escaping @Sendable (Bool) -> Void) {
        monitor.pathUpdateHandler = { path in
            handler(path.status == .satisfied)
        }
        monitor.start(queue: queue)
    }

    func cancel() {
        monitor.cancel()
    }
}

// MARK: - NetworkMonitoring protocol

/// Protocol that exposes the current connectivity state and change notifications.
/// Actors (APIClient, OfflineQueueService) use this to decide whether to queue requests.
public protocol NetworkMonitoring: Sendable {
    /// `true` when the device has a usable network path.
    var isConnected: Bool { get async }
    /// Registers a callback that fires on every connectivity change.
    /// Multiple calls replace the previous handler.
    func startMonitoring(onChange: @escaping @Sendable (Bool) -> Void) async
    /// Stops monitoring and cancels the underlying NWPathMonitor.
    func stopMonitoring() async
}

// MARK: - NetworkMonitorService

/// Actor-isolated service that observes NWPathMonitor and publishes connectivity changes.
///
/// Usage:
/// ```swift
/// let monitor = NetworkMonitorService()
/// await monitor.startMonitoring { connected in
///     if connected { await offlineQueue.drain(...) }
/// }
/// ```
public actor NetworkMonitorService: NetworkMonitoring {

    private var _isConnected: Bool = false
    private let pathMonitor: any NWPathMonitorInterface
    private var onChange: (@Sendable (Bool) -> Void)?

    // MARK: - Init

    public init(pathMonitor: (any NWPathMonitorInterface)? = nil) {
        self.pathMonitor = pathMonitor ?? RealNWPathMonitor()
    }

    // MARK: - NetworkMonitoring

    public var isConnected: Bool { _isConnected }

    public func startMonitoring(onChange: @escaping @Sendable (Bool) -> Void) {
        self.onChange = onChange
        pathMonitor.start(queue: .global(qos: .utility)) { [self] (connected: Bool) in
            Task { await self.handlePathChange(connected) }
        }
    }

    public func stopMonitoring() {
        pathMonitor.cancel()
        onChange = nil
    }

    // MARK: - Private

    private func handlePathChange(_ connected: Bool) {
        _isConnected = connected
        onChange?(connected)
    }
}
