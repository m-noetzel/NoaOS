// ApprovalDetailView.swift — Approval detail with approve/deny and biometric gate
// Spec ref: SPEC.md §29.3 item 4, §29.6, Phase iOS7 deliverable 4

import SwiftUI

/// Shows a single approval's details and dry-run preview.
/// High-risk approvals trigger Face ID / Touch ID before submission (§29.3 item 4).
public struct ApprovalDetailView: View {

    @Bindable var viewModel: ApprovalDetailViewModel
    @Environment(\.dismiss) private var dismiss

    public init(viewModel: ApprovalDetailViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                // MARK: - Risk badge + domain header
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Approval Request")
                            .font(.headline)
                        Label(viewModel.approval.domain, systemImage: "globe")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    riskBadge
                }
                .padding()
                .background(.background.secondary)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                // MARK: - Dry-run preview
                if let preview = viewModel.approval.previewText {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Action Preview", systemImage: "eye")
                            .font(.subheadline.bold())

                        Text(preview)
                            .font(.body)
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(.background.secondary)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }

                // MARK: - Biometric notice for high-risk
                if viewModel.approval.riskTier == .high {
                    Label(
                        "Face ID / Touch ID required to approve this action",
                        systemImage: "faceid"
                    )
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .padding(.horizontal, 4)
                }

                // MARK: - Action buttons
                HStack(spacing: 16) {
                    Button(role: .destructive) {
                        Task { await viewModel.decide(.denied) }
                    } label: {
                        Label("Deny", systemImage: "xmark.circle.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(viewModel.isSubmitting)

                    Button {
                        Task { await viewModel.decide(.approved) }
                    } label: {
                        Label("Approve", systemImage: "checkmark.circle.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .disabled(viewModel.isSubmitting)
                }

                if viewModel.isSubmitting {
                    HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Review Request")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
        .onChange(of: viewModel.isDone) { _, isDone in
            if isDone { dismiss() }
        }
    }

    // MARK: - Private

    @ViewBuilder
    private var riskBadge: some View {
        let (color, label): (Color, String) = {
            switch viewModel.approval.riskTier {
            case .high: return (.red, "High Risk")
            case .medium: return (.orange, "Medium Risk")
            case .low: return (.green, "Low Risk")
            case .unknown: return (.secondary, "Unknown")
            }
        }()

        Text(label)
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
