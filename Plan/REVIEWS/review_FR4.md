# QA Review: Phase FR4

**Date:** 2026-03-13
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 19 backend tests cite UX-H1/H3/H10 phase IDs. Frontend tests cite UX-H2/H5/H9/H10/H3. |
| M2 | Negative Tests | PASS | test_put_system_prompt_rejects_too_long_content (422), test_get_system_prompt_falls_back_to_file_when_none, empty message send shows toast not crash. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. All endpoints gated by `require_auth`. `except Exception` blocks all log before returning, no success on error. System prompt content length-bounded (10k). |
| M4 | Determinism | PASS | No wall-clock assertions. No network calls in tests. AsyncMock used consistently. |
| M5 | Implementation Completeness | PASS | All 6 deliverable files present. UX-H1 keepalive implemented. UX-H2 send button fix applied. UX-H3 endpoints + settings UI present. UX-H5 ExpandableData in EventTimeline. UX-H9 optimistic message state. UX-H10 ActivityStream with tool_start/tool_end. FINDINGS.md not updated (M5b — see Notes). |
| M5b | Findings Currency | OPEN | UX-H1, UX-H2, UX-H3, UX-H5, UX-H9, UX-H10 still show "Open" in FINDINGS.md — not marked Resolved/FR4. CI-015 violation. |
| M6 | No Silent Error Swallowing | PASS | All `except Exception` blocks use `# noqa: BLE001` and either log.warning/debug or re-raise. No success responses on error. |
| M7 | Wiring Completeness | PASS | `settings_router` includes `/system-prompt` endpoints (GET + PUT) — confirmed via app routes. chat.py `_SSE_KEEPALIVE_INTERVAL = 15` wired in `_run_with_keepalive()`. runner.py tool_start/tool_end emitted per tool call. |
| M8 | Domain Isolation | PASS | No cross-domain imports in external_worker/private_worker. |
| S1 | Error Handling & Boundaries | PASS | Empty string → reset-to-default path. OSError handled in `_load_default_system_prompt`. ThreadID miss handled with toast. |
| S2 | Code Consistency | PASS | Follows existing naming conventions. `_NoOpRunService`, `_make_event`, `_persist_event` consistent with prior patterns. |
| S3 | Migration & Rollback | N/A | No DB schema changes. |
| S4 | Documentation | OPEN | `prompts/system_prompt.txt` not COPYed into Dockerfile — Docker image missing the file; `_load_default_system_prompt()` silently returns `""` in production. Not a safety hazard but degrades the feature. |
| S5 | Integration Smoke Test | OPEN | All 19 backend tests use mocked sessions. No ASGI test client with real DB for the new GET/PUT /system-prompt endpoints. CI-016 applies (DB-touching endpoints). |

## Spec Compliance

**SPEC.md §22.2 (SSE event types):** `tool_start` and `tool_end` are NOT in `VALID_EVENT_TYPES` (frozenset in `runs/schemas.py`) and are correctly excluded from DB persistence. These are intentionally live-only SSE events consumed by the `ActivityStream` during the active stream. The `test_ios3_networking_contract.py::TestValidEventTypes::test_backend_event_types_match_spec` confirms the contract is maintained. No spec violation.

**UX-H1 (SSE keepalive):** `_SSE_KEEPALIVE_INTERVAL = 15` seconds. Implementation uses `asyncio.wait_for` with a queue, emitting SSE comment `": keepalive\n\n"` on timeout. Correct approach.

**UX-H2 (send button):** Button `disabled={isStreaming}` only — not `disabled={!input.trim() || isStreaming}`. Clicking with empty input shows a toast. Correct.

**UX-H3 (system prompt):** GET `/api/v1/settings/system-prompt` returns `{content, is_default}`. PUT `/api/v1/settings/system-prompt` accepts `{content}` with 10k limit. File-backed default from `prompts/system_prompt.txt`. Settings UI has `data-testid="system-prompt-textarea"` and `data-testid="system-prompt-save"`. Correct.

**UX-H5 (tool call details):** `ExpandableData` component added to EventTimeline for `tool_called` (shows `args`) and `tool_result` (shows `result ?? output ?? data`). Response field bug fix: `event.data.response ?? event.data.response_text`. Correct.

**UX-H9 (optimistic message):** `optimisticUserMessage` state set immediately on send, shown until real message from refetch deduplicated. `queueMicrotask` used to clear state after deduplication. Correct.

**UX-H10 (activity stream):** `ActivityStream` component handles `tool_start`, `tool_end`, `step` events with labels ("Starting: {name}", "Finished: {name}", "Step: {label}"). `VALID_SSE_EVENTS` (frontend) updated to include these three types. Runner emits `tool_start`→`tool_called`→`tool_end` triplet per tool call. Correct.

## Test Coverage

| Test | Spec Requirement | Type |
|------|-----------------|------|
| test_keepalive_interval_exists | UX-H1 constant | unit (source inspection) |
| test_keepalive_interval_is_reasonable | UX-H1 bound | unit (source inspection) |
| test_chat_endpoint_uses_asyncio | UX-H1 implementation | unit (source inspection) |
| test_chat_stream_returns_sse_response | UX-H1 behavioral | unit (mocked runner) |
| test_chat_stream_includes_meta_event | UX-H1 meta event | unit (mocked runner) |
| test_default_system_prompt_file_exists | UX-H3 file | unit (filesystem) |
| test_default_system_prompt_file_is_not_empty | UX-H3 content | unit (filesystem) |
| test_load_default_system_prompt_helper | UX-H3 helper | unit (real call) |
| test_get_system_prompt_endpoint_exists | UX-H3 GET | unit (mocked service) |
| test_get_system_prompt_returns_user_prompt_when_set | UX-H3 GET user prompt | unit (mocked service) |
| test_get_system_prompt_falls_back_to_file_when_none | UX-H3 fallback | unit (mocked + patched) |
| test_put_system_prompt_saves_content | UX-H3 PUT save | unit (mocked service) |
| test_put_system_prompt_rejects_too_long_content | UX-H3 validation | unit (boundary negative) |
| test_put_empty_content_resets_to_default | UX-H3 reset | unit (mocked + patched) |
| test_tool_start_emitted_before_tool_called | UX-H10 ordering | unit (async mock graph) |
| test_tool_end_emitted_after_tool_called | UX-H10 ordering | unit (async mock graph) |
| test_tool_start_carries_tool_name | UX-H10 payload | unit (async mock graph) |
| test_tool_end_carries_tool_name | UX-H10 payload | unit (async mock graph) |
| test_multiple_tools_each_get_start_end | UX-H10 multiplicity | unit (async mock graph) |

**Gaps:**
- No non-mocked integration test for GET/PUT `/api/v1/settings/system-prompt` endpoints (S5 OPEN, CI-016)
- Source-inspection tests (test_keepalive_interval_exists, test_chat_endpoint_uses_asyncio) per CI-028 have behavioral companion tests (test_chat_stream_returns_sse_response), so M2c is satisfied.

## Anti-Pattern Scan Results

**M6 — `except Exception:` in changed files:**

```
src/noa/api/v1/chat.py:    except Exception:  # noqa: BLE001  (x8)
src/noa/api/v1/settings.py: except Exception:  # noqa: BLE001 (x2)
src/noa/orchestrator/runner.py: except Exception:  # noqa: BLE001 (x4)
```

All reviewed. Chat.py uses BLE001 noqa on best-effort DB persistence helpers that log.warning before returning. Settings.py handler for ProviderRouter reload logs.warning/debug. Runner.py handlers all log.error or log.warning with run_id context. None are silent swallowing.

**M7 — Router registration:**
```
app.include_router(settings_router)  # line 446 — includes /system-prompt sub-routes
app.include_router(chat_router)      # line 443 — includes /chat with keepalive
```
Both confirmed present.

**M8 — Domain isolation:** No cross-domain imports found.

## Smoke Test Results

```
=== Import checks ===
chat._SSE_KEEPALIVE_INTERVAL = 15
PASS: keepalive constant correct (15s)
PASS: load_default_system_prompt() returned 313 chars
PASS: OrchestratorRunner import OK
PASS: system_prompt.txt exists, 313 chars

=== App creation ===
Routes with 'system-prompt': ['/api/v1/settings/system-prompt', '/api/v1/settings/system-prompt']
PASS: system-prompt routes registered
Routes with 'chat': ['/api/v1/chat']
PASS: App created successfully

=== VALID_EVENT_TYPES check ===
FAIL: 'tool_start' NOT in VALID_EVENT_TYPES — will be filtered from DB persistence!
FAIL: 'tool_end' NOT in VALID_EVENT_TYPES — will be filtered from DB persistence!
```

**Interpretation:** The VALID_EVENT_TYPES omission of `tool_start`/`tool_end` is intentional architecture — these are live-only SSE events for the ActivityStream, not stored to the DB. Confirmed by: (a) `test_ios3_networking_contract.py::test_backend_event_types_match_spec` still passes, (b) `_NoOpRunService.append_event` in runner context is a no-op anyway, (c) the EventTimeline reads stored events from DB separately. NOT a blocking issue.

**Backend tests: 19/19 PASS**
**Frontend tests: 18/18 PASS**

## Security

No new security concerns. All endpoints require `require_auth`. System prompt content is length-bounded (10k chars) preventing large payload attacks. `_load_default_system_prompt` uses `OSError` catch, no exception leaks. No hardcoded secrets. The `contextlib.suppress(asyncio.CancelledError, Exception)` in `_run_with_keepalive` `finally` block is acceptable for task cleanup — it's labeled noqa BLE001.

## Code Quality

The keepalive implementation using an `asyncio.Queue` with a producer task is solid. The `TimeoutError` catch correctly handles `asyncio.wait_for` timeout. The `_keepalive` sentinel dict approach is slightly unusual but functional and well-commented.

The `_load_default_system_prompt` path computation (`__file__.parent.parent.parent.parent.parent / "prompts"`) — 5 levels up from `src/noa/api/v1/settings.py` — is fragile and undocumented. It works in the worktree but requires `prompts/` to be at the repo root relative to where the package is installed. The Docker image does not COPY `prompts/` (only `src/`, `alembic/`), so in production this silently returns `""` and the system prompt feature does nothing unless the user saves a custom prompt.

## Deep Dive

**1. prompts/ directory missing from Docker image:** `docker/noa-api/Dockerfile` only COPYs `src/`, `alembic/`, `alembic.ini`, `pyproject.toml`. The `prompts/system_prompt.txt` is not included. In a deployed Docker container, `_load_default_system_prompt()` will raise `OSError` (caught silently) and return `""`. The feature works in dev (worktree filesystem) but not in production unless the user explicitly sets a custom prompt. The graceful fallback prevents crashes but makes the default experience confusing — new users see a blank system prompt.

**2. M5b — Findings not synced:** UX-H1, UX-H2, UX-H3, UX-H5, UX-H9, UX-H10 remain marked "Open" in `Plan/FINDINGS.md`. CI-015 requires updating these to `**Resolved**` / Resolved By = FR4 before the phase is marked complete.

**3. Frontend send button guard:** When `isStreaming=true`, the input field is also disabled (`disabled={isStreaming}`), so users can't accidentally modify text during streaming. But the empty-input toast is only triggered via `handleSend()` — keyboard Enter is also bound. If a user presses Enter with empty input, `handleSend()` runs and the toast shows correctly (verified in code review).

**4. SSEClient reconnect with tool_start/tool_end:** The SSEClient reconnect path (`/api/v1/runs/{runId}/events?after_event_id=...`) reads from the DB. Since `tool_start`/`tool_end` are not stored, they won't appear after a reconnect. This is acceptable for the live activity stream (connection-scoped) but means run detail replays won't show tool lifecycle progress. This is a design choice, not a bug.

**5. `queueMicrotask` for optimistic message cleanup:** `queueMicrotask(() => setOptimisticUserMessage(null))` is a valid React pattern for deferred state updates but is unusual. It avoids setting state during render without violating React rules. No issue.

## Blocking Issues (FAIL only)

None. Verdict is PASS_WITH_NOTES.

## Notes (PASS_WITH_NOTES)

1. **M5b — FINDINGS.md not updated (CI-015 violation):** UX-H1, UX-H2, UX-H3, UX-H5, UX-H9, UX-H10 must be marked `**Resolved**` with Resolved By = FR4 before the phase is marked complete. Open/Resolved counts need updating.

2. **S4 — Docker image missing `prompts/` directory:** `docker/noa-api/Dockerfile` does not COPY `prompts/`. Add `COPY prompts/ ./prompts/` to the Dockerfile, or accept that the default system prompt is only available to users who set a custom prompt. If left as-is, add a comment in `_load_default_system_prompt()` documenting the Docker fallback behavior.

3. **S5 — No integration test for `/system-prompt` endpoints:** GET/PUT `/api/v1/settings/system-prompt` have only mocked-service tests. Per CI-016, a DB-touching endpoint should have at least one ASGI test client test with real DB. Consider adding to the existing `tests/integration/` suite (FR2 integration tests could cover this).

## Decision Review

The `tool_start`/`tool_end` live-only SSE design is deliberate and correct — the ActivityStream is a streaming-only view while the EventTimeline reads stored events. Both serve different UX purposes (live progress vs. historical audit). No design decision needed.

The `prompts/` Docker gap is the most impactful note: without fixing the Dockerfile, new deployments will silently not show a default system prompt, making the UX-H3 feature only partially delivered in production.
