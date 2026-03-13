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
    private let googleAuthService: GoogleAuthService
    private let settingsViewModel: SettingsViewModel

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

        // AuthViewModel is created first so the onUnauthorized callback can reference it.
        // iOS-H3: when APIClient receives an unrecoverable 401, it calls this callback
        // which transitions AuthGuard to LoginView.
        let authVM = AuthViewModel(authService: auth)

        // Main API client — uses AuthService as token provider, offline queue, and the
        // 401 callback that triggers the login screen.
        let client = ServiceFactory.makeAPIClient(
            tokenProvider: auth,
            offlineQueue: queue,
            onUnauthorized: { @Sendable [weak authVM] in
                // Dispatch to @MainActor because AuthViewModel is @MainActor-isolated.
                Task { @MainActor [weak authVM] in
                    authVM?.handleUnauthorized()
                }
            }
        )

        // Network monitor — wired to drain the offline queue when connectivity is restored.
        // iOS-H1: previously the monitor existed but drain() was never called on reconnect.
        let monitor = ServiceFactory.makeNetworkMonitor(draining: queue, via: client)

        let bio = BiometricService()
        let googleAuth = GoogleAuthService(
            apiClient: client,
            webAuthSession: ASWebAuthSessionAdapter()
        )

        authService      = auth
        apiClient        = client
        offlineQueue     = queue
        networkMonitor   = monitor
        authViewModel    = authVM
        approvalService  = ApprovalService(apiClient: client)
        biometricService = bio
        chatService      = ChatService(
            apiClient: client,
            baseURL: NoaEnvironment.current.baseURL,
            tokenProvider: auth
        )
        googleAuthService = googleAuth
        settingsViewModel = SettingsViewModel(
            googleAuthService: googleAuth,
            biometricService: bio
        )
    }

    var body: some Scene {
        WindowGroup {
            ContentView(
                authViewModel: authViewModel,
                chatService: chatService,
                approvalService: approvalService,
                biometricService: biometricService,
                settingsViewModel: settingsViewModel
            )
        }
    }
}
