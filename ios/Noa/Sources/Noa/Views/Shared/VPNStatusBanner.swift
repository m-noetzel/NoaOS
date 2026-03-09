// VPNStatusBanner.swift — VPN auto-connect prompt banner
// Spec ref: SPEC.md §29.4, §36.3 item 7, Phase iOS10 deliverable 6
//
// Responsibilities:
//   - Show a non-intrusive banner when VPN is required but disconnected
//   - Offer a one-tap action to launch the VPN client app

import SwiftUI

/// A banner view that prompts the user to connect to the VPN.
///
/// Shown when the device is off-LAN and VPN is disconnected.
/// The banner provides a button to launch Tailscale (primary) or WireGuard (fallback)
/// via their respective URL schemes.
///
/// Spec ref: SPEC.md §29.4, Phase iOS10 deliverable 6
public struct VPNStatusBanner: View {

    // MARK: - Properties

    /// Whether the banner is currently visible.
    /// When `false`, the view renders with zero height (no layout impact).
    public let isVisible: Bool

    /// Called when the user taps "Connect". Caller passes the desired scheme
    /// (e.g. "tailscale://") to `VPNService.launchVPNApp(scheme:)`.
    public let onConnect: () -> Void

    // MARK: - Init

    public init(isVisible: Bool, onConnect: @escaping () -> Void) {
        self.isVisible = isVisible
        self.onConnect = onConnect
    }

    // MARK: - Body

    public var body: some View {
        if isVisible {
            HStack(spacing: 12) {
                Image(systemName: "lock.slash.fill")
                    .foregroundStyle(.white)
                    .font(.system(size: 16, weight: .semibold))

                VStack(alignment: .leading, spacing: 2) {
                    Text("VPN Required")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text("Connect to reach the Noa server remotely.")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.85))
                }

                Spacer()

                Button(action: onConnect) {
                    Text("Connect")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.orange)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(.white)
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.orange)
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }
}

// MARK: - Preview

#if DEBUG
#Preview("VPN Banner — Visible") {
    VStack {
        VPNStatusBanner(isVisible: true) {
            print("Connect tapped")
        }
        Spacer()
    }
}

#Preview("VPN Banner — Hidden") {
    VStack {
        VPNStatusBanner(isVisible: false) {}
        Spacer()
    }
}
#endif
