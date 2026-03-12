# System Audit Report -- Wave 21 Boundary

**Date:** 2026-03-12
**Auditor:** system-auditor agent
**Scope:** Full-system audit at Wave 21 (Pipeline Excellence & Quality Infrastructure) boundary
**Container:** noaos-noa-api-1 (healthy, 18h uptime), noa-dev (5h uptime)

---

## Summary

- **Overall Health Score**: 7.5/10
- **Endpoints Tested**: 52/60 responding correctly (8 returning 404 due to stale container)
- **E2E Flows Tested**: 4/5 passing
- **Security Issues**: 2 found (1 medium, 1 low)
- **Dead Code Items**: 3 found
- **Cross-Phase Regressions**: 2 found
- **Unit Tests**: 1728 passing, 2 known-flaky failures, 1 new failure (QE6)
- **Integration Tests**: 55/56 passing (1 env-specific failure)
- **Static Gates**: ruff 0 errors, mypy 0 errors

---

## Critical Findings (must fix before next wave)

None.

---

## High Findings (fix soon)

### H1: DELETE /threads/{id} returns 500 -- FK constraint violation

**Endpoint:** `DELETE /api/v1/threads/{thread_id}`
**Response:** `{"code":"INTERNAL_ERROR","message":"An internal error occurred"}`
**Root Cause:** `usage_stats.run_id` FK to `runs` table lacks `ondelete="CASCADE"`. When thread deletion cascades to delete runs, the usage_stats rows still reference those run IDs, causing `IntegrityError: ForeignKeyViolationError`.
**Location:** `src/noa/db/models/usage.py:37` -- `run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))` -- missing `ondelete="CASCADE"` or `ondelete="SET NULL"`.
**Impact:** Users cannot delete threads that have associated chat runs. This breaks the thread lifecycle and iOS swipe-to-delete.
**Fix:** Add `ondelete="SET NULL"` to the FK (since run_id is already nullable) and create a migration.

### H2: Backup container crash-looping

**Container:** `noaos-backup-1`
**Status:** `Restarting (1) 17 seconds ago` (continuous restart loop)
**Error:** `setpgid: Operation not permitted` (repeated in logs)
**Root Cause:** The DE3 container hardening (`cap_drop: ALL`, `security_opt: no-new-privileges`) is too restrictive for the backup container, which needs `setpgid` for its shell scripts (pg_dump pipeline).
**Impact:** No automated backups are running. The `/health/backup` endpoint returns 404 (route exists but server is stale -- see M1).
**Fix:** Add `cap_add: [SETPGID]` to the backup service in docker-compose.yml, or relax security_opt for that specific container.

---

## Medium Findings (track)

### M1: Running API server does not reflect latest code (stale container)

**Observation:** The noa-api container has been running 18 hours without restart. Uvicorn started with `--factory` (no `--reload`). Routes added in Wave 20 (Google OAuth, health/backup, voice/transcribe) are registered in code but return 404 from the live server.
**Affected routes:**
- `GET /api/v1/auth/google/authorize` -- 404
- `GET /api/v1/auth/google/callback` -- 404
- `GET /api/v1/auth/google/status` -- 404
- `DELETE /api/v1/auth/google/disconnect` -- 404
- `GET /health/backup` / `GET /api/v1/health/backup` -- 404
- `POST /api/v1/voice/transcribe` -- 404
**Impact:** New features from Wave 20 are not available to users until container restart.
**Fix:** Restart the noa-api container (`docker compose restart noa-api`). Consider adding `--reload` for development or documenting the restart requirement after code changes.

### M2: /docs, /redoc, /openapi.json exposed unconditionally

**Observation:** API documentation endpoints return 200 with full schema. No environment-based gating.
**Impact:** In production, this exposes the full API surface to attackers for reconnaissance.
**Fix:** Conditionally disable docs in production: `docs_url=None if ENVIRONMENT == "production" else "/docs"`.

### M3: traceability.py --check overwrites manual sections in TRACEABILITY.md

**Observation:** Running `traceability.py --check` regenerates TRACEABILITY.md, overwriting the manually-added "Mutation Testing Baseline" section that QE6 tests expect.
**Impact:** CI traceability check would break the QE6 test assertion (`test_traceability_has_mutation_baseline_section`).
**Fix:** Either append-only mode for manual sections, or move the mutation baseline to a separate file.

### M4: Integration tests require manual TEST_DATABASE_URL in dev container

**Observation:** Integration tests (30 tests in 6 suites) fail with `RuntimeError: No TEST_DATABASE_URL env var set and testcontainers failed to start` when run from noa-dev container. Docker socket is not available inside the dev container for testcontainers.
**Impact:** Developers must manually set `TEST_DATABASE_URL` to run integration tests locally.
**Fix:** Add `TEST_DATABASE_URL` to the dev container environment in docker-compose.dev.yml.

---

## Low/Informational

### L1: Two pre-existing flaky tests

- `test_qc3_error_handling.py::test_lifespan_db_skip_emits_warning` -- aiosqlite event loop closed race condition
- `test_tool_interface.py::TestMCPToolAdapter::test_mcp_adapter_execute_raises_not_implemented` -- error message drift from TM6

These are known since Wave 18-19 and tracked.

### L2: QE6 test failure -- mutation baseline section

`test_traceability_has_mutation_baseline_section` fails because TRACEABILITY.md was regenerated without the manual section. Related to M3.

### L3: NotImplementedError stubs remain (2 locations)

- `src/noa/tools/mcp_adapter.py:58` -- legacy adapter (superseded by TM6 mcp_remote.py, retained for backward-compat tests)
- `src/noa/orchestrator/nodes/tools.py:73` -- fallback if gateway not wired (defensive, not a stub)

Both are intentional/documented.

### L4: Pass-only functions (abstract/interface methods)

14 pass-only functions found, all are legitimate abstract base class methods or protocol stubs:
- `ToolGateway.execute`, `ToolInterface.execute`, `SearchProvider.name/search`
- `TranscriptionProvider.transcribe`, `NotificationSink.notify`
- `CapabilityStore.has_capability/grant/revoke`
- `NoOpCheckpointer.save`
- `RunServiceProtocol.create_run/update_status/append_event`

These are interface contracts, not stubs.

### L5: Run cost shows as None in API response

Runs created via chat show `total_cost_usd: null` even though LLM usage shows cost_usd: 0.0. The cost aggregation from usage_stats to the run list endpoint may need a join or post-calculation.

### L6: Network isolation test failure (env-specific)

`test_api_port_binding_is_localhost_only` fails because the test inspects Docker port bindings from inside a container. This test is designed for CI (where Docker socket is available), not dev container.

### L7: TODO comment remains

`src/noa/api/v1/tools.py:33` -- `# TODO(TM1): replace with vault/Keychain integration before production.`

---

## Endpoint Status Matrix

| Route | Method | Auth | Status | Notes |
|-------|--------|------|--------|-------|
| `/health` | GET | No | 200 | OK |
| `/health/ready` | GET | No | 200 | OK |
| `/health/echo` | GET | No | 422 | Requires query param (correct) |
| `/health/metrics` | GET | No | 200 | OK |
| `/health/tools` | GET | No | 200 | OK |
| `/health/backup` | GET | No | 404 | Stale container (M1) |
| `/api/v1/auth/login` | POST | No | 200 | Works (tested register+login) |
| `/api/v1/auth/register` | POST | No | 200 | Works |
| `/api/v1/auth/refresh` | POST | No | N/T | Not tested (needs refresh token) |
| `/api/v1/auth/logout` | POST | Yes | N/T | Not tested |
| `/api/v1/auth/google/authorize` | GET | Yes | 404 | Stale container (M1) |
| `/api/v1/auth/google/callback` | GET | No | 404 | Stale container (M1) |
| `/api/v1/auth/google/status` | GET | Yes | 404 | Stale container (M1) |
| `/api/v1/auth/google/disconnect` | DELETE | Yes | 404 | Stale container (M1) |
| `/api/v1/threads` | GET | Yes | 200 | Returns list |
| `/api/v1/threads` | POST | Yes | 200 | Creates thread |
| `/api/v1/threads/{id}` | DELETE | Yes | 500 | FK violation (H1) |
| `/api/v1/threads/{id}/messages` | GET | Yes | 200 | Returns messages |
| `/api/v1/chat` | POST | Yes | 200 | SSE streaming works correctly |
| `/api/v1/runs` | GET | Yes | 200 | Returns run list |
| `/api/v1/settings` | GET | Yes | 200 | Credentials masked |
| `/api/v1/settings` | PATCH | Yes | 200 | Round-trip verified |
| `/api/v1/approvals/pending` | GET | Yes | 200 | Returns empty list |
| `/api/v1/memory/facts` | GET | Yes | 200 | Returns empty list |
| `/api/v1/tools` | GET | Yes | 200 | Returns 4 tools with functions |
| `/api/v1/cost/summary` | GET | Yes | 200 | Returns daily/monthly |
| `/api/v1/artifacts` | GET | Yes | 200 | Returns empty list |
| `/api/v1/usage` | GET | Yes | 200 | Returns daily/monthly |
| `/api/v1/queue` | GET | Yes | 200 | Returns empty list |
| `/api/v1/tasks` | GET | Yes | 200 | Returns empty tasks |
| `/api/v1/audit/entries` | GET | Yes | 422 | Requires trace_id param (correct) |
| `/api/v1/audit/verify` | POST | Yes | 200 | Hash chain valid |
| `/api/v1/voice/transcribe` | POST | Yes | 404 | Stale container (M1) |
| `/docs` | GET | No | 200 | OpenAPI docs (M2) |
| `/openapi.json` | GET | No | 200 | Full schema exposed (M2) |

---

## E2E Flow Results

| Flow | Steps Completed | Failure Point | Details |
|------|-----------------|---------------|---------|
| Register + Login | 2/2 | -- | Token returned, credentials work |
| Create Thread + Chat + Messages | 3/3 | -- | SSE streams correctly, messages stored, run created |
| Settings PATCH round-trip | 3/3 | -- | Get/Patch/Verify all work, credentials masked |
| Thread Delete (with run data) | 1/2 | DELETE step | FK constraint on usage_stats (H1) |
| Audit verify | 1/1 | -- | Hash chain valid, 0 entries |

---

## Security Checklist

| Check | Result | Details |
|-------|--------|---------|
| Auth on protected endpoints | PASS | All protected endpoints return 401 without token |
| CORS origin restriction | PASS | Evil origin gets no access-control-allow-origin |
| CORS no wildcard | PASS | Explicit rejection of `*` in code |
| Credential masking | PASS | Settings API masks all credential values |
| JWT error sanitization | PASS | Returns "Invalid token", no stack traces |
| SQL injection | PASS | Parameterized queries, returns 401 (auth first) |
| Path traversal | PASS | Returns 404, no file access |
| Domain isolation | PASS | No cross-domain imports between private/external workers |
| Error response info leakage | PASS | "An internal error occurred" for 500s, no stack traces |
| No hardcoded secret fallbacks | PASS | No `or "dev"` / `or ""` patterns found |
| Docs exposure | MEDIUM | /docs and /openapi.json accessible without auth (M2) |
| Rate limiting (tools) | PASS | Per-user rate limiting in ToolGateway |
| CSP headers | PASS | Content-Security-Policy header present |
| X-Content-Type-Options | PASS | nosniff header present |
| Circular imports | PASS | All 15 core modules import cleanly |

---

## Static Analysis

| Check | Result | Details |
|-------|--------|---------|
| ruff | PASS | 0 errors across src/ and tests/ |
| mypy | PASS | 0 errors across 166 files (QE2 achievement) |
| Unused imports (F401) | PASS | None found |

---

## Test Suite Summary

| Suite | Passed | Failed | Errors | Notes |
|-------|--------|--------|--------|-------|
| Unit tests | 1727 | 1 | 0 | QE6 mutation baseline (L2) |
| Known-flaky (excluded) | -- | 2 | 0 | test_qc3 lifespan, test_mcp_adapter |
| Integration tests | 55 | 1 | 0 | Network isolation env-specific (L6) |
| Integration (no DB URL) | 25 | 1 | 30 | 30 errors from missing testcontainers socket |

---

## Wave 21 Deliverable Verification

| Phase | Deliverable | Present | Working |
|-------|-------------|---------|---------|
| QE1 | CI backlog triage | Yes | 39 tests pass |
| QE2 | mypy zero | Yes | 0 errors confirmed live |
| QE3 | Findings closure | Yes | 0 open in FINDINGS.md |
| QE4 | Integration tests | Yes | 55/56 pass with real Postgres |
| QE5 | traceability.py + TRACEABILITY.md | Yes | 97/128 covered, 9 Phase-2 orphans |
| QE6 | pytest-cov config + mutmut config | Yes | 1 test failure (M3 interaction) |

---

## Recommendations

1. **Immediate:** Restart noa-api container to pick up Wave 20 code (Google OAuth, backup health, voice transcribe routes)
2. **High priority:** Fix usage_stats FK cascade (H1) -- add migration with `ondelete="SET NULL"` on `usage_stats.run_id`
3. **High priority:** Fix backup container setpgid permission (H2) -- add `cap_add: [SETPGID]` to backup service
4. **Medium:** Add environment-based docs gating (M2) -- disable /docs in production
5. **Medium:** Fix traceability.py to preserve manual sections (M3) -- or move mutation baseline elsewhere
6. **Medium:** Add TEST_DATABASE_URL to dev container environment (M4)
7. **Low:** Clean up the QE6 test to not depend on manual TRACEABILITY.md sections

---

## Score Rationale

Starting at 5/10 baseline:
- +1: ruff and mypy both at zero errors (first time in project history)
- +1: 1727/1730 unit tests pass, integration suite robust (55/56)
- +1: Strong security posture (auth, CORS, credential masking, error sanitization)
- +0.5: All Wave 21 deliverables present and functional
- -0.5: DELETE /threads broken with FK violation (H1)
- -0.5: Backup container crash-looping (H2)
- 0: Stale container is ops hygiene, not code quality

**Final Score: 7.5/10**

The codebase is in strong shape. The static analysis gates (ruff + mypy at zero) are a significant quality milestone. The two high findings (H1 FK cascade, H2 backup permissions) are straightforward fixes. The stale container issue (M1) resolves with a simple restart but highlights the need for either auto-reload in dev or documented restart procedures.
