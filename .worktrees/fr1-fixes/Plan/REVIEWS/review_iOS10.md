# QA Review: Phase iOS10

**Date:** 2026-03-09
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 13 tests have docstrings citing SPEC.md ss29.4, ss36.3, or phase plan deliverables |
| M2 | Negative Tests | PASS | T2 (invalid hash rejected), T3 (self-signed rejected), T4 (expired rejected), T10 (scheme unavailable), T6 (empty pin set check) |
| M3 | Security Boundaries | PASS | No hardcoded secrets. Placeholder SPKI hash is intentional and documented. Default-deny on empty pin set. Trust chain evaluated before hash check. No DEBUG bypass in pinning delegate. |
| M4 | Determinism | PASS | No wall-clock time, no network calls, no unseeded randomness. All tests use mock providers and deterministic hashes. |
| M5 | Implementation Completeness | PASS | All 5 files created per phase plan. Deliverable 6 ("APIClient uses pinning delegate for all sessions") explicitly deferred to iOS11 per user attestation -- acceptable since this is a library package with no app target yet. |
| M6 | No Silent Error Swallowing | PASS | No bare except blocks (Swift). No `try?` in security-critical paths. CertificatePinningDelegate logs CFError via NSLog before rejecting. Unknown key type returns nil (reject path). |
| M7 | Wiring Completeness | PASS | For a library package without an app target, M7 is assessed as: components are importable and instantiable. VPNService and CertificatePinningDelegate accept protocol-injected dependencies for testability. Production wiring deferred to iOS11 (acceptable). |
| M8 | Domain Isolation | PASS | N/A for pure iOS package. No cross-domain imports. |
| S1 | Error Handling & Boundaries | PASS | Empty pin set rejects all (default-deny). Invalid URL scheme returns false. Non-server-trust challenges fall through to default handling. |
| S2 | Code Consistency | PASS | Follows existing codebase patterns: actor for VPNService, protocol abstraction for testability (VPNStatusProviding/URLOpenable pattern matches BiometricAuthenticating from iOS7), Sendable conformance throughout. |
| S3 | Migration & Rollback | PASS | N/A -- no database changes. |
| S4 | Documentation | PASS | Excellent inline documentation. SPKI header bytes documented with OID references. openssl command documented for pin hash generation. Pin rotation documented in PinnedCertificates.swift. |
| S5 | Integration Smoke Test | OPEN | T7 manually injects CertificatePinningDelegate into a URLSession and runs an APIClient request. However, it does not verify that production APIClient code uses the pinning delegate (it does not). The test plan's critical T8 (all session creation uses pinning) has no corresponding test. |

## Test Plan Coverage

The implementation covers 11 of 12 MUST-HAVE test plan items (T1-T7, T9-T12). Missing from the test plan:

- **T8 (all session creation uses pinning delegate)**: NOT TESTED and NOT IMPLEMENTED. All four URLSession creation sites (`APIClient.swift:61`, `SSEClient.swift:53`, `VoiceService.swift:123`, `ChatService.swift:71`) still use `URLSession(configuration: config)` without any delegate. The developer explicitly deferred this to iOS11 and communicated it. This is the most important integration gap in this phase, but acceptable given the library-only context.

- **T7 (non-server-trust challenge passed through)**: Not explicitly tested, but `evaluatePinning()` is the testable entry point and only handles SPKI hash comparison. The `urlSession(_:didReceive:completionHandler:)` method handles the `performDefaultHandling` fallback for non-server-trust challenges, which is not unit-testable without real URLSession infrastructure. Acceptable.

The implementation adds 2 tests beyond the test plan: T12 (VPN prompt shown when off-LAN and disconnected) and T13 (VPN prompt suppressed when already connected). Good coverage additions.

## Spec Compliance

| Requirement | Status | Detail |
|---|---|---|
| SPEC.md ss29.4: Certificate pinning on native iOS app | Partially implemented | CertificatePinningDelegate is correct and well-tested. Not yet wired into production URLSessions (deferred to iOS11). |
| SPEC.md ss29.4: SPKI public key pinning | Implemented | SHA-256 of full SPKI DER (AlgorithmIdentifier header + raw key bytes). Supports EC P-256, RSA-2048, RSA-4096. |
| SPEC.md ss36.3 item 7: VPN auto-connect | Implemented | VPNService detects status, shouldPromptForVPN logic handles on-LAN/off-LAN/connected correctly. |
| Phase plan deliverable 2: Pin hashes in bundle | Implemented | PinnedCertificates.swift with placeholder hash. OR semantics for rotation. |
| Phase plan deliverable 5: URL scheme launch | Implemented | launchVPNApp with protocol-abstracted URL opener. canOpenURL check before open. |
| Phase plan deliverable 6: APIClient uses pinning delegate | Deferred | Explicitly deferred to iOS11 per developer. |

## Test Coverage

| Test | Maps to | Spec ref |
|---|---|---|
| test_validPinHash_allowsConnection | T1 | ss29.4 |
| test_invalidPinHash_rejectsConnection | T2 | ss29.4 |
| test_selfSignedCertificate_isRejected | T3 | ss29.4 |
| test_expiredCertificate_isRejected | T4 | ss29.4 |
| test_multiPin_atLeastOneMatch_allowsConnection | T5 | Deliverable 2 |
| test_pinnedCertificates_containsAtLeastOneHash | T6/T14 | L11 |
| test_apiClient_pinningFailure_surfacesTypedError | T7 | ss29.4 |
| test_vpnService_isConnected_returnsWithoutCrashing | T8 (test plan T9) | ss36.3 |
| test_vpnService_disconnectedStatus_isFalse | T9 (test plan T9) | ss29.4 |
| test_launchVPNApp_returnsFalse_whenSchemeUnavailable | T10 (test plan T12) | Deliverable 5 |
| test_vpnPrompt_suppressed_whenOnLAN | T11 (test plan T11) | ss29.4 |
| test_vpnPrompt_shown_whenOffLANAndDisconnected | T12 (test plan T10) | ss36.3 |
| test_vpnPrompt_suppressed_whenAlreadyConnected | T13 | ss29.4 |

Gap: Test plan T8 (all session creation uses pinning delegate) has no test. This is the highest-risk untested item.

## Anti-Pattern Scan Results

**M6: Silent error swallowing**
- No `try?` in CertificatePinningDelegate.swift or VPNService.swift
- No bare `except`/`catch` blocks that swallow errors
- `spkiHash(for:)` returns `nil` on failure (triggers rejection path, not acceptance) -- correct default-deny behavior

**M7: Wiring completeness**
- `CertificatePinningDelegate` is NOT referenced by any URLSession creation in production code (confirmed via grep for `CertificatePinning` in Sources/Noa: only found in its own file)
- `VPNStatusBanner` is NOT used in any view
- `VPNService` is NOT referenced by any ViewModel
- All three are orphaned components. Wiring is deferred to iOS11.

**M8: Domain isolation**
- N/A for iOS package. No cross-domain imports.

**`#if DEBUG` bypass check:**
- No `#if DEBUG` in CertificatePinningDelegate.swift. Pinning is never disabled in debug mode. Correct.

**URLSession audit (all 4 creation sites):**
```
APIClient.swift:61     — URLSession(configuration: config) — NO delegate
SSEClient.swift:53     — URLSession(configuration: config) — NO delegate
VoiceService.swift:123 — URLSession(configuration: config) — NO delegate
ChatService.swift:71   — URLSession(configuration: config) — NO delegate
```
All four remain unpinned. This is the deferred deliverable 6.

## Smoke Test Results

`swift test` completed with 139/139 tests passing (127 XCTest + 12 swift-testing). 13 new tests from iOS10 (7 CertificatePinningTests + 6 VPNServiceTests).

All iOS10 types compile and are instantiable in the test target. No import errors, no crashes.

## Security

**Certificate Pinning Implementation -- CORRECT:**
1. Trust chain evaluation (`SecTrustEvaluateWithError`) runs BEFORE hash comparison -- self-signed and expired certs are rejected even if hash matches. This is the correct order.
2. SPKI hash includes the full AlgorithmIdentifier header, not just raw key bytes. This matches `openssl pkey -pubin -outform DER | sha256` output. Correct.
3. Empty pin set rejects all connections (default-deny per L11). Correct.
4. No `#if DEBUG` bypass in pinning delegate. Correct.
5. No fallback to system trust evaluation after hash mismatch. Correct.
6. Multiple pin hashes use OR semantics (any match accepts). Correct for pin rotation.

**NEVPNStatusProvider `@unchecked Sendable`:**
- The class has no mutable stored properties. `isVPNConnected` is a computed property. The `@unchecked` is needed because `NEVPNManager` is not declared Sendable by Apple. This is acceptable.

**Placeholder SPKI hash:**
- `PinnedCertificates.spkiHashes` contains `"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="` -- a placeholder. This MUST be replaced before production deployment. The comment documents this clearly. T6 would catch removal (empty set) but NOT catch an unchanged placeholder. A deploy-time check should verify the hash against the actual server certificate.

**No hardcoded secrets.** No API keys, no tokens.

## Code Quality

**Good:**
- Clean separation of concerns: CertificatePinningDelegate (security), PinnedCertificates (config), VPNService (detection/launch), VPNStatusBanner (UI)
- Protocol abstractions (VPNStatusProviding, URLOpenable) enable testability without entitlements
- SPKI header bytes are documented with OID references and size comments
- Sendable conformance is correct throughout

**Concern -- DispatchSemaphore in actor:**
- `VPNService.launchViaSystem(url:)` (line 139-164) uses `DispatchSemaphore` to synchronously wait for a `@MainActor` task. This blocks a cooperative thread pool thread while waiting for the MainActor. If the MainActor is busy (e.g., processing UI events) and the cooperative pool is saturated, this could theoretically deadlock. In practice this is unlikely for a single call, but it is an anti-pattern for Swift concurrency. The code comment acknowledges the tradeoff. This is acceptable for now but should be refactored in iOS11 to use `async` properly.

**Minor: `@unchecked Sendable` on NEVPNStatusProvider.**
- Justified (no mutable state, NEVPNManager not Sendable in Apple SDK). Acceptable.

## Beyond the Test Plan

1. **T8 test is absent -- this was the test plan's highest-priority integration test.** The test plan specifically warned: "If only APIClient is pinned, SSE streaming and voice uploads are MITM-vulnerable." Currently NONE of the four session sites are pinned. The implementation is internally correct (CertificatePinningDelegate works perfectly) but externally disconnected (nothing uses it). This is the "wired in class, not used" anti-pattern (test plan anti-pattern #1). Acceptable ONLY because production wiring is explicitly deferred to iOS11.

2. **VPNService.launchViaSystem DispatchSemaphore deadlock risk.** Not in the test plan. The semaphore blocks a cooperative executor thread while waiting for MainActor dispatch. This is a latent issue that won't manifest in unit tests (which use the mock URLOpenable path, bypassing launchViaSystem entirely).

3. **PinnedCertificates placeholder hash passes T6.** T6 checks "at least one non-empty hash" which the placeholder satisfies. There is no test that validates the hash is actually correct for the production server. This is acceptable pre-deployment but creates a risk: the app could ship with pinning that rejects all real connections (because the hash doesn't match any server cert). A pre-release integration test should validate this.

4. **NEVPNStatusProvider reads NEVPNManager on actor thread.** NEVPNManager.shared() may trigger internal synchronization. Reading `.connection.status` on a cooperative thread is potentially blocking. Noted by developer as "latent, not causing failures."

## Notes (PASS_WITH_NOTES)

1. **[IMPORTANT] Deliverable 6 deferred:** CertificatePinningDelegate is not wired into any production URLSession. All 4 session creation sites (APIClient, SSEClient, VoiceService, ChatService) remain unpinned. iOS11 MUST wire this or certificate pinning provides zero runtime protection. File paths: `Sources/Noa/Services/APIClient.swift:61`, `Sources/Noa/Services/SSEClient.swift:53`, `Sources/Noa/Services/VoiceService.swift:123`, `Sources/Noa/Services/ChatService.swift:71`.

2. **[IMPORTANT] VPNStatusBanner and VPNService are orphaned.** Neither is referenced from any view or ViewModel. iOS11 must compose these into the app. Files: `Sources/Noa/Views/Shared/VPNStatusBanner.swift`, `Sources/Noa/Services/VPNService.swift`.

3. **DispatchSemaphore in actor context.** `VPNService.launchViaSystem(url:)` at line 147 blocks a cooperative thread with `sema.wait()`. Refactor to `async` in iOS11 or later. Low risk in practice but violates Swift concurrency best practices.

4. **Placeholder SPKI hash.** `PinnedCertificates.spkiHashes` contains a placeholder that must be replaced before deployment. Add a pre-release check (CI or manual) to validate the hash against the actual server certificate.

5. **No test for non-server-trust challenge fallback.** The `performDefaultHandling` path in the delegate (line 96) is untested. Low risk -- the code is straightforward.

## Decision Review

The phase delivers correct, well-tested certificate pinning logic and VPN status detection. The CertificatePinningDelegate's SPKI implementation (including AlgorithmIdentifier headers) is cryptographically sound. The trust-before-hash evaluation order is correct. Default-deny on empty pins is correct.

The main gap is that none of this is wired into the production networking stack. This is explicitly deferred to iOS11. For a library package with no app target, this is acceptable. The verdict would be FAIL if this were a phase that required a running application, but as the second-to-last phase before iOS11 (integration), it is PASS_WITH_NOTES with strong emphasis on note #1.

Test count: 139 total (127 XCTest + 12 swift-testing), 13 new from iOS10.
