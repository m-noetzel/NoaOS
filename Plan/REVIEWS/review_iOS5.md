# QA Review: Phase iOS5

**Date:** 2026-03-09
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 3/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | **FAIL** | Zero Swift tests for iOS5. 32 Python contract tests exist but no ChatViewModel/ChatService/ThreadListViewModel test files. All 60 Swift tests are from iOS3/iOS4. |
| M2 | Negative Tests | **FAIL** | No Swift negative tests at all. Python contract tests are shape-only (no error paths). |
| M3 | Security Boundaries | PASS | No hardcoded secrets/URLs. ChatService uses TokenProviding for auth injection. No cross-domain imports. |
| M4 | Determinism | PASS | No wall-clock, network, or random dependencies in contract tests. |
| M5 | Implementation Completeness | **FAIL** | Two contract mismatches between ChatViewModel and backend payload field names. See blocking issues B1, B2. |
| M6 | No Silent Error Swallowing | **FAIL** | `try?` on SSE event decoding in ChatService.swift:93 silently drops unparseable events. `try?` on logout in MainTabView.swift:63 is acceptable (best-effort). |
| M7 | Wiring Completeness | PASS | threads router wired in app.py. MainTabView is public and compilable. Library package has no app entry point (consistent with iOS3/iOS4). |
| M8 | Domain Isolation | N/A | Pure iOS client package -- no backend domain imports. |
| S1 | Error Handling & Boundaries | PASS | Optimistic append with rollback on failure. Error banners in ChatView. Loading/error states in ThreadListView. |
| S2 | Code Consistency | PASS | Follows established patterns from iOS3/iOS4: actor services, @Observable ViewModels, @MainActor. |
| S3 | Migration & Rollback | N/A | No DB schema changes (delete endpoint is a stub). |
| S4 | Documentation | PASS | Spec refs in file headers. Type annotations throughout. |
| S5 | Integration Smoke Test | OPEN | Backend smoke passes. Swift builds clean. But no Swift tests exercise the ViewModel-to-Service wiring at all. |

## Test Plan Coverage

The test plan specified 17 MUST-HAVE and 6 NICE-TO-HAVE Swift-side tests. **Zero** of the MUST-HAVE Swift tests are present. The 32 Python contract tests cover backend schema shapes but do not test any Swift behavior (SSE lifecycle, token accumulation, optimistic append/rollback, error state transitions). The test plan's core concern -- that "tests validated shape, not behavior" (RC1) -- is fully realized here: the Python tests validate backend shapes, but nobody tests whether the Swift code actually works.

Coverage mapping:

| Test Plan ID | Status | Notes |
|-------------|--------|-------|
| T1: send_message_creates_sse_stream | MISSING | No Swift test |
| T2: send_message_with_existing_thread | MISSING | No Swift test |
| T3: token_stream_accumulation | MISSING | No Swift test |
| T4: result_ready_finalizes_message | MISSING | Would also catch B1 |
| T5: error_event_surfaces_error_state | MISSING | No Swift test |
| T6: meta_event_captures_ids | MISSING | No Swift test |
| T7: tool_called_event | MISSING | No Swift test |
| T8: approval_requested_event | MISSING | No Swift test |
| T9: thread_list_loads_threads | MISSING | No Swift test |
| T10: thread_list_create_thread | MISSING | No Swift test |
| T11: thread_list_load_failure | MISSING | No Swift test |
| T12: send_message_network_error | MISSING | No Swift test |
| T13: classification_done_event | MISSING | Would also catch B2 |
| T14: step_started_event | MISSING | No Swift test |
| T15: message_history_loads | MISSING | No Swift test |
| T16: empty_message_not_sent | MISSING | No Swift test |
| T17: concurrent_send_prevented | MISSING | No Swift test |

## Spec Compliance

**Deliverables present:**
1. ChatView with message list, composer bar, streaming display -- PRESENT
2. ChatViewModel with SSE lifecycle and token accumulation -- PRESENT but field name bugs
3. ThreadListView and ThreadListViewModel -- PRESENT
4. NavigationSplitView layout -- PRESENT (MainTabView)
5. Inline indicators: tool_called, approval_requested, classification_done, step_started -- PRESENT but classification_done reads wrong field
6. Model/privacy mode selectors in composer -- PRESENT (ComposerBar has privacy picker; model selection is via selectedProvider/selectedModel properties but no UI picker for model)

**Contract mismatches (blocking):**
- result_ready: ChatViewModel reads `payload["text"]`, backend sends `payload["response"]`
- classification_done: ChatViewModel reads `payload["domain"]`, backend sends `payload["privacy_mode"]`

## Anti-Pattern Scan Results

```
M6: Bare except / blind exception
  threads.py: clean (0 matches)
  ChatService.swift: try? on line 93 (SSE event decode)
  MainTabView.swift: try? on line 63 (logout -- acceptable)

M7: Wiring
  app.py line 347: app.include_router(threads_router) -- WIRED
  MainTabView: exists, public, not yet wired by AuthGuard (no app target)

M8: Domain isolation
  No cross-domain imports found.
```

## Smoke Test Results

```
Backend (Python via Docker):
[OK] threads router imported, prefix=/api/v1/threads
[OK] DELETE endpoint found: /api/v1/threads/{thread_id}
[OK] chat router imported, prefix=/api/v1
[OK] ChatRequest has provider field
[OK] ChatRequest has privacy_mode field
[OK] All 8 event types validated
[OK] threads_router wired in app.py
[OK] result_ready uses 'response' field (not 'response_text' or 'text')
     NOTE: iOS ChatViewModel reads payload['text'] -- CONTRACT MISMATCH
[OK] classification_done uses 'privacy_mode' field
     NOTE: iOS ChatViewModel reads payload['domain'] -- CONTRACT MISMATCH

Swift:
Build: clean (0 errors)
Tests: 60/60 pass (all from iOS3/iOS4; 0 from iOS5)
```

## Security

- No hardcoded secrets, API keys, or URLs in new files.
- ChatService uses TokenProviding protocol for Bearer token injection -- correct.
- ChatService creates a fresh URLSession per `sendMessage()` call (no session reuse). This is a minor resource concern but not a security issue.
- MainTabView logout uses `try? await authViewModel.logout()` -- acceptable for best-effort server notification; local auth state is cleared regardless.
- No CORS concerns (native client, no browser sandbox).

## Code Quality

**Good:**
- Actor-based ChatService with proper Sendable conformance.
- @Observable + @MainActor ChatViewModel follows Swift 6 strict concurrency.
- Optimistic append with rollback on network error (lines 195-215).
- Concurrent send prevention via `isStreaming` guard (line 84).
- Empty/whitespace message rejection (line 84).
- AnyCodable type-eraser handles all JSON value types including nested arrays/dicts.
- Error banners in ChatView are dismissible with clear messaging.

**Concerns:**
- ChatService.sendMessage() creates a new URLSession per call (line 71). Each call allocates connection pool, TLS context, etc. Should reuse a shared session.
- `try?` on SSE decode (line 93) silently drops events. If the backend sends an unexpected payload shape, the event vanishes with no indication.
- Model selector UI is incomplete: ComposerBar has a privacy picker but no model/provider picker widget. The selectedProvider/selectedModel properties exist on ChatViewModel but are never set from the UI.

## Beyond the Test Plan

1. **Python contract test `response_text` vs backend `response`:** The Python contract test `test_result_ready_payload_has_response_text` asserts `payload["response_text"]` exists, but the actual backend runner.py emits `payload["response"]`. The contract test is testing its own mock shape, not the real backend. This means the contract test suite has a gap -- it should verify the actual backend emission, not a fabricated dict.

2. **Python contract test `step_name` vs backend `step`:** `test_step_started_payload_has_step_name_and_model` asserts `"step_name"` in payload, but the backend sends `{"step": "agent"}`. Another contract test inaccuracy. The Swift code correctly reads `"step"`, so this doesn't cause a runtime bug in Swift, but it undermines the contract test's value.

3. **Thread response shape drift:** Backend list_threads stub returns items without `user_id` field, but Swift Thread struct has `userId` as non-optional. The contract test helper `_make_thread_dict` includes `user_id`, masking this stub gap. When the stubs are replaced with real DB queries, the response must include `user_id` or Thread decoding will fail.

4. **Single ChatViewModel instance shared across thread selections:** MainTabView creates one ChatViewModel and reuses it for all threads. When the user selects a different thread, `ChatView.task` calls `viewModel.loadHistory(threadId:)` which replaces messages. But if a stream is active on thread A and the user taps thread B, the stream continues appending to thread B's message list. The `cancelStream()` method exists but is never called on thread switch.

5. **No model/provider picker UI:** Phase deliverable 6 requires "model/privacy mode selectors in composer." The privacy picker exists but there is no UI widget to select provider or model. The `selectedProvider` and `selectedModel` properties on ChatViewModel are always nil. This is a partial deliverable gap.

## Blocking Issues

1. **B1: Contract mismatch -- result_ready field name.** `ios/Noa/Sources/Noa/ViewModels/ChatViewModel.swift:175` reads `payload["text"]` but the backend (`src/noa/orchestrator/runner.py:148`) sends `payload["response"]`. The result_ready event will silently fail to update the assistant message with the canonical response text, leaving potentially incomplete token-accumulated text in the UI.

2. **B2: Contract mismatch -- classification_done field name.** `ios/Noa/Sources/Noa/ViewModels/ChatViewModel.swift:153` reads `payload["domain"]` but the backend (`src/noa/orchestrator/runner.py:76`) sends `payload["privacy_mode"]`. The classification indicator will always show "unknown" instead of "private" or "external".

3. **B3: Zero Swift tests for iOS5.** No ChatViewModelTests, ChatServiceTests, or ThreadListViewModelTests exist. The test plan specified 17 MUST-HAVE Swift tests. All 60 passing Swift tests are from previous phases. This violates M1 (spec traceability) and M2 (negative tests). Without tests, the contract mismatches (B1, B2) were not caught.

4. **B4: Silent SSE event dropping.** `ios/Noa/Sources/Noa/Services/ChatService.swift:93` uses `try?` on `decoder.decode(SSEEvent.self, from: data)`. Any event with an unexpected payload shape (new fields, type mismatches, encoding issues) is silently dropped with no error callback. Combined with B1 (wrong field name), the result_ready event may fail to decode entirely, leaving the user with a partial response and no indication anything went wrong. At minimum, decode failures should be logged or reported via an error event yield.

## Decision Review

The implementation quality of the Swift code is generally good -- proper actor isolation, @Observable patterns, optimistic append/rollback, concurrent send prevention. The architecture is sound. However, the complete absence of Swift tests for this phase means the contract mismatches (B1, B2) went undetected. This is the exact RC1 pattern from the project audit: "tests validated shape, not behavior." The Python contract tests validate backend shapes but nobody tested whether ChatViewModel actually handles real SSE events correctly.

The fix is straightforward:
1. Fix the two field name mismatches (B1: `"text"` -> `"response"`, B2: `"domain"` -> `"privacy_mode"`).
2. Replace `try?` with proper error handling in SSE decode.
3. Add Swift tests covering at minimum: token accumulation, result_ready finalization, error event handling, thread list loading, and concurrent send prevention.
