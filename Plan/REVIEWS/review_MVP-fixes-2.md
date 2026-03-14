# QA Review: Phase MVP-fixes-2

**Date:** 2026-03-14
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 3 test files cite phase IDs (MVP-M1, MVP-L2, MVP-H2, SPEC.md §17.1/17.2). drain_dispatch.py header cites SPEC.md §17.2 directly. |
| M2 | Negative Tests | PASS | drain_dispatch: TestNoRunnerConfigured (no dispatch), TestEmptyQueue (poll returns None), TestMaxRetriesExceeded (boundary at exact max), retry failure path. tool_visibility: TestEnableToolRejectsFunctionKeys (404 for function-level keys). queue_wiring: runner-not-called when queued. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. enable_tool validates against TOOL_SCHEMAS (deny-unknown). No function-level key bypass. All TOOL_SCHEMAS keys present in TOOL_CAPABILITIES — no KeyError risk in enable_tool response body. |
| M4 | Determinism | PASS | No wall-clock time in assertions. No network calls. All 1981 tests pass deterministically. |
| M5 | Implementation Completeness | PASS | All 4 fixes implemented: MVP-M1 (drain dispatch with retry logic), MVP-M2 (Run/Conversation rows created for queued path), MVP-L1 (TOOL_SCHEMAS validation), MVP-L2 (meta event before queued event). Pre-existing test fixes also confirmed passing. |
| M5b | Findings Currency | PASS | FINDINGS.md updated: MVP-M1, MVP-M2, MVP-L1, MVP-L2 all marked Resolved with "MVP-fixes-2". Open count: 2 (L11/L12 feature requests only). |
| M6 | No Silent Error Swallowing | PASS | All except blocks are `# noqa: BLE001` with `logger.exception` or `logger.error`. No `pass` on exception. _dispatch_task logs error with exc and retry count. Pre-existing patterns unchanged. |
| M7 | Wiring Completeness | PASS | No new routers. QueueDrainWorker already wired in lifespan (MVP-fixes phase). drain.py confirmed imported in app.py at line 353. |
| M8 | Domain Isolation | PASS | No cross-domain imports. drain.py imports only from noa.queue.durable. No external_worker in private_worker or vice versa. |
| M2b | Write-Path Test Fidelity | PASS | drain_dispatch tests mock DurableQueue.poll() returning a real mock task object; status assertions check task.status directly — not vacuous round-trips. |
| M3b | Write-Path User Scoping | PASS | _make_run_service called with user_id at line 134-136 for queued path. Run row includes user_id at creation. |
| M4b | Mock Interface Accuracy | PASS | Session mocks use AsyncMock for async methods (commit). Drain tests use MagicMock for task object (sync attributes). No async/sync confusion. |
| M5c | Related-Issue Scope | PASS | MVP-M1/M2/L1/L2 are all 4 explicitly-tracked findings. No sibling instances missed. |

## Spec Compliance

SPEC.md §17.2 (queue drain): `_dispatch_task` now calls `runner.run()` consuming all events via `async for`. On success sets status="completed"; on failure increments retry_count and sets status based on max_retries comparison. Matches spec semantics.

SPEC.md §17.1/17.2 (queued chat path): Run + Conversation rows now created via `_make_run_service(initial_status="queued")` before enqueue, so queued requests are visible on Runs page. Matches requirement.

Tool endpoint fix (MVP-L1): Validation now uses `TOOL_SCHEMAS` (top-level tool names only) rather than `TOOL_CAPABILITIES` (which includes function-level keys). enable_tool returns 404 for `memory__remember`, `web_search__search`, etc.

SSE contract (MVP-L2): `_queued_event_stream` emits `meta` event first, then `queued`, then `done`. Matches normal chat path contract.

## Test Coverage

| Requirement | Tests | Status |
|---|---|---|
| MVP-M1: dispatch on success | TestSuccessfulDispatch (3 tests) | Covered |
| MVP-M1: retry on failure | TestFailedDispatchWithRetriesRemaining (3 tests) | Covered |
| MVP-M1: max retries → failed | TestMaxRetriesExceeded (2 tests) | Covered |
| MVP-M1: no runner | TestNoRunnerConfigured (2 tests) | Covered |
| MVP-M1: empty queue | TestEmptyQueue (1 test) | Covered |
| MVP-M2: Run rows on queued path | test_meta_event_contains_run_id_and_thread_id (UUID validated) | Partially — no DB assertion |
| MVP-L1: function-key 404 | TestEnableToolRejectsFunctionKeys (2 tests via TestClient) | Covered |
| MVP-L2: meta before queued | test_meta_event_precedes_queued_event | Covered |
| MVP-L2: meta has run_id/thread_id | test_meta_event_contains_run_id_and_thread_id | Covered |

Coverage gap: MVP-M2 (Run/Conversation creation for queued path) has no DB-level assertion. The test patches `_get_session_factory` to return `None`, so `_make_run_service` silently skips the DB write. The test confirms the SSE stream contains correct run_id/thread_id, but does not verify the Run row was actually persisted. Acceptable for this phase given the DB session factory is the correct system boundary to mock in unit tests. S5 is OPEN for the DB write path.

Non-mocked integration test: `TestQueuedResponse` uses `create_app()` + `TestClient`, exercising real FastAPI routing, SSE streaming, and the `_queued_event_stream` generator without mocking those layers. This satisfies S5 for the HTTP/SSE path.

## Anti-Pattern Scan Results

**M6: Bare except blocks in new code:**
```
src/noa/queue/drain.py:74:  except Exception:  # noqa: BLE001
src/noa/queue/drain.py:107: except Exception:  # noqa: BLE001
```
Both log via `logger.exception(...)` — not silent. PASS.

**M7: Wiring check:**
```
src/noa/api/app.py:353: from noa.queue.drain import QueueDrainWorker
src/noa/api/app.py:357-362: drain_worker = QueueDrainWorker(...); await drain_worker.start()
src/noa/api/app.py:369-370: if drain_worker is not None: await drain_worker.stop()
```
QueueDrainWorker instantiated in lifespan. Shutdown registered. PASS.

**M8: Domain isolation:**
```
grep "from noa.private_worker" src/noa/external_worker/ → No matches
grep "from noa.external_worker" src/noa/private_worker/ → No matches
```
PASS.

**Ruff check on all changed files:** `All checks passed!`

## Smoke Test Results

```
=== Import Tests ===
PASS: noa.queue.drain imports OK
PASS: noa.api.v1.tools imports OK
PASS: noa.api.v1.chat imports OK

=== TOOL_CAPABILITIES Coverage ===
PASS: All TOOL_SCHEMAS keys have TOOL_CAPABILITIES entries
  calendar -> calendar.write
  external_memory -> external_memory.remember
  gmail -> gmail.send
  memory -> memory.remember
  notion -> notion.read
  web_search -> search.read

=== _NoOpRunService interface ===
PASS: _NoOpRunService: all methods callable and no-op

=== MVP-L1: TOOL_SCHEMAS validation ===
PASS: 14 function-level keys in TOOL_CAPABILITIES, all absent from TOOL_SCHEMAS (will return 404)

=== MVP-L2: meta event order in _queued_event_stream ===
  Event order: ['meta', 'queued', 'done']
PASS: meta event precedes queued event
PASS: meta event contains run_id and thread_id

=== MVP-M1: Commit pattern ===
  session.commit() calls in _dispatch_task: 1
PASS: _dispatch_task commits after status change

Full test suite: 1981 passed, 88 warnings in 80.75s
```

## Security

No new security concerns introduced.

- enable_tool correctly uses TOOL_SCHEMAS (not TOOL_CAPABILITIES) for validation — prevents no-op grants from function-level keys.
- Drain worker runs with `privacy_mode="private"` hardcoded — cannot be overridden by queue payload, correct domain enforcement.
- _NoOpRunService methods accept and discard all arguments — no injection surface.
- Retry logic does not expose internal exception messages to the client (logged only).

## Code Quality

**mypy finding (non-blocking):** `src/noa/queue/drain.py:129: error: Item "None" of "Any | None" has no attribute "run"`. The type signature `runner: Any | None = None` and the guard at lines 97-104 mean this is a false positive at runtime (None is always caught before `_dispatch_task` is called), but mypy cannot prove this across method boundaries. Adding `assert self._runner is not None` at the start of `_dispatch_task` would eliminate the error and make the invariant explicit.

**_NoOpRunService duplication:** There are now two `_NoOpRunService` classes — one in `noa.queue.drain` and one in `noa.api.v1.chat`. Both are identical 3-method no-op stubs. This is minor technical debt; consolidating into `noa.queue.noop` or similar would reduce drift risk.

## Deep Dive

### Processing-stuck on crash (untracked, low severity)

`DurableQueue.poll()` only returns tasks with `status == "queued"` (line 165 of durable.py). `_drain_one` sets `task.status = "processing"` and commits before calling `_dispatch_task`. If the API container crashes between these two commits, the task is stuck in `"processing"` state permanently — `poll()` will never return it again. The task would need manual DB intervention to be retried.

This is a pre-existing design gap (present before this phase) and not introduced by the MVP-fixes-2 changes. The retry logic added in this phase handles failures during dispatch, but not crashes during dispatch setup. Adding a `"processing"` timeout recovery to `poll()` (similar to how it handles `timeout_at` for `"queued"/"retrying"` tasks) would fix this.

This finding is worth tracking but not blocking for this phase.

### Retry boundary condition: off-by-one confirmed correct

`task.retry_count >= task.max_retries` is the comparison after incrementing. With `retry_count=2, max_retries=3`: after increment, `3 >= 3` → `True` → `"failed"`. This is correct: max 3 total attempts (retry_count 0, 1, 2, then fails on 3rd failure). The test `test_status_failed_when_max_retries_reached` confirms this with `retry_count=2, max_retries=3`.

### TOOL_CAPABILITIES KeyError risk eliminated

`enable_tool` previously accessed `TOOL_CAPABILITIES[name]` in the response body (line 297). After the MVP-L1 fix, `name` is validated against `TOOL_SCHEMAS` — and all TOOL_SCHEMAS keys are confirmed present in TOOL_CAPABILITIES. No KeyError path exists. PASS.

### _make_run_service return value for queued path is discarded

At lines 134-137: `await _make_run_service(..., initial_status="queued")` is called but its return value (a `_NoOpRunService`) is discarded. This is intentional — the queued path doesn't run the runner, so no run service is needed. The function is called purely for its DB side effect. The code is correct but slightly misleading. A comment would clarify intent.

## Notes (PASS_WITH_NOTES)

1. **mypy annotation gap** (`src/noa/queue/drain.py:129`): Add `assert self._runner is not None` at the start of `_dispatch_task` to satisfy mypy and make the runtime invariant explicit. Low risk but good practice.

2. **_NoOpRunService duplication**: Two identical classes exist in `drain.py` and `chat.py`. Consider consolidating to `noa.queue.noop` or `noa.api.v1.chat` as the canonical location and importing in drain.py. Prevents divergence if the interface changes.

3. **Processing-stuck-on-crash**: `DurableQueue.poll()` does not recover tasks stuck in `"processing"` status after a crash. Add recovery to `poll()` similar to the existing timeout recovery for `"queued"/"retrying"` tasks. Low severity now; would become high severity in production under load.

4. **MVP-M2 DB-level assertion missing**: No test verifies that the Run row is actually persisted to DB when `_make_run_service` is called for the queued path. Tests mock `_get_session_factory` to `None`, meaning the DB write is silently skipped in all current tests. A future integration test with a real DB session would close this gap.

5. **`_make_run_service` return value discarded on queued path**: Comment the intentional discard at line 134 to clarify that the function is called for its DB side effect only.

## Decision Review

All 4 MVP-fixes-2 findings (MVP-M1, MVP-M2, MVP-L1, MVP-L2) are implemented and verified through 44 passing tests plus smoke tests. The implementation is correct, secure, and properly wired. The pre-existing test fixes (mock patterns) also pass. Notes are minor quality improvements, none blocking.
