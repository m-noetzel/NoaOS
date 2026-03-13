// VPNService.swift — VPN status detection and auto-connect prompt
// Spec ref: SPEC.md §29.4, §36.3 item 7, Phase iOS10 deliverables 3-5
//
// Responsibilities:
//   - Report whether the device VPN is currently connected
//   - Determine whether the auto-connect prompt should be shown
//   - Launch Tailscale or WireGuard via their URL schemes

import Foundation
import NetworkExtension
#if canImport(AppKit)
import AppKit
#endif
#if canImport(UIKit)
import UIKit
#endif

// MARK: - VPNStatusProviding

/// Protocol for VPN connection status, enabling test injection without NEVPNManager entitlements.
public protocol VPNStatusProviding: Sendable {
    /// Returns `true` when the VPN is connected.
    var isVPNConnected: Bool { get }
}

// MARK: - URLOpenable

/// Protocol abstracting UIApplication.open(_:) / NSWorkspace.open(_:) for testability.
public protocol URLOpenable: Sendable {
    /// Returns whether the given URL scheme can be opened on this device.
    func canOpenURL(_ url: URL) -> Bool
    /// Opens the given URL.
    func open(_ url: URL)
}

// MARK: - NEVPNManager Status Provider

/// Production implementation backed by NEVPNManager.
/// Requires the `com.apple.developer.networking.vpn.api` entitlement.
/// Falls back to `false` gracefully when the entitlement is absent (simulator / CI).
public final class NEVPNStatusProvider: VPNStatusProviding, @unchecked Sendable {

    public init() {}

    public var isVPNConnected: Bool {
        let status = NEVPNManager.shared().connection.status
        return status == .connected
    }
}

// MARK: - VPNService

/// Actor-isolated service for VPN status detection and app launch.
///
/// Spec ref:
///   - SPEC.md §29.4: All clients connect over VPN when remote.
///   - SPEC.md §36.3 item 7: VPN auto-connect prompt when off-LAN and disconnected.
public actor VPNService {

    // MARK: - Properties

    private let statusProvider: any VPNStatusProviding
    private let urlOpener: (any URLOpenable)?

    // MARK: - Init

    /// Creates a VPNService with the given status provider and URL opener.
    ///
    /// - Parameters:
    ///   - statusProvider: Source of VPN connection status (default: NEVPNStatusProvider).
    ///   - urlOpener: Used to launch VPN apps via URL scheme (default: nil = system opener).
    public init(
        statusProvider: any VPNStatusProviding = NEVPNStatusProvider(),
        urlOpener: (any URLOpenable)? = nil
    ) {
        self.statusProvider = statusProvider
        self.urlOpener = urlOpener
    }

    // MARK: - Public API

    /// Returns `true` when the VPN is currently connected.
    ///
    /// Delegates to the injected `VPNStatusProviding` implementation.
    /// In production this reads from `NEVPNManager`; in tests it reads from a mock.
    public var isConnected: Bool {
        statusProvider.isVPNConnected
    }

    /// Determines whether the VPN auto-connect prompt should be displayed.
    ///
    /// The prompt is suppressed when:
    /// - The device is already on the local network (LAN), or
    /// - The VPN is already connected.
    ///
    /// Spec ref: SPEC.md §29.4 — on-LAN devices do not need VPN.
    ///
    /// - Parameter isOnLAN: `true` when the device is detected on the home/office LAN.
    /// - Returns: `true` when the user should be prompted to connect to the VPN.
    public func shouldPromptForVPN(isOnLAN: Bool) -> Bool {
        // Never prompt when on LAN — VPN is not required locally.
        guard !isOnLAN else { return false }
        // Never prompt when already connected.
        guard !statusProvider.isVPNConnected else { return false }
        return true
    }

    /// Attempts to launch a VPN client app via its URL scheme.
    ///
    /// Returns `false` (without crashing) when the app is not installed.
    /// Common schemes: `tailscale://`, `wireguard://`.
    ///
    /// Spec ref: Phase iOS10 deliverable 5 — launch Tailscale/WireGuard via URL scheme.
    ///
    /// - Parameter scheme: The URL scheme to open (e.g. `"tailscale://"`).
    /// - Returns: `true` if the app was launched, `false` if not installed or opener unavailable.
    public func launchVPNApp(scheme: String) -> Bool {
        guard let url = URL(string: scheme) else { return false }

        // Use injected opener (tests) or system opener (production).
        if let opener = urlOpener {
            guard opener.canOpenURL(url) else { return false }
            opener.open(url)
            return true
        }

        // Production path: use platform URL opener.
        return launchViaSystem(url: url)
    }

    // MARK: - Private Helpers

    /// Launches a URL via the platform's system URL opener.
    /// Platform-conditional compilation ensures this compiles on both iOS and macOS.
    ///
    /// Returns `false` when the scheme cannot be opened (app not installed or scheme not
    /// in LSApplicationQueriesSchemes). On iOS the canOpenURL check runs synchronously
    /// before dispatching the open call to the main actor.
    private func launchViaSystem(url: URL) -> Bool {
        #if canImport(UIKit)
        // Check canOpenURL on the calling thread (it is thread-safe per Apple docs).
        // Only dispatch `open` to the main actor, which requires an async call. Since
        // actors cannot make this synchronous, we check availability here and return the
        // result immediately; the actual open fires asynchronously on the main actor.
        // This preserves the correct `false` return when the app is not installed.
        final class Box: @unchecked Sendable { var value = false }
        let box = Box()
        let sema = DispatchSemaphore(value: 0)
        Task { @MainActor in
            box.value = UIApplication.shared.canOpenURL(url)
            sema.signal()
        }
        sema.wait()
        guard box.value else { return false }
        Task { @MainActor in
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
        return true
        #elseif canImport(AppKit)
        NSWorkspace.shared.open(url)
        return true
        #else
        return false
        #endif
    }
}
