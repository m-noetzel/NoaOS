// OV10Tests.swift — iOS SSE Sync + Chat Parameters (Phase OV10)
// Spec ref: SPEC.md §22.2, §6.2
//
// Tests:
//   1. SSEEventType parsing for new event types (tool_start, tool_end, compaction, queued)
//   2. ChatRequest encoding with temperature and maxTokens — snake_case keys present
//   3. ChatRequest encoding without temperature and maxTokens — keys omitted from JSON
//   4. ChatRequest encoding roundtrip — decode preserves values

import Testing
import Foundation
@testable import Noa

// MARK: - OV10: New SSEEventType cases

@Suite("OV10: New SSEEventType cases")
struct OV10SSEEventTypeTests {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    @Test("tool_start parses to .toolStart")
    func test_toolStart_parsesCorrectly() {
        let parsed = SSEEventType(rawValue: "tool_start")
        #expect(parsed == .toolStart)
    }

    @Test("tool_end parses to .toolEnd")
    func test_toolEnd_parsesCorrectly() {
        let parsed = SSEEventType(rawValue: "tool_end")
        #expect(parsed == .toolEnd)
    }

    @Test("compaction parses to .compaction")
    func test_compaction_parsesCorrectly() {
        let parsed = SSEEventType(rawValue: "compaction")
        #expect(parsed == .compaction)
    }

    @Test("queued parses to .queued")
    func test_queued_parsesCorrectly() {
        let parsed = SSEEventType(rawValue: "queued")
        #expect(parsed == .queued)
    }

    @Test("all 16 backend SSEEventType raw values are valid")
    func test_allSixteenEventTypes_areValid() {
        let allRawValues = [
            "message_received",
            "classification_done",
            "step_started",
            "token_stream",
            "tool_called",
            "tool_result",
            "tool_start",
            "tool_end",
            "approval_requested",
            "approval_received",
            "artifact_created",
            "result_ready",
            "compaction",
            "queued",
            "error",
            "meta",
        ]
        for raw in allRawValues {
            let parsed = SSEEventType(rawValue: raw)
            #expect(parsed != nil, "'\(raw)' must be a valid SSEEventType case")
        }
    }

    @Test("SSEEvent.type resolves tool_start and tool_end from wire format")
    func test_sseEvent_newTypes_resolveFromWireFormat() throws {
        let json = """
            {
                "event_type": "tool_start",
                "payload": {"tool_name": "web_search", "tool_use_id": "tu-abc"}
            }
            """
        let event = try decoder.decode(SSEEvent.self, from: json.data(using: .utf8)!)
        #expect(event.type == .toolStart)
        #expect(event.payload?["tool_name"]?.value as? String == "web_search")
    }

    @Test("SSEEvent.type resolves queued from wire format")
    func test_sseEvent_queued_resolveFromWireFormat() throws {
        let json = """
            {
                "event_type": "queued",
                "payload": {"message": "Private worker unavailable; request queued."}
            }
            """
        let event = try decoder.decode(SSEEvent.self, from: json.data(using: .utf8)!)
        #expect(event.type == .queued)
    }

    @Test("SSEEvent.type resolves compaction from wire format")
    func test_sseEvent_compaction_resolveFromWireFormat() throws {
        let json = """
            {
                "event_type": "compaction",
                "payload": {"tokens_before": 80000, "tokens_after": 12000}
            }
            """
        let event = try decoder.decode(SSEEvent.self, from: json.data(using: .utf8)!)
        #expect(event.type == .compaction)
    }
}

// MARK: - OV10: ChatRequest temperature and maxTokens encoding

@Suite("OV10: ChatRequest temperature and maxTokens")
struct OV10ChatRequestTests {

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        return e
    }()

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    // Helper: encode ChatRequest and return the parsed JSON dict.
    private func encodeToDict(_ req: ChatRequest) throws -> [String: Any] {
        let data = try encoder.encode(req)
        let obj = try JSONSerialization.jsonObject(with: data)
        guard let dict = obj as? [String: Any] else {
            Issue.record("Expected JSON object")
            return [:]
        }
        return dict
    }

    @Test("temperature encodes as snake_case key with correct Float value")
    func test_temperature_encodesWithSnakeCaseKey() throws {
        let req = ChatRequest(message: "hello", temperature: 0.7)
        let dict = try encodeToDict(req)
        // Encoded value may be Double in the JSON dict
        let value = dict["temperature"] as? Double ?? dict["temperature"] as? Float.RawSignificand as? Double
        // Use a simple cast approach since JSON deserialization gives Double
        if let d = dict["temperature"] as? Double {
            #expect(abs(d - 0.7) < 0.01, "temperature must be ~0.7, got \(d)")
        } else {
            Issue.record("temperature key missing or wrong type in encoded JSON: \(dict)")
        }
        // Verify camelCase key is NOT present
        #expect(dict["maxTokens"] == nil, "maxTokens camelCase key must not appear")
    }

    @Test("maxTokens encodes as max_tokens snake_case key")
    func test_maxTokens_encodesAsSnakeCaseKey() throws {
        let req = ChatRequest(message: "hello", maxTokens: 4096)
        let dict = try encodeToDict(req)
        let value = dict["max_tokens"] as? Int
        #expect(value == 4096, "max_tokens must be 4096, got \(String(describing: dict["max_tokens"]))")
        // Verify camelCase key is NOT present
        #expect(dict["maxTokens"] == nil, "maxTokens camelCase key must not appear")
    }

    @Test("temperature and maxTokens together encode correctly")
    func test_temperature_and_maxTokens_encodeTogether() throws {
        let req = ChatRequest(
            message: "test",
            privacyMode: "external",
            temperature: 1.0,
            maxTokens: 8192
        )
        let dict = try encodeToDict(req)
        if let t = dict["temperature"] as? Double {
            #expect(abs(t - 1.0) < 0.01)
        } else {
            Issue.record("temperature key missing")
        }
        let mt = dict["max_tokens"] as? Int
        #expect(mt == 8192)
        #expect(dict["privacy_mode"] as? String == "external")
    }

    @Test("nil temperature omits temperature key from JSON")
    func test_nilTemperature_omitsKeyFromJSON() throws {
        let req = ChatRequest(message: "hello", temperature: nil)
        let dict = try encodeToDict(req)
        // JSONEncoder omits nil optionals by default — the key must not appear
        #expect(dict["temperature"] == nil, "nil temperature must be omitted from encoded JSON")
    }

    @Test("nil maxTokens omits max_tokens key from JSON")
    func test_nilMaxTokens_omitsKeyFromJSON() throws {
        let req = ChatRequest(message: "hello", maxTokens: nil)
        let dict = try encodeToDict(req)
        #expect(dict["max_tokens"] == nil, "nil maxTokens must be omitted from encoded JSON")
    }

    @Test("default ChatRequest omits temperature and max_tokens")
    func test_defaultRequest_omitsBothOptionalFields() throws {
        let req = ChatRequest(message: "hello")
        let dict = try encodeToDict(req)
        #expect(dict["temperature"] == nil)
        #expect(dict["max_tokens"] == nil)
        // Required fields must still be present
        #expect(dict["message"] as? String == "hello")
        #expect(dict["privacy_mode"] as? String == "private")
    }

    @Test("ChatRequest with all fields encodes all fields")
    func test_fullRequest_encodesAllFields() throws {
        let threadId = UUID()
        let req = ChatRequest(
            message: "full test",
            threadId: threadId,
            privacyMode: "external",
            provider: "openai",
            model: "gpt-4o",
            temperature: 0.5,
            maxTokens: 2048
        )
        let dict = try encodeToDict(req)
        #expect(dict["message"] as? String == "full test")
        #expect(dict["thread_id"] as? String == threadId.uuidString.lowercased()
            || dict["thread_id"] as? String == threadId.uuidString)
        #expect(dict["privacy_mode"] as? String == "external")
        #expect(dict["provider"] as? String == "openai")
        #expect(dict["model"] as? String == "gpt-4o")
        let mt = dict["max_tokens"] as? Int
        #expect(mt == 2048)
        if let t = dict["temperature"] as? Double {
            #expect(abs(t - 0.5) < 0.01)
        } else {
            Issue.record("temperature key missing or wrong type")
        }
    }

    @Test("ChatRequest temperature boundary: 0.0 and 2.0 encode correctly")
    func test_temperature_boundaryValues() throws {
        let minReq = ChatRequest(message: "min", temperature: 0.0)
        let maxReq = ChatRequest(message: "max", temperature: 2.0)

        let minDict = try encodeToDict(minReq)
        let maxDict = try encodeToDict(maxReq)

        if let t = minDict["temperature"] as? Double {
            #expect(abs(t - 0.0) < 0.001)
        } else {
            Issue.record("min temperature not found")
        }
        if let t = maxDict["temperature"] as? Double {
            #expect(abs(t - 2.0) < 0.001)
        } else {
            Issue.record("max temperature not found")
        }
    }

    @Test("ChatRequest maxTokens boundary: 256 and 16384 encode correctly")
    func test_maxTokens_boundaryValues() throws {
        let minReq = ChatRequest(message: "min", maxTokens: 256)
        let maxReq = ChatRequest(message: "max", maxTokens: 16384)

        let minDict = try encodeToDict(minReq)
        let maxDict = try encodeToDict(maxReq)

        #expect(minDict["max_tokens"] as? Int == 256)
        #expect(maxDict["max_tokens"] as? Int == 16384)
    }
}
