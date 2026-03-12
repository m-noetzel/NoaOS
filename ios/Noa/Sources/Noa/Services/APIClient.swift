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
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            let frac = ISO8601DateFormatter()
            frac.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = frac.date(from: string) {
                return date
            }
            let basic = ISO8601DateFormatter()
            basic.formatOptions = [.withInternetDateTime]
            if let date = basic.date(from: string) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid date: \(string)")
        }
        return d
    }()

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()

    /// HTTP methods that require an Idempotency-Key header per §25.4.
    private static let writeMethods: Set<String> = ["POST", "PUT", "PATCH"]

    private let networkMonitor: (any NetworkMonitoring)?
    private let offlineQueue: (any OfflineQueuing)?

    /// Called when a 401 cannot be recovered by token refresh.
    /// Typically set to `authViewModel.handleUnauthorized` by the app composition root.
    /// iOS-H3: allows the auth layer to react to unrecoverable auth failures at runtime.
    private var onUnauthorized: (@Sendable () -> Void)?

    // MARK: - Init

    public init(
        environment: NoaEnvironment = .current,
        tokenProvider: any TokenProviding,
        session: URLSession? = nil,
        networkMonitor: (any NetworkMonitoring)? = nil,
        offlineQueue: (any OfflineQueuing)? = nil,
        onUnauthorized: (@Sendable () -> Void)? = nil
    ) {
        self.baseURL = environment.baseURL
        self.tokenProvider = tokenProvider
        self.networkMonitor = networkMonitor
        self.offlineQueue = offlineQueue
        self.onUnauthorized = onUnauthorized
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

    /// Returns true if the current token provider has a non-nil access token.
    /// Used by DeviceService (and similar) to guard API calls when unauthenticated.
    public func isAuthenticated() async -> Bool {
        let token = await tokenProvider.accessToken()
        return token != nil
    }

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
        // Offline guard: if a write request arrives while disconnected, queue it.
        // Spec ref: SPEC.md §29.3 item 6
        if let monitor = networkMonitor, let queue = offlineQueue {
            let connected = await monitor.isConnected
            let isWrite = Self.writeMethods.contains(method.uppercased())
            if !connected && isWrite {
                let bodyData = body.flatMap { try? Self.encoder.encode(AnyEncodable($0)) }
                // Allocate a stable idempotency key for this queued entry
                let key = UUID().uuidString
                let queued = QueuedRequest(
                    endpoint: endpoint,
                    method: method,
                    bodyData: bodyData,
                    idempotencyKey: key
                )
                await queue.enqueue(queued)
                throw APIError.queued(id: key)
            }
        }

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
                // Refresh failed — session is unrecoverable. Notify the auth layer
                // so AuthGuard can transition to the login screen. iOS-H3.
                onUnauthorized?()
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
            // If still 401 after one refresh, session is unrecoverable. iOS-H3.
            if retryHTTP.statusCode == 401 {
                onUnauthorized?()
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

    // MARK: - Offline queue replay

    /// Replays a `QueuedRequest` that was enqueued while the device was offline.
    ///
    /// The pre-serialised body bytes are injected directly as `httpBody` — no
    /// double-encoding occurs. The response is discarded; callers only care whether
    /// the request succeeds or throws.
    ///
    /// - Parameter request: A previously-queued write request.
    /// - Throws: `APIError` on network or server failure.
    public func replayRequest(_ request: QueuedRequest) async throws {
        let token = await tokenProvider.accessToken()
        let url = baseURL.appendingPathComponent(request.endpoint)
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = request.method
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token {
            urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        // Reuse the idempotency key that was assigned at enqueue time (§25.4).
        urlRequest.setValue(request.id, forHTTPHeaderField: "Idempotency-Key")
        urlRequest.httpBody = request.bodyData

        let (_, response): (Data, URLResponse)
        do {
            (_, response) = try await session.data(for: urlRequest)
        } catch let urlError as URLError {
            throw APIError.networkError(underlying: urlError)
        } catch {
            throw APIError.networkError(underlying: error)
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError.networkError(underlying: URLError(.badServerResponse))
        }

        switch http.statusCode {
        case 200...299:
            return  // success — caller dequeues the item
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        case 429:
            let retryAfter = http.value(forHTTPHeaderField: "Retry-After")
                .flatMap { TimeInterval($0) }
            throw APIError.rateLimited(retryAfter: retryAfter)
        default:
            throw APIError.unknown(statusCode: http.statusCode)
        }
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
