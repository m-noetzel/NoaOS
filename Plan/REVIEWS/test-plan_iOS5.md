# Test Plan: Phase iOS5

**Date:** 2026-03-09
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md 22.2 (Event Stream), 29.2 (Web UI / Chat with streaming), 29.3 Phase 2 (Native iOS thin client)

## Summary

iOS5 builds the primary chat screen: ChatService (POST /chat with SSE, thread CRUD), ChatViewModel (SSE lifecycle, token accumulation, message state), ThreadListViewModel (thread list loading/creation), and SwiftUI views (ChatView, MessageBubble, ComposerBar, ToolCallCard, ThreadListView, MainTabView). The key testing risks are: (1) SSE token accumulation logic silently dropping or duplicating tokens, (2) ChatViewModel state machine having unreachable or inconsistent states, (3) ChatService not correctly wiring SSEClient for streaming, (4) thread management API calls not matching backend envelope contract, and (5) error states being swallowed rather than surfaced to the UI.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_send_message_creates_sse_stream
- **Spec ref:** SPEC.md 22.2, 29.2 (Chat with streaming SSE)
- **Category:** Behavioral
- **Setup:** ChatViewModel with mock APIClient and mock SSEClient/factory
- **Action:** Call sendMessage("Hello") with no existing threadId
- **Expected:** (1) ChatRequest is sent via POST /api/v1/chat with message="Hello" and threadId=nil, (2) SSE stream is opened, (3) ViewModel state transitions to .streaming, (4) a user message bubble appears in the messages array immediately (optimistic append)
- **Why:** Core chat flow. If message sending does not trigger SSE streaming, the app is non-functional.

#### T2: test_send_message_with_existing_thread
- **Spec ref:** SPEC.md 22.2, ChatModels.ChatRequest
- **Category:** Behavioral
- **Setup:** ChatViewModel with a pre-set threadId (UUID)
- **Action:** Call sendMessage("Follow-up") on existing thread
- **Expected:** ChatRequest includes the existing threadId. SSE stream opens. Message appended to existing messages array.
- **Why:** Continuing a conversation is the primary UX. If threadId is not passed, backend creates a new thread every time.

#### T3: test_token_stream_accumulation
- **Spec ref:** SPEC.md 22.2 token_stream event type
- **Category:** Behavioral
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed a sequence of SSE events: meta, then token_stream with tokens ["Hello", " ", "world", "!"]
- **Expected:** (1) An assistant message appears in messages array, (2) its content progressively accumulates to "Hello world!", (3) each token_stream event appends to the same message (not creating new messages)
- **Why:** Token-by-token accumulation is the core streaming UX. If tokens create separate messages or overwrite each other, the UI is broken.

#### T4: test_result_ready_finalizes_message
- **Spec ref:** SPEC.md 22.2 result_ready event
- **Category:** Behavioral
- **Setup:** ChatViewModel mid-stream with accumulated tokens
- **Action:** Feed result_ready event with payload {"response_text": "Hello world!"}
- **Expected:** (1) The streaming assistant message is finalized with the result_ready content, (2) ViewModel state transitions from .streaming to .idle, (3) the message content matches the response_text from result_ready (not the accumulated tokens, which may be incomplete)
- **Why:** result_ready is the ground truth for the final response. If ignored, partial token accumulation errors persist in the UI.

#### T5: test_error_event_surfaces_error_state
- **Spec ref:** SPEC.md 22.2 error event type
- **Category:** Behavioral / Negative
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed an SSE event with event_type="error", payload={"code": "RATE_LIMITED", "message": "Too many requests"}
- **Expected:** (1) ViewModel transitions to an error state, (2) error is accessible to the view layer (e.g., errorMessage property is set), (3) streaming stops
- **Why:** Silent error swallowing is a recurring anti-pattern (retro RC1). Users must see errors, not a frozen UI.

#### T6: test_meta_event_captures_run_and_thread_ids
- **Spec ref:** SPEC.md 22.2, SSEClient.extractMeta
- **Category:** Behavioral
- **Setup:** ChatViewModel with no threadId set
- **Action:** Feed meta event with payload {"run_id": "<uuid>", "thread_id": "<uuid>"}
- **Expected:** (1) ViewModel captures threadId for subsequent messages, (2) runId is stored for potential run detail navigation
- **Why:** Without capturing threadId from meta, follow-up messages will always create new threads. This was a known SSE integration gap in the web frontend (QC6).

#### T7: test_tool_called_event_creates_tool_card
- **Spec ref:** SPEC.md 22.2 tool_called event, Phase iOS5 deliverable 5
- **Category:** Behavioral
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed tool_called event with payload {"tool_name": "web_search", "args": {"query": "weather"}}
- **Expected:** A tool call indicator appears in the message list or as an inline element, showing the tool name and arguments
- **Why:** Phase deliverable explicitly requires "inline indicators: tool calls, approval requests." If tool events are ignored, the user has no visibility into what the agent is doing.

#### T8: test_approval_requested_event_surfaces_approval_ui
- **Spec ref:** SPEC.md 22.2 approval_requested event, Phase iOS5 deliverable 5
- **Category:** Behavioral
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed approval_requested event with payload {"risk_tier": "high", "preview": "Delete all files in /tmp"}
- **Expected:** (1) An approval request indicator appears in the message flow, (2) it contains the risk tier and preview text, (3) ViewModel state reflects that approval is pending
- **Why:** Approval gating is a security-critical feature (SPEC governance model). If approval requests are invisible, users cannot govern the agent.

#### T9: test_thread_list_loads_threads
- **Spec ref:** SPEC.md 29.2 (thread management), backend GET /api/v1/threads
- **Category:** Behavioral
- **Setup:** ThreadListViewModel with mock APIClient returning [Thread, Thread]
- **Action:** Call loadThreads()
- **Expected:** (1) threads array is populated with 2 Thread objects, (2) loading state transitions: idle -> loading -> loaded, (3) threads are ordered by createdAt descending
- **Why:** Thread list is the navigation entry point. If it fails silently, users see an empty sidebar.

#### T10: test_thread_list_create_thread
- **Spec ref:** Backend POST /api/v1/threads
- **Category:** Behavioral
- **Setup:** ThreadListViewModel with mock APIClient
- **Action:** Call createThread()
- **Expected:** (1) POST /api/v1/threads is called, (2) the new thread is added to the threads array, (3) the new thread is selected (navigated to)
- **Why:** Users must be able to start new conversations. If creation fails silently, users are stuck.

#### T11: test_thread_list_load_failure_shows_error
- **Spec ref:** Phase iOS5, ARCH_INVARIANTS L9
- **Category:** Negative
- **Setup:** ThreadListViewModel with mock APIClient that throws APIError.networkError
- **Action:** Call loadThreads()
- **Expected:** (1) error state is set with actionable message, (2) threads array remains empty (not crashed), (3) state is .error, not .loading forever
- **Why:** Network errors on thread load must surface, not leave the UI in a permanent loading spinner.

#### T12: test_send_message_network_error
- **Spec ref:** Phase iOS5, ARCH_INVARIANTS L9
- **Category:** Negative
- **Setup:** ChatViewModel with mock SSE that throws APIError.networkError immediately
- **Action:** Call sendMessage("test")
- **Expected:** (1) error state is surfaced, (2) the user's message remains visible (not lost), (3) ViewModel returns to idle (not stuck in streaming)
- **Why:** Users will send messages while offline. The message must not vanish, and the UI must not freeze.

#### T13: test_classification_done_event_shows_indicator
- **Spec ref:** SPEC.md 22.2 classification_done, Phase iOS5 deliverable 5
- **Category:** Behavioral
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed classification_done event with payload {"privacy_mode": "private", "confidence": 0.95}
- **Expected:** Privacy/classification indicator appears in the message flow showing "private" mode
- **Why:** Phase deliverable explicitly lists "classification" as an inline indicator.

#### T14: test_step_started_event_shows_progress
- **Spec ref:** SPEC.md 22.2 step_started, Phase iOS5 deliverable 5
- **Category:** Behavioral
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed step_started event with payload {"step_name": "research", "model": "gpt-4"}
- **Expected:** A step progress indicator appears showing the step name
- **Why:** Phase deliverable explicitly lists "step progress" as an inline indicator.

#### T15: test_message_history_loads_on_thread_selection
- **Spec ref:** Backend GET /api/v1/threads/{thread_id}/messages
- **Category:** Behavioral
- **Setup:** ChatViewModel or ChatService with mock APIClient
- **Action:** Load messages for a specific threadId
- **Expected:** (1) GET /api/v1/threads/{id}/messages is called, (2) messages array is populated with historical messages in chronological order, (3) both user and assistant messages are present
- **Why:** Thread selection must show conversation history. Without this, switching threads shows blank chat.

#### T16: test_empty_message_not_sent
- **Spec ref:** Input validation (L11 default-deny)
- **Category:** Negative / Security
- **Setup:** ChatViewModel in idle state
- **Action:** Call sendMessage("") or sendMessage("   ")
- **Expected:** (1) No API call is made, (2) No SSE stream is opened, (3) State remains idle
- **Why:** Empty messages waste server resources and could trigger unexpected backend behavior.

#### T17: test_concurrent_send_prevented
- **Spec ref:** Phase iOS5 (SSE lifecycle management)
- **Category:** Negative / Edge case
- **Setup:** ChatViewModel currently in .streaming state
- **Action:** Call sendMessage("second message") while streaming is active
- **Expected:** (1) Second send is rejected or queued, (2) First stream is not interrupted, (3) No duplicate SSE connections
- **Why:** Double-tap or accidental sends during streaming could create duplicate streams, duplicate messages, or crash the SSE parser.

### NICE-TO-HAVE Tests

#### T18: test_token_stream_with_empty_token
- **Spec ref:** SPEC.md 22.2 token_stream
- **Category:** Edge case
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed token_stream event with payload {"token": "", "position": 0}
- **Expected:** Empty token is handled gracefully (either appended as empty string or skipped), no crash
- **Why:** Backend might emit empty tokens as keepalive or on whitespace boundaries.

#### T19: test_unknown_event_type_ignored_gracefully
- **Spec ref:** Forward compatibility
- **Category:** Edge case
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed event with event_type="new_future_type"
- **Expected:** Event is ignored without crash, streaming continues
- **Why:** Backend may add new event types. SSEEventType already has no default case for unknown strings -- the type property returns nil. ViewModel must handle nil type.

#### T20: test_long_message_rendering
- **Spec ref:** UX robustness
- **Category:** Edge case
- **Setup:** ChatViewModel with messages
- **Action:** Add a message with 10,000+ character content
- **Expected:** No crash, message is stored correctly (view layer truncation is separate)
- **Why:** LLM responses can be very long. ViewModel must not choke on large strings.

#### T21: test_rapid_token_stream_performance
- **Spec ref:** SPEC.md 22.2 token_stream (streaming UX)
- **Category:** Edge case / Performance
- **Setup:** ChatViewModel in streaming state
- **Action:** Feed 500 token_stream events in rapid succession
- **Expected:** All tokens accumulated correctly, no dropped tokens, completes in reasonable time
- **Why:** Fast LLM output can produce many tokens per second. Accumulation must keep up.

#### T22: test_thread_list_empty_state
- **Spec ref:** UX
- **Category:** Edge case
- **Setup:** ThreadListViewModel with mock returning empty array
- **Action:** Call loadThreads()
- **Expected:** threads is empty, state is .loaded (not .error), UI can show empty state
- **Why:** New users have no threads. Empty state should be distinct from error state.

#### T23: test_model_privacy_mode_selector_state
- **Spec ref:** Phase iOS5 deliverable 6 (model/privacy mode selectors in composer)
- **Category:** Behavioral
- **Setup:** ChatViewModel or ComposerBar state
- **Action:** Set privacy mode to .private, then .external
- **Expected:** Selected mode is reflected in subsequent ChatRequest payloads
- **Why:** Phase deliverable explicitly requires model/privacy mode selectors. If they exist in UI but don't affect the request, they are decorative.

## Security Test Requirements

- **T16 (empty message):** Input validation at the client prevents wasted server resources and potential injection.
- **T8 (approval):** Approval requests must be visible -- suppressed approval UI is a governance bypass.
- **T17 (concurrent send):** Prevents duplicate SSE connections that could leak auth tokens or create resource exhaustion.
- **Auth token injection:** ChatService/SSEClient must pass Bearer tokens via TokenProviding (inherited from iOS3/iOS4). Verify ChatService uses the authenticated SSEClient, not a bare URLSession. This is tested implicitly through SSEClient's existing test suite but should be verified in the ChatService init.
- **No hardcoded URLs or tokens** in any new file.

## Integration Test Requirements

At least one test must verify the full ChatViewModel -> ChatService -> SSEClient wiring path without mocking the ViewModel->Service boundary. Specifically:

- **T1 or T3 should use a real ChatService** (with mock APIClient/URLSession underneath) rather than mocking ChatService at the ViewModel level. This catches the "wired in class, not in app" anti-pattern that has recurred in QC5, QC8, and iOS1.
- ThreadListViewModel should call real ChatService.loadThreads() (with mock network), not a mocked service method.

If ALL tests mock the service layer, the ViewModel could have the wrong method signature, wrong parameter types, or wrong return type and tests would still pass. This is the RC1 finding from the project audit retro.

## Anti-Patterns to Watch For

Based on past retros and audit findings:

1. **"Shape not behavior" testing (RC1):** Tests that verify a property exists but not that it changes correctly during the SSE lifecycle. Token accumulation must be tested with a sequence of events, not a single event.

2. **"Wired in class, not in app" (QC5/QC8/iOS1):** ChatService may exist and pass tests, but if MainTabView or the navigation structure does not instantiate ChatViewModel with a real ChatService, the app shows nothing. M7 for iOS means: ChatView is reachable from MainTabView/AuthGuard, with real service injection.

3. **Optimistic append without rollback (QC7):** If sendMessage optimistically adds a user message to the array but the SSE stream fails, does the message stay (misleading) or get removed (correct)? Test T12 must verify this.

4. **SSE Last-Event-ID not passed through ChatService:** SSEClient already handles Last-Event-ID, but does ChatService create the SSEClient correctly and let it reconnect? Or does it create a new SSEClient per message, losing reconnection state?

5. **`try?` swallowing errors:** Watch for `try?` on ChatService API calls that silently eat failures. Every error path must surface to the ViewModel's error state.

6. **ChatRequest missing fields:** Phase deliverable 6 requires model/privacy mode selectors. If ChatRequest does not include these fields, the selectors are decorative. Check that the Encodable model matches what the backend expects.

7. **NavigationSplitView not tested:** Views are hard to unit test, but the wiring from ThreadListView selection -> ChatView(threadId:) must be verifiable. At minimum, verify that selecting a thread in ThreadListViewModel triggers message history loading.

## Test Gate Verification

```bash
# From project root, build and run Swift tests for iOS5:
cd ios/Noa && swift test --filter ChatViewModelTests
cd ios/Noa && swift test --filter ChatServiceTests
cd ios/Noa && swift test --filter ThreadListViewModelTests

# Or via xcodebuild (if xcodeproj exists):
# xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa \
#   -destination 'platform=iOS Simulator,name=iPhone 16' \
#   -only-testing:NaoTests/ChatViewModelTests \
#   -only-testing:NaoTests/ChatServiceTests \
#   -only-testing:NaoTests/ThreadListViewModelTests

# Backend contract tests (Python, if created):
source .venv/bin/activate && python3 -m pytest tests/unit/test_ios5_chat_contract.py -v --override-ini="pythonpath=src"
```

Note: The phase plan references xcodebuild with Noa.xcodeproj, but the current project uses SPM (Package.swift). Use `swift test --filter` unless an xcodeproj is created in this phase. The test target is named `NaoTests` (not `NoaTests` -- known naming inconsistency from iOS3).

## Mandatory Test Count

Phase plan estimates ~14 tests. This test plan specifies 17 MUST-HAVE and 6 NICE-TO-HAVE (23 total). The MUST-HAVE count is higher because the plan's estimate of 14 undercovers the inline indicator events (tool_called, approval_requested, classification_done, step_started) which are explicit phase deliverables and each need at least one test.

Minimum acceptable: all 17 MUST-HAVE tests present and passing. Tests T18-T23 are recommended but non-blocking.
