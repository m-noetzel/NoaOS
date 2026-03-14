// SettingsView.swift — Settings tab with Google OAuth2 section
// Spec ref: SPEC.md §29.3 (Mobile Access — OAuth2), §12.1, §12.2
// Phase GO3
//
// Shows the Google account connection status and connect/disconnect controls.
// Uses NavigationStack with a Form layout matching TranscriptionProviderView.

import SwiftUI

// MARK: - SettingsView

/// Root settings view with Google account connection management.
public struct SettingsView: View {

    // MARK: - Dependencies

    @State var viewModel: SettingsViewModel
    let authViewModel: AuthViewModel

    // MARK: - Init

    public init(viewModel: SettingsViewModel, authViewModel: AuthViewModel) {
        self._viewModel = State(wrappedValue: viewModel)
        self.authViewModel = authViewModel
    }

    // MARK: - Body

    public var body: some View {
        List {
            // MARK: - Backend Connection section (iOS-H5)
            Section("Backend") {
                backendSection
            }

            // MARK: - Google Account section
            Section("Google Account") {
                googleSection
            }

            // MARK: - Voice section
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
        .onAppear {
            Task {
                await viewModel.loadStatus()
                await viewModel.checkBackendHealth()
            }
        }
        // Disconnect confirmation alert
        .alert("Disconnect Google Account?", isPresented: $viewModel.showDisconnectConfirmation) {
            Button("Disconnect", role: .destructive) {
                Task { await viewModel.disconnectGoogle() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Your Google Calendar and Gmail connection will be removed. You can reconnect anytime.")
        }
        // Error alert
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) {
                viewModel.errorMessage = nil
            }
        } message: {
            if let msg = viewModel.errorMessage {
                Text(msg)
            }
        }
    }

    // MARK: - Backend section (iOS-H5)

    @ViewBuilder
    private var backendSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Backend URL")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(viewModel.backendURL)
                .font(.caption.monospaced())
                .foregroundStyle(.primary)
                .textSelection(.enabled)
        }
        .padding(.vertical, 4)

        HStack {
            Text("Connection")
            Spacer()
            switch viewModel.backendStatus {
            case .unknown:
                Text("Not checked")
                    .foregroundStyle(.secondary)
            case .checking:
                ProgressView()
                    .controlSize(.small)
            case .reachable:
                Label("Reachable", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                    .font(.callout)
            case .unreachable(let reason):
                VStack(alignment: .trailing, spacing: 2) {
                    Label("Unreachable", systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                        .font(.callout)
                    Text(reason)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.trailing)
                }
            }
        }

        Button {
            Task { await viewModel.checkBackendHealth() }
        } label: {
            Label("Test Connection", systemImage: "network")
        }
        .disabled({
            if case .checking = viewModel.backendStatus { return true }
            return false
        }())
        .accessibilityLabel("Test backend connection")
    }

    // MARK: - Google section

    @ViewBuilder
    private var googleSection: some View {
        switch viewModel.googleStatus {
        case .loading:
            HStack {
                Text("Google Account")
                    .foregroundStyle(.secondary)
                Spacer()
                ProgressView()
                    .controlSize(.small)
            }

        case .disconnected:
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Google Account")
                    Text("Calendar & Gmail access")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    Task { await viewModel.connectGoogle() }
                } label: {
                    if viewModel.isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text("Connect")
                            .bold()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading)
                .accessibilityLabel("Connect Google account")
            }

        case .connected(let email):
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Google Account")
                    if let email = email, !email.isEmpty {
                        Text(email)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        Label("Connected", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundStyle(.green)
                    }
                }
                Spacer()
                Button(role: .destructive) {
                    viewModel.showDisconnectConfirmation = true
                } label: {
                    if viewModel.isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text("Disconnect")
                    }
                }
                .disabled(viewModel.isLoading)
                .accessibilityLabel("Disconnect Google account")
            }
        }
    }
}
