// CertificatePinningDelegate.swift — URLSessionDelegate with SPKI certificate pinning
// Spec ref: SPEC.md §29.4 (Connection Security), Phase iOS10 deliverable 1
//
// Responsibilities:
//   - Validate server certificates via SHA-256 SubjectPublicKeyInfo (SPKI) hash pinning
//   - Accept connections only when at least one pinned hash matches the server leaf cert (OR semantics)
//   - Reject connections when trust evaluation fails (self-signed, expired, chain error)
//   - Expose `evaluatePinning(spkiHash:trustEvaluationPassed:)` as a testable entry point
//
// SPKI hash generation (must match what this code computes):
//   openssl s_client -connect <host>:443 | openssl x509 -pubkey -noout | \
//   openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64

import Foundation
import Security
import CryptoKit

// MARK: - CertificatePinningDelegate

/// URLSessionDelegate implementing public-key (SPKI) certificate pinning.
///
/// For each server trust challenge, the delegate:
/// 1. Evaluates the OS-level certificate trust chain.
/// 2. Extracts the leaf certificate's SubjectPublicKeyInfo (SPKI) DER bytes.
/// 3. Computes SHA-256 of the full SPKI DER and base64-encodes the result.
/// 4. Accepts the connection iff the computed hash matches ANY pinned hash (OR semantics).
///
/// SPKI DER = AlgorithmIdentifier header + BIT STRING wrapping raw key bytes.
/// The header bytes are key-type-specific and prepended before hashing.
/// This matches what `openssl pkey -pubin -outform DER | openssl dgst -sha256` produces.
///
/// Spec ref: SPEC.md §29.4
// NSObject is immutable-after-init; Sendable conformance is safe because
// `pinnedSPKIHashes` is a `let Set<String>` (value type, inherently Sendable).
public final class CertificatePinningDelegate: NSObject, URLSessionDelegate, Sendable {

    // MARK: - SPKI AlgorithmIdentifier Headers
    //
    // These byte sequences are the DER-encoded AlgorithmIdentifier + BIT STRING wrapper
    // that precede the raw public key bytes in a SubjectPublicKeyInfo structure.
    // They are prepended to `SecKeyCopyExternalRepresentation` output before hashing,
    // producing a digest that matches `openssl pkey -pubin -outform DER | sha256`.

    /// SPKI header for EC P-256 (secp256r1) keys — 26 bytes.
    /// AlgorithmIdentifier: ecPublicKey (1.2.840.10045.2.1) + prime256v1 (1.2.840.10045.3.1.7)
    private static let ecP256SPKIHeader: [UInt8] = [
        0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86,
        0x48, 0xce, 0x3d, 0x02, 0x01, 0x06, 0x08, 0x2a,
        0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03,
        0x42, 0x00,
    ]

    /// SPKI header for RSA-2048 keys — 24 bytes.
    /// AlgorithmIdentifier: rsaEncryption (1.2.840.113549.1.1.1) + NULL
    private static let rsa2048SPKIHeader: [UInt8] = [
        0x30, 0x82, 0x01, 0x22, 0x30, 0x0d, 0x06, 0x09,
        0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01,
        0x01, 0x05, 0x00, 0x03, 0x82, 0x01, 0x0f, 0x00,
    ]

    /// SPKI header for RSA-4096 keys — 24 bytes.
    private static let rsa4096SPKIHeader: [UInt8] = [
        0x30, 0x82, 0x02, 0x22, 0x30, 0x0d, 0x06, 0x09,
        0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01,
        0x01, 0x05, 0x00, 0x03, 0x82, 0x02, 0x0f, 0x00,
    ]

    // MARK: - Properties

    /// The set of accepted SPKI SHA-256 hashes (base64-encoded).
    /// At least one must match the server's leaf certificate for the connection to proceed.
    private let pinnedSPKIHashes: Set<String>

    // MARK: - Init

    /// Creates a pinning delegate with the given set of accepted SPKI hashes.
    ///
    /// - Parameter pinnedSPKIHashes: Base64-encoded SHA-256 digests of accepted SPKI DER structures.
    ///   If this set is empty, all connections are rejected (default-deny).
    public init(pinnedSPKIHashes: [String]) {
        self.pinnedSPKIHashes = Set(pinnedSPKIHashes)
        super.init()
    }

    // MARK: - URLSessionDelegate

    public func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        // Only handle server trust challenges; defer others to default handling.
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust
        else {
            completionHandler(.performDefaultHandling, nil)
            return
        }

        // Step 1: Evaluate OS-level trust chain (catches expired, self-signed, chain errors).
        var cfError: CFError?
        let trustIsValid = SecTrustEvaluateWithError(serverTrust, &cfError)
        if let error = cfError {
            // Log trust evaluation errors for incident response (no private data in CFError).
            NSLog("[CertificatePinning] Trust evaluation error: %@", String(describing: error))
        }

        // Step 2: Extract leaf certificate and compute its SPKI hash.
        let leafCertOpt: SecCertificate?
        if #available(iOS 15.0, macOS 12.0, *) {
            leafCertOpt = (SecTrustCopyCertificateChain(serverTrust) as? [SecCertificate])?.first
        } else {
            leafCertOpt = SecTrustGetCertificateAtIndex(serverTrust, 0)
        }
        guard let leafCert = leafCertOpt,
              let spkiHash = CertificatePinningDelegate.spkiHash(for: leafCert)
        else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Step 3: Evaluate pinning — if accepted, provide the server trust credential.
        if evaluatePinning(spkiHash: spkiHash, trustEvaluationPassed: trustIsValid) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    // MARK: - Testable Entry Point

    /// Evaluates pinning given a pre-computed SPKI hash and a trust result.
    ///
    /// Exposed for unit testing: tests call this directly with a synthetic hash and trust result,
    /// bypassing the need for real TLS infrastructure.
    ///
    /// - Parameters:
    ///   - spkiHash: Base64-encoded SHA-256 hash of the server certificate's SPKI DER.
    ///   - trustEvaluationPassed: Whether the OS trust chain evaluation succeeded.
    /// - Returns: `true` if the connection should be allowed, `false` to cancel.
    public func evaluatePinning(spkiHash: String, trustEvaluationPassed: Bool) -> Bool {
        // Reject if trust evaluation failed (self-signed, expired, chain error).
        guard trustEvaluationPassed else { return false }
        // Reject if the hash is not in the pinned set (OR semantics: any match is enough).
        // Empty pin set = default deny (all connections rejected).
        return pinnedSPKIHashes.contains(spkiHash)
    }

    // MARK: - Private Helpers

    /// Computes the SHA-256 hash of the SubjectPublicKeyInfo (SPKI) DER bytes for the given certificate.
    ///
    /// SPKI DER = AlgorithmIdentifier header bytes + raw key bytes from SecKeyCopyExternalRepresentation.
    /// The header bytes are key-type-specific (EC P-256, RSA-2048, RSA-4096).
    /// This produces the same digest as: `openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64`
    ///
    /// SPKI pinning survives certificate renewals when the same key pair is reused.
    ///
    /// - Parameter certificate: The SecCertificate to hash.
    /// - Returns: Base64-encoded SHA-256 digest of the SPKI DER, or nil if extraction fails.
    static func spkiHash(for certificate: SecCertificate) -> String? {
        guard let publicKey = SecCertificateCopyKey(certificate) else { return nil }

        // Get the key attributes to determine the key type and size.
        guard let attributes = SecKeyCopyAttributes(publicKey) as? [CFString: Any],
              let keyType = attributes[kSecAttrKeyType] as? String,
              let keySize = attributes[kSecAttrKeySizeInBits] as? Int
        else { return nil }

        // Extract raw key bytes.
        var cfKeyError: Unmanaged<CFError>?
        guard let rawKeyData = SecKeyCopyExternalRepresentation(publicKey, &cfKeyError) as Data? else {
            return nil
        }

        // Select the SPKI AlgorithmIdentifier header matching the key type and size.
        // CFString constants bridge to Swift String; compare via == after casting.
        let ecType = kSecAttrKeyTypeECSECPrimeRandom as String
        let rsaType = kSecAttrKeyTypeRSA as String
        let header: [UInt8]
        switch (keyType, keySize) {
        case (ecType, 256):
            header = ecP256SPKIHeader
        case (rsaType, 2048):
            header = rsa2048SPKIHeader
        case (rsaType, 4096):
            header = rsa4096SPKIHeader
        default:
            // Unknown key type — cannot construct SPKI header, reject to stay secure.
            return nil
        }

        // Construct SPKI DER = header + raw key bytes, then SHA-256 hash it.
        var spkiDER = Data(header)
        spkiDER.append(rawKeyData)
        let digest = SHA256.hash(data: spkiDER)
        return Data(digest).base64EncodedString()
    }
}
