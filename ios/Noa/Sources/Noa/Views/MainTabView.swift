// MainTabView.swift — Root tab navigation (Chat, Approvals, Settings)
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 4, Phase iOS8 deliverable 6
//
// Uses NavigationSplitView on iPad/large screen and a TabView on iPhone.
// The Chat tab embeds ThreadListView in the sidebar and ChatView in the detail.
// The Settings tab now includes a TranscriptionProviderView row (iOS8).

import SwiftUI

@MainActor
public struct MainTabView: View {

    // MARK: - Dependencies

    let authViewModel: AuthViewModel
    let chatService: ChatService
    let approvalService: any ApprovalServicing
    let biometricService: any BiometricAuthenticating

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
        biometricService: any BiometricAuthenticating
    ) {
        self.authViewModel = authViewModel
        self.chatService = chatService
        self.approvalService = approvalService
        self.biometricService = biometricService
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

            // MARK: Settings tab
            NavigationStack {
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
            .tabItem {
                Label("Settings", systemImage: "gearshape")
            }
            .tag(2)
        }
    }
}
