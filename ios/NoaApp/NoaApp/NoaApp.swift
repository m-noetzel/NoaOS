import SwiftUI
import Noa

// MARK: - Null token provider for the AuthService bootstrap client

private struct NullTokenProvider: TokenProviding {
    func accessToken() async -> String? { nil }
    func refreshAccessToken() async throws -> String {
        throw URLError(.userAuthenticationRequired)
    }
}

// MARK: - App entry

@main
struct NoaApp: App {

    // MARK: Service graph

    private let authService: AuthService
    private let apiClient: APIClient
    private let authViewModel: AuthViewModel
    private let chatService: ChatService
    private let approvalService: ApprovalService
    private let biometricService: BiometricService
    private let offlineQueue: OfflineQueueService
    private let networkMonitor: NetworkMonitorService

    init() {
        // Bootstrap client — used only by AuthService for login/refresh (no bearer token needed).
        let bootstrapClient = ServiceFactory.makeAPIClient(
            tokenProvider: NullTokenProvider()
        )
        let auth = AuthService(
            apiClient: bootstrapClient,
            keychainService: "com.noetzel.noa.tokens"
        )

        // Offline queue — persists write requests while the device is offline.
        let queue = OfflineQueueService()

        // Main API client — uses AuthService as token provider and the offline queue.
        let client = ServiceFactory.makeAPIClient(
            tokenProvider: auth,
            networkMonitor: nil,  // monitor wired below after client is created
            offlineQueue: queue
        )

        // Network monitor — wired to drain the offline queue when connectivity is restored.
        // iOS-H1: previously the monitor existed but drain() was never called on reconnect.
        let monitor = ServiceFactory.makeNetworkMonitor(draining: queue, via: client)

        authService      = auth
        apiClient        = client
        offlineQueue     = queue
        networkMonitor   = monitor
        authViewModel    = AuthViewModel(authService: auth)
        approvalService  = ApprovalService(apiClient: client)
        biometricService = BiometricService()
        chatService      = ChatService(
            apiClient: client,
            baseURL: NoaEnvironment.current.baseURL,
            tokenProvider: auth
        )
    }

    var body: some Scene {
        WindowGroup {
            ContentView(
                authViewModel: authViewModel,
                chatService: chatService,
                approvalService: approvalService,
                biometricService: biometricService
            )
        }
    }
}
