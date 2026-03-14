# Project Health Brief — 2026-03-14 (MVP-fixes-2)

**Score: 7/10**
Starting at 5: +0 (mid-wave — Wave 22/23 boundary not reached); +1 (last QA verdict PASS_WITH_NOTES, all must-haves green); +1 (zero critical findings open); +1 (application security posture fully green); +0 (infrastructure not re-audited, mid-wave); +1 (non-mocked integration tests present via TestClient). Subtract: -1 infrastructure security warn (no lockfile, carried baseline); -1 open findings (3 open: L11, L12 feature requests, MVP-L3 low queue-recovery gap). Score = 5+1+1+1+1-1-1 = 7. Stable at prior brief level.

## What Happened (since last brief)

1. **QueueDrainWorker now actually dispatches tasks** — MVP-M1 fixed the semantic dead-end: `_dispatch_task()` calls `runner.run()` consuming all events, sets status="completed" on success, and implements retry logic (retry_count increment, status="queued" if retries remain, "failed" if exhausted). The queue-and-resume feature is now functionally complete.
2. **Queued chat path creates Run/Conversation rows** — MVP-M2 added `_make_run_service(initial_status="queued")` call before enqueue so queued private requests are immediately visible on the Runs page. No more invisible stuck requests.
3. **enable_tool now validates against TOOL_SCHEMAS** — MVP-L1 prevents no-op grants for function-level keys like `memory__remember`. Endpoint returns 404 for keys not in TOOL_SCHEMAS.

## Greatest Risk

**Queue task stuck in "processing" on API crash.** `DurableQueue.poll()` only returns `status="queued"` tasks. The drain worker sets `task.status = "processing"` and commits before dispatching. If the API container crashes between that commit and dispatch completion, the task is permanently stuck — `poll()` will never return it. No timeout recovery exists for `"processing"` state (unlike the existing `timeout_at` recovery for `"queued"/"retrying"` tasks). In production, any container restart during active dispatch would silently lose the in-flight task. This is a low-severity finding now (MVP-L3, tracked in FINDINGS.md) but becomes high-severity in any deployment with restarts under load.

## Decisions Needed

- **MVP-L3 recovery:** Add `"processing"` timeout recovery to `DurableQueue.poll()`. A task stuck in "processing" for longer than `timeout_at` should be reset to "queued" so it can be retried. This is a one-method change and should be prioritized before production deployment with private-domain queuing.
- **_NoOpRunService consolidation:** Two identical no-op classes exist in `drain.py` and `chat.py`. Decide canonical location and consolidate before either interface diverges.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All new code paths require auth. Drain worker hardcodes privacy_mode="private" (cannot be overridden via payload). |
| Secrets | ok | No secrets in queue payload. No hardcoded credentials in drain.py or tools.py changes. |
| Domain isolation | ok | No cross-domain imports. Drain worker enforces private-only execution. |
| Input validation | ok | enable_tool validates against TOOL_SCHEMAS. Function-level keys correctly rejected with 404. |
| Error handling | ok | All except blocks log with logger.exception/error. No silent swallowing. No success-on-error. |

## Security Posture — Infrastructure

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | N/A — mid-wave. Baseline: 107 scoped allow rules. |
| Docker config | ok | N/A — mid-wave. Baseline: no root, no privileged, no secrets in ENV. |
| CORS / network exposure | ok | N/A — mid-wave. Baseline: explicit localhost origins, wildcard rejected. |
| Secrets in repo | ok | N/A — mid-wave. Baseline: only .env.example tracked. |
| Dependency pinning | warn | No lockfile. Loose >= pins. Carried from baseline. |

## Risks You Are Taking

1. **Task stuck on crash (Low probability, Medium impact):** A container restart during drain dispatch leaves a task permanently in "processing" status. poll() never recovers it. Fix requires one guard in poll() — low effort, should be done before any load-testing.

2. **No dependency lockfile (Medium probability, Low impact):** New upstream release could introduce breaking change on next pip install. Standard Python risk; low likelihood given package stability but unmitigated.

3. **MVP-M2 DB write not tested with real DB (Low probability, Low impact):** `_make_run_service` for the queued path is mocked away in all current tests. If the Conversation/Run row creation fails silently in production (wrong field type, missing FK, etc.), queued requests will appear to enqueue successfully but have no Runs page entry. Covered by the existing noqa: BLE001 + logger.debug path, not a crash, but creates a hidden gap.
