# Test Plan: Phase iOS10

**Date:** 2026-03-09
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md §29.4, §36.3 item 7

## Summary

iOS10 adds certificate pinning (SPKI) to all API connections and VPN status detection with an auto-connect prompt. The key testing risks are: (1) pinning must reject invalid certificates without any bypass, (2) ALL four URLSession creation sites must use the pinning delegate (not just APIClient), (3) VPN detection relies on NEVPNManager which requires a protocol abstraction for testability, and (4) pin rotation must work without an app update or must be handled carefully to avoid bricking the app.

## Critical Observation: Four URLSession Sites

The codebase currently creates URLSession instances in FOUR locations:

1. `APIClient.swift:61` — `URLSession(configuration: config)`
2. `SSEClient.swift:53` — `URLSession(configuration: config)`
3. `VoiceService.swift:123` — `URLSession(configuration: config)`
4. `ChatService.swift:71` — `URLSession(configuration: config)`

The phase plan says "APIClient uses pinning delegate for all sessions" but if only APIClient is modified, the other three are MITM-vulnerable. The test plan must verify ALL session creation paths use pinning.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_valid_certificate_accepted
- **Spec ref:** SPEC.md §29.4 — "Certificate pinning on the native iOS app to prevent MITM"
- **Category:** Behavioral
- **Setup:** CertificatePinningDelegate configured with a known SPKI hash. URLAuthenticationChallenge with a server trust whose leaf certificate matches the pinned hash.
- **Action:** Call `urlSession(_:didReceive:completionHandler:)` with the matching challenge.
- **Expected:** Completion handler called with `.useCredential` and the server trust credential. No error thrown.
- **Why:** If valid certs are rejected, the app cannot connect at all.

#### T2: test_invalid_certificate_rejected
- **Spec ref:** SPEC.md §29.4
- **Category:** Behavioral / Security
- **Setup:** CertificatePinningDelegate with pin hash A. Challenge with a certificate whose SPKI hash is B (does not match).
- **Action:** Call the delegate method with the non-matching challenge.
- **Expected:** Completion handler called with `.cancelAuthenticationChallenge`. Connection must fail. No fallback to system trust store.
- **Why:** This IS the MITM protection. If a mismatched cert is accepted, pinning is theater.

#### T3: test_self_signed_certificate_rejected
- **Spec ref:** SPEC.md §29.4
- **Category:** Security
- **Setup:** CertificatePinningDelegate with production pin hashes. Challenge with a self-signed certificate not in the pin set.
- **Action:** Call the delegate method.
- **Expected:** `.cancelAuthenticationChallenge`. Must NOT fall back to system trust evaluation.
- **Why:** Self-signed certs are the primary MITM attack vector on local networks.

#### T4: test_expired_certificate_rejected
- **Spec ref:** SPEC.md §29.4
- **Category:** Security
- **Setup:** Challenge with a certificate that matches the SPKI pin but is expired (if the implementation checks expiry in addition to pin match).
- **Action:** Call the delegate method.
- **Expected:** Either rejected (if expiry is checked alongside pin) OR accepted (SPKI pinning is hash-based, expiry is orthogonal). The developer must document which behavior is chosen and the test must match. If accepted, add a comment explaining why SPKI pinning does not check expiry.
- **Why:** Clarifies the security model. SPKI pins survive certificate renewals (same key pair), so accepting expired-but-pin-matched certs is actually correct behavior for SPKI pinning.

#### T5: test_multi_pin_rotation_accepts_any_matching_pin
- **Spec ref:** Phase plan deliverable 2 — "Pin hashes embedded in app bundle, configurable for rotation"
- **Category:** Behavioral
- **Setup:** PinnedCertificates contains [hash_old, hash_new]. Challenge with a certificate matching hash_new only.
- **Action:** Call the delegate method.
- **Expected:** `.useCredential` — any single match in the pin set is sufficient.
- **Why:** Pin rotation requires deploying a new pin BEFORE rotating the server certificate. If only the first pin is checked, rotation breaks connectivity.

#### T6: test_empty_pin_set_rejects_all
- **Spec ref:** ARCH_INVARIANTS.md L11 — "Default-deny on permissions"
- **Category:** Security / Invariant
- **Setup:** PinnedCertificates with an empty pin array (misconfiguration scenario).
- **Action:** Call the delegate method with any certificate.
- **Expected:** `.cancelAuthenticationChallenge` or a preconditionFailure/fatal error at init time. Must NOT accept all connections when pins are empty. The default-deny principle requires that no pins = no trust.
- **Why:** An empty pin set that accepts everything is a silent security bypass. This is the "unsafe fallback default" anti-pattern (L11).

#### T7: test_non_server_trust_challenge_passed_through
- **Spec ref:** Implementation correctness
- **Category:** Behavioral
- **Setup:** URLAuthenticationChallenge with protection space type != NSURLAuthenticationMethodServerTrust (e.g., HTTP Basic auth).
- **Action:** Call the delegate method.
- **Expected:** `.performDefaultHandling` — pinning delegate only handles server trust challenges. Other challenge types are passed through to default handling.
- **Why:** If ALL challenges are canceled (not just server trust), HTTP auth and client certificates break.

#### T8: test_all_session_creation_uses_pinning_delegate
- **Spec ref:** SPEC.md §29.4 — "Certificate pinning on the native iOS app"
- **Category:** Integration / Invariant
- **Setup:** Grep or source-inspect all URLSession instantiations in `Sources/Noa/`.
- **Action:** For each URLSession init call, verify it passes a delegate that is (or wraps) CertificatePinningDelegate. Alternatively, verify a factory/shared session is used.
- **Expected:** ALL four sites (APIClient, SSEClient, VoiceService, ChatService) use pinned sessions. Zero unpinned URLSession instances in production code.
- **Why:** If only APIClient is pinned, SSE streaming and voice uploads are MITM-vulnerable. This is the most likely implementation gap (phase plan only mentions APIClient).

#### T9: test_vpn_status_connected
- **Spec ref:** §36.3 item 7 — "VPN auto-connect"
- **Category:** Behavioral
- **Setup:** VPNService with a mock NEVPNManager (via protocol) that reports `.connected` status.
- **Action:** Query VPN status.
- **Expected:** Returns a connected/active state. No auto-connect prompt shown.
- **Why:** When VPN is connected, the banner must not appear.

#### T10: test_vpn_status_disconnected_off_lan_shows_prompt
- **Spec ref:** Phase plan deliverable 4 — "Auto-connect prompt when off-LAN and VPN disconnected"
- **Category:** Behavioral
- **Setup:** VPN status = `.disconnected`. Network = not on local LAN (e.g., cellular or unknown Wi-Fi).
- **Action:** Evaluate whether to show the VPN banner.
- **Expected:** Banner/prompt is shown to the user, offering to connect via Tailscale or WireGuard.
- **Why:** Core deliverable: user must be prompted when they're remote and unprotected.

#### T11: test_vpn_disconnected_on_lan_skips_prompt
- **Spec ref:** Phase plan test list — "on-LAN skip"
- **Category:** Behavioral
- **Setup:** VPN status = `.disconnected`. Network = on LAN (home network detection — by SSID, gateway IP, or similar heuristic).
- **Action:** Evaluate whether to show the VPN banner.
- **Expected:** Banner is NOT shown. On LAN, the connection to Noa API is direct and secure.
- **Why:** Nagging users to connect VPN when they're already on the home network is wrong UX and indicates incorrect LAN detection logic.

#### T12: test_vpn_url_scheme_launch_tailscale
- **Spec ref:** Phase plan deliverable 5 — "Launch Tailscale/WireGuard via URL scheme"
- **Category:** Behavioral
- **Setup:** Mock URL opener (via protocol abstraction over UIApplication.open).
- **Action:** Call the VPN connect action with provider = Tailscale.
- **Expected:** Attempts to open the Tailscale URL scheme (e.g., `tailscale://`). If mock reports can't open, falls back gracefully (e.g., App Store link or error message).
- **Why:** If the URL scheme is wrong or missing, the "Connect VPN" button does nothing.

### NICE-TO-HAVE Tests

#### T13: test_vpn_url_scheme_launch_wireguard
- **Spec ref:** Phase plan deliverable 5
- **Category:** Behavioral
- **Setup:** Same as T12 but for WireGuard.
- **Action:** Call connect with provider = WireGuard.
- **Expected:** Opens WireGuard URL scheme (e.g., `wireguard://`).
- **Why:** Second VPN provider support.

#### T14: test_pinned_certificates_configuration_is_not_empty
- **Spec ref:** ARCH_INVARIANTS.md L11
- **Category:** Invariant
- **Setup:** None.
- **Action:** Access `PinnedCertificates.spkiHashes` (or equivalent).
- **Expected:** The array is non-empty. Contains at least one valid base64-encoded SHA-256 hash.
- **Why:** Ships with empty pins = no pinning. A compile-time or test-time check prevents this.

#### T15: test_vpn_status_change_notification
- **Spec ref:** Implementation correctness
- **Category:** Behavioral
- **Setup:** VPNService observing NEVPNManager status changes (via NotificationCenter or similar).
- **Action:** Simulate status change from `.connected` to `.disconnected`.
- **Expected:** VPNService publishes the new status. Observing views update accordingly.
- **Why:** If status changes aren't observed, the banner appears/disappears only on app launch.

#### T16: test_certificate_pinning_delegate_thread_safety
- **Spec ref:** Swift 6 strict concurrency
- **Category:** Invariant
- **Setup:** CertificatePinningDelegate must be Sendable or an actor.
- **Action:** Verify Sendable conformance compiles. If it's a class, check for `@unchecked Sendable` with justification.
- **Expected:** Compiles under Swift 6 strict concurrency without warnings.
- **Why:** URLSessionDelegate methods are called on arbitrary threads. Non-Sendable delegates cause data races.

#### T17: test_vpn_service_protocol_abstraction
- **Spec ref:** L8 — "No network calls in unit tests"
- **Category:** Integration
- **Setup:** VPNService should accept a protocol for NEVPNManager (since NEVPNManager requires a Network Extension entitlement and doesn't work in test targets).
- **Action:** Instantiate VPNService with a mock conforming to the protocol.
- **Expected:** All operations work without requiring the real NEVPNManager.
- **Why:** Without a protocol abstraction, VPNService is untestable in unit tests.

#### T18: test_pinning_delegate_receives_challenge_from_real_session
- **Spec ref:** Wiring correctness
- **Category:** Integration
- **Setup:** Create a URLSession with the CertificatePinningDelegate. Make a request to a known HTTPS endpoint (e.g., via URLProtocol mock that triggers a server trust challenge).
- **Action:** Perform a data task.
- **Expected:** The delegate's `didReceive challenge` method is called. Verifies the delegate is correctly wired to the session (not silently ignored).
- **Why:** URLSession silently ignores delegates that don't implement the right method signatures. A typo in the method name = no pinning.

## Security Test Requirements

1. **No pinning bypass in DEBUG mode.** Grep the implementation for `#if DEBUG` inside the pinning delegate. If pinning is disabled in debug builds, document it but flag as a security concern — a debug build leaked to production would have no MITM protection.

2. **No `SecTrustEvaluateWithError` fallback.** After SPKI hash comparison fails, the delegate must NOT fall back to system trust evaluation (which would accept any CA-signed certificate, defeating pinning).

3. **Pin hash format validation.** SPKI hashes should be base64-encoded SHA-256. If the format is wrong (e.g., hex instead of base64, SHA-1 instead of SHA-256), the comparison silently fails and all certs are rejected (denial of service) or a weak hash allows collision attacks.

4. **VPN status does not gate API calls.** The VPN banner is informational. If VPNService.isConnected returns false, API calls must NOT be blocked. The user might be on LAN. Only certificate pinning provides security — VPN detection is UX only.

## Integration Test Requirements

- **T8 is the critical integration test.** It verifies that the pinning delegate is actually used across all networking paths. This must NOT be a source-inspection test (those are weak per project retro RC1). Instead, create sessions the same way production code does and verify the delegate is set.

- **T18** provides a second integration layer: verifying the delegate method is actually invoked by URLSession, not just set on the session object.

## Anti-Patterns to Watch For

Based on past retros and the project audit:

1. **"Wired in class, not used" (QC8 pattern):** CertificatePinningDelegate exists and is created, but never passed to URLSession as a delegate. The session ignores it. Verify: `URLSession(configuration:delegate:delegateQueue:)` is called with the pinning delegate, not just `URLSession(configuration:)`.

2. **"Partial fix" (iOS1 pattern):** Only APIClient gets the pinning delegate, SSEClient/VoiceService/ChatService are left unpinned. The phase plan specifically says "APIClient uses pinning delegate" which might be interpreted as "only APIClient." All four must be covered.

3. **`#if DEBUG` bypass:** Developers often disable pinning in debug mode for convenience. This must be documented and tested separately.

4. **Source-inspection tests (retro RC1):** Tests that grep for `CertificatePinningDelegate` in source code prove nothing about runtime behavior. T8 must instantiate real objects and check the delegate, not read source files.

5. **`try?` on security-critical paths (iOS5 lesson):** If certificate validation uses `try?` anywhere, validation errors are silently swallowed and the connection proceeds. The pinning delegate must use `try` (throwing) or explicit error handling, never `try?`.

6. **Orphaned VPNService (QC5/QC8 pattern):** VPNService is created but never connected to a view or view model. The VPNStatusBanner must actually read from VPNService, not hardcode a state.

7. **NEVPNManager without protocol abstraction:** NEVPNManager requires Network Extensions entitlement. If VPNService uses it directly without a protocol wrapper, all tests that import VPNService will fail in the test target. The iOS7 BiometricService pattern (BiometricAuthenticating protocol) should be followed.
