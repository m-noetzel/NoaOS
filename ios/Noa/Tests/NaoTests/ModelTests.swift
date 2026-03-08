// ModelTests.swift — Codable roundtrip tests for all model types
// Spec ref: SPEC.md §25.3, §22.1, §22.2, §29.6, §10.1
// Test plan: test-plan_iOS3.md T17-T21, T28, T29, T31

import XCTest
@testable import Noa

final class ModelTests: XCTestCase {

    private let iso8601 = "2026-03-08T10:00:00+00:00"

    private var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }

    private var encoder: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }

    // MARK: - T17: ApiResponse success envelope

    func test_apiResponse_successEnvelope_decodesCorrectly() throws {
        // Spec ref: SPEC.md §25.3, T17
        let json = """
            {
                "ok": true,
                "data": {"id": "abc-123", "name": "test"},
                "error": null,
                "trace_id": "trace-xyz-001"
            }
            """
        let data = json.data(using: .utf8)!
        let response = try decoder.decode(ApiResponse<SimpleModel>.self, from: data)

        XCTAssertTrue(response.ok)
        XCTAssertEqual(response.data?.id, "abc-123")
        XCTAssertEqual(response.data?.name, "test")
        XCTAssertNil(response.error)
        XCTAssertEqual(response.traceId, "trace-xyz-001")
    }

    // MARK: - T18: ApiResponse error envelope

    func test_apiResponse_errorEnvelope_decodesCorrectly() throws {
        // Spec ref: SPEC.md §25.3, T18
        let json = """
            {
                "ok": false,
                "data": null,
                "error": {"code": "AUTH_TOKEN_EXPIRED", "message": "Access token has expired"},
                "trace_id": "trace-err-001"
            }
            """
        let data = json.data(using: .utf8)!
        let response = try decoder.decode(ApiResponse<SimpleModel>.self, from: data)

        XCTAssertFalse(response.ok)
        XCTAssertNil(response.data)
        XCTAssertEqual(response.error?.code, "AUTH_TOKEN_EXPIRED")
        XCTAssertFalse(response.error?.message.isEmpty ?? true)
    }

    // MARK: - T19: Thread model decoding

    func test_thread_decodesFromBackendJSON() throws {
        // Spec ref: SPEC.md §10.1, T19
        let threadId = UUID().uuidString
        let userId = UUID().uuidString
        let json = """
            {
                "id": "\(threadId)",
                "user_id": "\(userId)",
                "title": "My Thread",
                "created_at": "\(iso8601)"
            }
            """
        let data = json.data(using: .utf8)!
        let thread = try decoder.decode(Thread.self, from: data)

        XCTAssertEqual(thread.id.uuidString.lowercased(), threadId.lowercased())
        XCTAssertEqual(thread.userId.uuidString.lowercased(), userId.lowercased())
        XCTAssertEqual(thread.title, "My Thread")
        XCTAssertNotNil(thread.createdAt)
    }

    func test_thread_nullTitle_decodesCorrectly() throws {
        // Spec ref: §10.1 — title may be null
        let json = """
            {
                "id": "\(UUID().uuidString)",
                "user_id": "\(UUID().uuidString)",
                "title": null,
                "created_at": "\(iso8601)"
            }
            """
        let thread = try decoder.decode(Thread.self, from: json.data(using: .utf8)!)
        XCTAssertNil(thread.title)
    }

    // MARK: - T20: RunEvent model decoding

    func test_runEvent_decodesFromBackendJSON() throws {
        // Spec ref: SPEC.md §22.2, T20
        let eventId = UUID().uuidString
        let runId = UUID().uuidString
        let json = """
            {
                "id": "\(eventId)",
                "run_id": "\(runId)",
                "event_type": "token_stream",
                "timestamp": "\(iso8601)",
                "payload": {"text": "Hello world"}
            }
            """
        let data = json.data(using: .utf8)!
        let event = try decoder.decode(RunEvent.self, from: data)

        XCTAssertEqual(event.id.uuidString.lowercased(), eventId.lowercased())
        XCTAssertEqual(event.runId.uuidString.lowercased(), runId.lowercased())
        XCTAssertEqual(event.eventType, "token_stream")
        XCTAssertEqual(event.type, SSEEventType.tokenStream)
        XCTAssertNotNil(event.payload["text"])
    }

    func test_runEvent_unknownEventType_doesNotCrash() throws {
        // T28 variant: unknown event_type is stored as raw string, type is nil
        let json = """
            {
                "id": "\(UUID().uuidString)",
                "run_id": "\(UUID().uuidString)",
                "event_type": "future_event_type_not_yet_known",
                "timestamp": "\(iso8601)",
                "payload": {}
            }
            """
        let event = try decoder.decode(RunEvent.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(event.eventType, "future_event_type_not_yet_known")
        XCTAssertNil(event.type, "Unknown event types must map to nil (not crash)")
    }

    // MARK: - T21: Approval model decoding

    func test_approval_decodesFromBackendJSON() throws {
        // Spec ref: SPEC.md §29.6, T21
        let approvalId = UUID().uuidString
        let runId = UUID().uuidString
        let userId = UUID().uuidString
        let json = """
            {
                "id": "\(approvalId)",
                "run_id": "\(runId)",
                "user_id": "\(userId)",
                "risk_tier": "medium",
                "preview_text": "Send email to alice@example.com",
                "decision": "pending",
                "domain": "external",
                "requested_at": "\(iso8601)",
                "decided_at": null
            }
            """
        let data = json.data(using: .utf8)!
        let approval = try decoder.decode(Approval.self, from: data)

        XCTAssertEqual(approval.riskTier, .medium)
        XCTAssertEqual(approval.decision, .pending)
        XCTAssertEqual(approval.previewText, "Send email to alice@example.com")
        XCTAssertNil(approval.decidedAt)
    }

    func test_approval_nullPreviewText_decodesCorrectly() throws {
        // Spec ref: §29.6 — preview_text may be null
        let json = """
            {
                "id": "\(UUID().uuidString)",
                "run_id": "\(UUID().uuidString)",
                "user_id": "\(UUID().uuidString)",
                "risk_tier": "high",
                "preview_text": null,
                "decision": "approved",
                "domain": "external",
                "requested_at": "\(iso8601)",
                "decided_at": null
            }
            """
        let approval = try decoder.decode(Approval.self, from: json.data(using: .utf8)!)
        XCTAssertNil(approval.previewText)
        XCTAssertEqual(approval.decision, .approved)
        XCTAssertEqual(approval.riskTier, .high)
    }

    // MARK: - Run model decoding

    func test_run_decodesFromBackendJSON() throws {
        // Spec ref: SPEC.md §22.1
        let runId = UUID().uuidString
        let threadId = UUID().uuidString
        let userId = UUID().uuidString
        let json = """
            {
                "id": "\(runId)",
                "thread_id": "\(threadId)",
                "user_id": "\(userId)",
                "status": "running",
                "risk_tier": "low",
                "privacy_mode": "private",
                "summary": null,
                "created_at": "\(iso8601)",
                "updated_at": "\(iso8601)"
            }
            """
        let run = try decoder.decode(Run.self, from: json.data(using: .utf8)!)

        XCTAssertEqual(run.id.uuidString.lowercased(), runId.lowercased())
        XCTAssertEqual(run.status, .running)
        XCTAssertEqual(run.riskTier, .low)
        XCTAssertEqual(run.privacyMode, .private)
        XCTAssertNil(run.summary)
    }

    // MARK: - T28: Unknown enum values don't crash

    func test_riskTier_unknownValue_mapsToUnknown() throws {
        // T28: Forward compatibility — new backend enum values must not crash old app versions
        let json = """
            {
                "id": "\(UUID().uuidString)",
                "run_id": "\(UUID().uuidString)",
                "user_id": "\(UUID().uuidString)",
                "risk_tier": "ULTRA_HIGH",
                "preview_text": null,
                "decision": "pending",
                "domain": "external",
                "requested_at": "\(iso8601)",
                "decided_at": null
            }
            """
        let approval = try decoder.decode(Approval.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(approval.riskTier, .unknown, "Unknown risk_tier must map to .unknown, not crash")
    }

    // MARK: - T31: Message roles

    func test_message_allRoles_decodeCorrectly() throws {
        // T31: All message roles must decode to distinct enum values
        let roles: [(String, MessageRole)] = [
            ("user", .user),
            ("assistant", .assistant),
            ("system", .system),
            ("tool", .tool),
        ]

        for (roleStr, expectedRole) in roles {
            let json = """
                {
                    "id": "\(UUID().uuidString)",
                    "thread_id": "\(UUID().uuidString)",
                    "role": "\(roleStr)",
                    "content": "test content",
                    "created_at": "\(iso8601)"
                }
                """
            let message = try decoder.decode(Message.self, from: json.data(using: .utf8)!)
            XCTAssertEqual(message.role, expectedRole, "Role '\(roleStr)' must decode to \(expectedRole)")
        }
    }

    // MARK: - AuthTokens decoding

    func test_authTokens_decodesFromBackendJSON() throws {
        let json = """
            {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4",
                "token_type": "bearer",
                "expires_in": 3600
            }
            """
        let tokens = try decoder.decode(AuthTokens.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(tokens.tokenType, "bearer")
        XCTAssertEqual(tokens.expiresIn, 3600)
        XCTAssertFalse(tokens.accessToken.isEmpty)
        XCTAssertFalse(tokens.refreshToken.isEmpty)
    }

    // MARK: - T29: Extra JSON fields are ignored

    func test_thread_extraFields_areIgnored() throws {
        // T29: Forward compatibility — extra fields from backend API evolution must be ignored
        let json = """
            {
                "id": "\(UUID().uuidString)",
                "user_id": "\(UUID().uuidString)",
                "title": "Test Thread",
                "created_at": "\(iso8601)",
                "future_field": "this should be ignored",
                "another_new_field": 42
            }
            """
        // Swift's Codable ignores extra keys by default — this must not throw
        let thread = try decoder.decode(Thread.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(thread.title, "Test Thread")
    }

    // MARK: - SSEEvent decoding

    func test_sseEvent_decodesFromWireFormat() throws {
        let json = """
            {
                "event_type": "approval_requested",
                "payload": {
                    "approval_id": "abc-123",
                    "risk_tier": "high"
                }
            }
            """
        let event = try decoder.decode(SSEEvent.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(event.eventType, "approval_requested")
        XCTAssertEqual(event.type, .approvalRequested)
        XCTAssertNotNil(event.payload?["approval_id"])
    }

    // MARK: - ApprovalDecision encoding

    func test_approvalDecision_encodesCorrectly() throws {
        let decision = ApprovalDecision(decision: .approved)
        let data = try encoder.encode(decision)
        let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(dict?["decision"] as? String, "approved")
    }

    // MARK: - RunStatus values

    func test_runStatus_allValuesDecodeCorrectly() throws {
        let statuses: [(String, RunStatus)] = [
            ("pending", .pending),
            ("running", .running),
            ("awaiting_approval", .awaitingApproval),
            ("completed", .completed),
            ("failed", .failed),
            ("cancelled", .cancelled),
        ]

        for (raw, expected) in statuses {
            let json = "\"" + raw + "\""
            let status = try decoder.decode(RunStatus.self, from: json.data(using: .utf8)!)
            XCTAssertEqual(status, expected, "Status '\(raw)' must decode to \(expected)")
        }
    }
}

// Note: SimpleModel is defined in APIClientTests.swift and is visible here
// because both are in the same test target (NaoTests).
