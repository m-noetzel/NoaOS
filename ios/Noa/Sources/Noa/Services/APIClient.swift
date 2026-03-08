// APIClient.swift — Async HTTP client
// Spec ref: SPEC.md §25.3, §25.4, §29.3
//
// Responsibilities:
//   - Generic request<T> with ApiResponse<T> envelope decoding
//   - Authorization: Bearer <token> injection
//   - Idempotency-Key UUID header on POST/PUT/PATCH
//   - 401: refresh once, retry once, then throw .unauthorized
//   - 429: throw .rateLimited(retryAfter:)
//   - 30s timeout

import Foundation

/// Thread-safe HTTP client using Swift `actor` isolation.
/// Spec ref: SPEC.md §25.3, §25.4
public actor APIClient: APIClientProtocol {

    // MARK: - Properties

    private let baseURL: URL
    private let session: URLSession
    private let tokenProvider: any TokenProviding

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()

    /// HTTP methods that require an Idempotency-Key header per §25.4.
    private static let writeMethods: Set<String> = ["POST", "PUT", "PATCH"]

    // MARK: - Init

    public init(
        environment: NoaEnvironment = .current,
        tokenProvider: any TokenProviding,
        session: URLSession? = nil
    ) {
        self.baseURL = environment.baseURL
        self.tokenProvider = tokenProvider
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 30
            config.timeoutIntervalForResource = 30
            self.session = URLSession(configuration: config)
        }
    }

    // MARK: - APIClientProtocol

    /// Performs an HTTP request and decodes the `ApiResponse<T>` envelope.
    ///
    /// - Parameters:
    ///   - endpoint: Path relative to baseURL (e.g. "/api/v1/threads").
    ///   - method: HTTP method ("GET", "POST", etc.).
    ///   - body: Optional Encodable body; encoded as JSON. Ignored on GET.
    /// - Returns: The decoded `T` from the response `.data` field.
    /// - Throws: `APIError` typed errors.
    public func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        let token = await tokenProvider.accessToken()
        let request = try buildRequest(endpoint: endpoint, method: method, body: body, token: token)

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw APIError.networkError(underlying: urlError)
        } catch {
            throw APIError.networkError(underlying: error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(
                underlying: URLError(.badServerResponse)
            )
        }

        // 401: refresh token once and retry once (no infinite loop — §29.3)
        if httpResponse.statusCode == 401 {
            let newToken: String
            do {
                newToken = try await tokenProvider.refreshAccessToken()
            } catch {
                throw APIError.unauthorized
            }
            let retryRequest = try buildRequest(
                endpoint: endpoint, method: method, body: body, token: newToken
            )
            let (retryData, retryResponse): (Data, URLResponse)
            do {
                (retryData, retryResponse) = try await session.data(for: retryRequest)
            } catch let urlError as URLError {
                throw APIError.networkError(underlying: urlError)
            } catch {
                throw APIError.networkError(underlying: error)
            }
            guard let retryHTTP = retryResponse as? HTTPURLResponse else {
                throw APIError.networkError(underlying: URLError(.badServerResponse))
            }
            // If still 401 after one refresh, surface the error — do NOT retry again.
            if retryHTTP.statusCode == 401 {
                throw APIError.unauthorized
            }
            return try decode(T.self, from: retryData, statusCode: retryHTTP.statusCode, headers: retryHTTP)
        }

        // 429: rate limited
        if httpResponse.statusCode == 429 {
            let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After")
                .flatMap { TimeInterval($0) }
            throw APIError.rateLimited(retryAfter: retryAfter)
        }

        return try decode(T.self, from: data, statusCode: httpResponse.statusCode, headers: httpResponse)
    }

    // MARK: - Private helpers

    private func buildRequest(
        endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?,
        token: String?
    ) throws -> URLRequest {
        let url = baseURL.appendingPathComponent(endpoint)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        // Auth header injection — §29.3
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Idempotency-Key on write requests — §25.4
        if Self.writeMethods.contains(method.uppercased()) {
            request.setValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")
        }

        if let body, method.uppercased() != "GET" {
            request.httpBody = try Self.encoder.encode(AnyEncodable(body))
        }

        return request
    }

    private func decode<T: Decodable>(
        _ type: T.Type,
        from data: Data,
        statusCode: Int,
        headers: HTTPURLResponse
    ) throws -> T {
        // Try to decode the envelope first
        if let envelope = try? Self.decoder.decode(ApiResponse<T>.self, from: data) {
            if envelope.ok, let payload = envelope.data {
                return payload
            } else if let apiError = envelope.error {
                switch statusCode {
                case 401:
                    throw APIError.unauthorized
                case 403:
                    throw APIError.forbidden
                case 404:
                    throw APIError.notFound
                default:
                    throw APIError.serverError(
                        code: apiError.code,
                        message: apiError.message
                    )
                }
            }
        }

        // Handle non-envelope error responses
        switch statusCode {
        case 200...299:
            // Non-envelope success (e.g., raw T)
            do {
                return try Self.decoder.decode(T.self, from: data)
            } catch {
                throw APIError.decodingError(underlying: error)
            }
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        default:
            throw APIError.unknown(statusCode: statusCode)
        }
    }
}

// MARK: - AnyEncodable

/// Type-erasing Encodable wrapper so we can pass `any Encodable` to `JSONEncoder`.
private struct AnyEncodable: Encodable {
    private let encodeFunc: (Encoder) throws -> Void

    init(_ base: any Encodable) {
        self.encodeFunc = base.encode
    }

    func encode(to encoder: Encoder) throws {
        try encodeFunc(encoder)
    }
}
