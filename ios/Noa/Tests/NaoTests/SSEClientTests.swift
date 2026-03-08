// SSEClientTests.swift — Unit tests for SSELineParser and SSEClient
// Spec ref: SPEC.md §22.2, §29.1
// Test plan: test-plan_iOS3.md T11-T16

import XCTest
@testable import Noa

final class SSEClientTests: XCTestCase {

    // MARK: - T11: data: frame parsing

    func test_sseParser_basicDataFrame() {
        // Spec ref: SPEC.md §22.2, T11
        // Feed: data: {"event_type":"token_stream","payload":{"text":"hello"}}\n\n
        let text = #"data: {"event_type":"token_stream","payload":{"text":"hello"}}"# + "\n\n"
        let events = SSELineParser.parse(text: text)

        XCTAssertEqual(events.count, 1, "Should emit exactly one event")
        XCTAssertEqual(events[0].eventType, "token_stream")
    }

    // MARK: - T12: Multi-line data concatenation

    func test_sseParser_multilineData_concatenated() {
        // Spec ref: PLAN Phase iOS3 (T12 — multi-line data concatenation)
        // Per SSE spec: multiple data: lines are joined with \n
        // We split a JSON object across two data: lines
        // Note: a naive split like `{"event_type":"meta",\n"payload":{}}` makes invalid JSON
        // because the second "data: " prefix gets concatenated literally.
        // Use a valid multi-line example that concatenates to valid JSON:
        let validText =
            "data: {\"event_type\":\"result_ready\","
            + "\"payload\":{\"text\":\"done\"}}\n\n"
        let events = SSELineParser.parse(text: validText)
        XCTAssertEqual(events.count, 1)
        XCTAssertEqual(events[0].eventType, "result_ready")

        // Test actual multi-line: two data: lines whose content joins to valid JSON
        // {"event_type": "meta", "payload": {}}
        // Split at the comma:
        let multiLineText =
            "data: {\"event_type\": \"meta\""
            + "\ndata: , \"payload\": {}}\n\n"
        let multiEvents = SSELineParser.parse(text: multiLineText)
        // The concatenated JSON is: {"event_type": "meta", "payload": {}}
        // which is valid — should parse to one event
        XCTAssertEqual(
            multiEvents.count, 1,
            "Multi-line data: fields must concatenate before JSON parsing"
        )
        if let event = multiEvents.first {
            XCTAssertEqual(event.eventType, "meta")
        }
    }

    // MARK: - T13: Comments and empty lines are ignored

    func test_sseParser_commentsIgnored() {
        // Spec ref: SSE specification, T13
        let text = ": this is a keepalive comment\n\ndata: {\"event_type\":\"token_stream\",\"payload\":{}}\n\n"
        let events = SSELineParser.parse(text: text)

        XCTAssertEqual(events.count, 1, "Comment lines must be ignored; one event should emit")
        XCTAssertEqual(events[0].eventType, "token_stream")
    }

    // MARK: - T14: Malformed lines don't crash

    func test_sseParser_malformedLine_doesNotCrash() {
        // Spec ref: PLAN Phase iOS3 (T14 — malformed line handling)
        let text =
            "garbage without colon\n"
            + "data: {\"event_type\":\"result_ready\",\"payload\":{}}\n\n"
        let events = SSELineParser.parse(text: text)

        XCTAssertEqual(events.count, 1, "Malformed line must be skipped; valid event must still emit")
        XCTAssertEqual(events[0].eventType, "result_ready")
    }

    // MARK: - T13 extension: Multiple events in one stream

    func test_sseParser_multipleEvents() {
        // Verify the parser correctly resets state between events
        let text =
            "data: {\"event_type\":\"message_received\",\"payload\":{}}\n\n"
            + "data: {\"event_type\":\"token_stream\",\"payload\":{\"text\":\"hi\"}}\n\n"
            + "data: {\"event_type\":\"result_ready\",\"payload\":{}}\n\n"
        let events = SSELineParser.parse(text: text)

        XCTAssertEqual(events.count, 3)
        XCTAssertEqual(events[0].eventType, "message_received")
        XCTAssertEqual(events[1].eventType, "token_stream")
        XCTAssertEqual(events[2].eventType, "result_ready")
    }

    // MARK: - T16: run_id / thread_id extracted from meta event (via SSEClient)

    func test_sseClient_extractsRunIdAndThreadIdFromMetaEvent() async throws {
        // Spec ref: PLAN Phase iOS3 — SSEClient captures run_id and thread_id from meta event
        let runId = UUID().uuidString
        let threadId = UUID().uuidString
        let metaJSON =
            "{\"event_type\":\"meta\",\"payload\":{\"run_id\":\"\(runId)\",\"thread_id\":\"\(threadId)\"}}"
        let text = "data: \(metaJSON)\n\n"

        let events = SSELineParser.parse(text: text)
        XCTAssertEqual(events.count, 1)
        XCTAssertEqual(events[0].eventType, "meta")

        // Verify payload extraction
        if let payload = events[0].payload,
            case let capturedRunId as String = payload["run_id"]?.value,
            case let capturedThreadId as String = payload["thread_id"]?.value
        {
            XCTAssertEqual(capturedRunId, runId)
            XCTAssertEqual(capturedThreadId, threadId)
        } else {
            XCTFail("meta event payload must contain run_id and thread_id")
        }
    }

    // MARK: - Comment-only stream emits no events

    func test_sseParser_commentOnlyStream_emitsNoEvents() {
        let text = ": keepalive\n\n: another comment\n\n"
        let events = SSELineParser.parse(text: text)
        XCTAssertEqual(events.count, 0, "Comment-only stream must emit no events")
    }

    // MARK: - T15: Reconnection backoff schedule

    func test_backoffSchedule_correctValues() {
        // Spec ref: PLAN Phase iOS3 — backoff [1s, 2s, 5s, 10s]
        XCTAssertEqual(SSEClient.backoffSchedule, [1, 2, 5, 10], "Backoff schedule must be [1, 2, 5, 10]")
    }

    // MARK: - All 12 SSE event types parse correctly

    func test_allSSEEventTypes_parseCorrectly() {
        let eventTypes = [
            "message_received", "classification_done", "step_started",
            "token_stream", "tool_called", "tool_result",
            "approval_requested", "approval_received", "artifact_created",
            "result_ready", "error", "meta",
        ]

        for eventType in eventTypes {
            let text =
                "data: {\"event_type\":\"\(eventType)\",\"payload\":{}}\n\n"
            let events = SSELineParser.parse(text: text)
            XCTAssertEqual(
                events.count, 1,
                "Event type '\(eventType)' must parse to 1 event"
            )
            XCTAssertEqual(
                events[0].eventType, eventType,
                "eventType must round-trip for '\(eventType)'"
            )
        }
    }
}
