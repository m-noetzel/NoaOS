// ApprovalListView.swift — Pending approvals list with batch controls
// Spec ref: SPEC.md §29.6, §23.2, Phase iOS7 deliverable 3

import SwiftUI

/// Displays the list of pending approvals. Supports multi-selection for batch
/// approve/deny per SPEC.md §23.2. Tapping a row navigates to `ApprovalDetailView`.
public struct ApprovalListView: View {

    @Bindable var viewModel: ApprovalListViewModel

    let approvalService: any ApprovalServicing
    let biometricService: any BiometricAuthenticating

    /// iOS-M4: confirmation dialog state for batch deny.
    @State private var showBatchDenyConfirmation: Bool = false

    public init(
        viewModel: ApprovalListViewModel,
        approvalService: any ApprovalServicing,
        biometricService: any BiometricAuthenticating
    ) {
        self.viewModel = viewModel
        self.approvalService = approvalService
        self.biometricService = biometricService
    }

    public var body: some View {
        Group {
            if viewModel.isLoading {
                ProgressView("Loading approvals…")
            } else if viewModel.approvals.isEmpty {
                ContentUnavailableView(
                    "No Pending Approvals",
                    systemImage: "checkmark.shield",
                    description: Text("All approvals are up to date.")
                )
            } else {
                List(selection: $viewModel.selectedIds) {
                    ForEach(viewModel.approvals) { approval in
                        NavigationLink(value: approval) {
                            ApprovalRowView(approval: approval)
                        }
                        .tag(approval.id)
                    }
                }
                #if os(iOS)
                .environment(\.editMode, .constant(.active))
                #endif
                .safeAreaInset(edge: .bottom) {
                    if !viewModel.selectedIds.isEmpty {
                        BatchApprovalBar(
                            count: viewModel.selectedIds.count,
                            isProcessing: viewModel.isBatchProcessing,
                            onApprove: { Task { await viewModel.batchApprove() } },
                            // iOS-M4: show confirmation before executing batch deny
                            onDeny: { showBatchDenyConfirmation = true }
                        )
                    }
                }
            }
        }
        .navigationTitle("Approvals")
        .navigationDestination(for: Approval.self) { approval in
            ApprovalDetailView(
                viewModel: ApprovalDetailViewModel(
                    approval: approval,
                    service: approvalService,
                    biometric: biometricService
                )
            )
        }
        .task { await viewModel.load() }
        .refreshable { await viewModel.load() }
        // iOS-M4: Batch deny confirmation alert
        .confirmationDialog(
            "Deny \(viewModel.selectedIds.count) Approval\(viewModel.selectedIds.count == 1 ? "" : "s")?",
            isPresented: $showBatchDenyConfirmation,
            titleVisibility: .visible
        ) {
            Button("Deny All", role: .destructive) {
                Task { await viewModel.batchDeny() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will deny \(viewModel.selectedIds.count) selected approval\(viewModel.selectedIds.count == 1 ? "" : "s"). This action cannot be undone.")
        }
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }
}

// MARK: - ApprovalRowView

private struct ApprovalRowView: View {
    let approval: Approval

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Label(approval.domain, systemImage: "globe")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                RiskTierBadge(tier: approval.riskTier)
            }

            if let preview = approval.previewText {
                Text(preview)
                    .font(.body)
                    .lineLimit(3)
            }

            Text(approval.requestedAt, style: .relative)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - RiskTierBadge

private struct RiskTierBadge: View {
    let tier: RiskTier

    var body: some View {
        Text(tier.rawValue.capitalized)
            .font(.caption2.bold())
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(tierColor.opacity(0.15))
            .foregroundStyle(tierColor)
            .clipShape(Capsule())
    }

    private var tierColor: Color {
        switch tier {
        case .high: return .red
        case .medium: return .orange
        case .low: return .green
        case .unknown: return .secondary
        }
    }
}
