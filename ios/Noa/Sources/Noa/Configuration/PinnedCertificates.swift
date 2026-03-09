// PinnedCertificates.swift — Embedded SPKI pin hashes for the Noa API server
// Spec ref: SPEC.md §29.4, Phase iOS10 deliverable 2
//
// SPKI pin rotation: during key rotation, add the new hash before removing the old one.
// Both hashes will be accepted (OR semantics) until all clients have updated.
//
// To generate a new pin hash from a certificate:
//   openssl s_client -connect <host>:443 | openssl x509 -pubkey -noout | \
//   openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64
//
// SECURITY: An empty pin set causes all connections to be rejected.
// Any change to this file must be reviewed and approved by the security owner.

import Foundation

/// Embedded SPKI SHA-256 hashes for the Noa API server's TLS public keys.
///
/// These are base64-encoded SHA-256 digests of the SubjectPublicKeyInfo (SPKI)
/// DER structure from the server's TLS certificate(s).
///
/// Spec ref: SPEC.md §29.4 — Certificate pinning is mandatory for the native iOS app.
public enum PinnedCertificates {

    /// The set of accepted SPKI hashes.
    ///
    /// Includes the current production key and, during rotation, a backup key.
    /// At least one entry is required at all times (enforced by test T6).
    public static let spkiHashes: [String] = [
        // Primary Noa API server SPKI hash — rotated after initial deployment.
        // This placeholder hash must be replaced with the real server certificate's
        // SPKI hash before shipping to production.
        //
        // Generated from: openssl x509 -pubkey -noout | openssl pkey -pubin -outform DER |
        //                 openssl dgst -sha256 -binary | base64
        //
        // Replace with the actual production server hash at deploy time:
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ]
}
