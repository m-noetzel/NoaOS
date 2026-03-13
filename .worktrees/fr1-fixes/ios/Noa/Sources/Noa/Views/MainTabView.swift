// MainTabView.swift — Root tab navigation (Chat, Approvals, Settings)
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 4, Phase iOS8 deliverable 6, Phase GO3
//
// Uses NavigationSplitView on iPad/large screen and a TabView on iPhone.
// The Chat tab embeds ThreadListView in the sidebar and ChatView in the detail.
// The Settings tab now shows SettingsView with Google OAuth section (GO3).
//
// iOS-M1: networkMonitor and offlineQueue are optional. When provided, the view
// calls stopMonitoring() / clear() on disappear so system resources are freed
// when the root view is removed from the hierarchy (e.g. on logout).

import SwiftUI

@MainActor
public struct MainTabView: View {

    // MARK: - Dependencies

    let authViewModel: AuthViewModel
    let chatService: ChatService
    let approvalService: any ApprovalServicing
    let biometricService: any BiometricAuthenticating
    /// iOS-M1: optional so that callers that don't use offline queue are not affected.
    let networkMonitor: (any NetworkMonitoring)?
    let offlineQueue: (any OfflineQueuing)?
    /// GO3: optional — when nil, falls back to the legacy settings list (TranscriptionProviderView only).
    let settingsViewModel: SettingsViewModel?

    // MARK: - State

    @State private var chatViewModel: ChatViewModel
    @State private var threadListViewModel: ThreadListViewModel
    @State private var approvalListViewModel: ApprovalListViewModel
    @State private var selectedThreadId: UUID? = nil

    // MARK: - Init

    public init(
        authViewModel: AuthViewModel,
        chatService: ChatService,
        approvalService: any ApprovalServicing,
        biometricService: any BiometricAuthenticating,
        networkMonitor: (any NetworkMonitoring)? = nil,
        offlineQueue: (any OfflineQueuing)? = nil,
        settingsViewModel: SettingsViewModel? = nil
    ) {
        self.authViewModel = authViewModel
        self.chatService = chatService
        self.approvalService = approvalService
        self.biometricService = biometricService
        self.networkMonitor = networkMonitor
        self.offlineQueue = offlineQueue
        self.settingsViewModel = settingsViewModel
        _chatViewModel = State(wrappedValue: ChatViewModel(chatService: chatService))
        _threadListViewModel = State(wrappedValue: ThreadListViewModel(chatService: chatService))
        _approvalListViewModel = State(wrappedValue: ApprovalListViewModel(service: approvalService))
    }

    public var body: some View {
        TabView {
            // MARK: Chat tab
            NavigationSplitView {
                ThreadListView(
                    viewModel: threadListViewModel,
                    selectedThreadId: $selectedThreadId
                )
            } detail: {
                if let threadId = selectedThreadId {
                    ChatView(viewModel: chatViewModel, threadId: threadId)
                } else {
                    ContentUnavailableView(
                        "Select a Thread",
                        systemImage: "bubble.left",
                        description: Text("Pick a thread or start a new one.")
                    )
                }
            }
            // iOS-H2: cancel the active SSE stream and clear the message list whenever
            // the user switches to a different thread. Without this, the old stream
            // continues delivering tokens to the new thread's view.
            .onChange(of: selectedThreadId) { _, _ in
                chatViewModel.cancelStreamAndClear()
            }
            .tabItem {
                Label("Chat", systemImage: "bubble.left.and.bubble.right")
            }
            .tag(0)

            // MARK: Approvals tab (iOS7)
            NavigationStack {
                ApprovalListView(
                    viewModel: approvalListViewModel,
                    approvalService: approvalService,
                    biometricService: biometricService
                )
            }
            .tabItem {
                Label("Approvals", systemImage: "checkmark.shield")
            }
            .tag(1)

            // MARK: Settings tab (GO3: uses SettingsView when settingsViewModel is provided)
            NavigationStack {
                if let settingsVM = settingsViewModel {
                    SettingsView(viewModel: settingsVM, authViewModel: authViewModel)
                } else {
                    // Legacy fallback: basic settings list without Google section
                    List {
                        Section("Voice") {
                            NavigationLink("Transcription Provider") {
                                TranscriptionProviderView()
                            }
                        }
                    }
                    .navigationTitle("Settings")
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button("Sign Out") {
                                Task { try? await authViewModel.logout() }
                            }
                        }
                    }
                }
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape")
            }
            .tag(2)
        }
        // iOS-M1: Stop background services when this root view disappears (e.g. on
        // logout). Without this, NWPathMonitor holds a live system resource and the
        // offline queue retains its file handle indefinitely.
        .onDisappear {
            Task {
                await networkMonitor?.stopMonitoring()
                await offlineQueue?.clear()
            }
        }
    }
}
