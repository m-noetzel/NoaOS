# Wave 21 Findings Recheck (v2) -- 2026-03-12

## Summary

| Finding | Verdict | Details |
|---------|---------|---------|
| H1: DELETE /threads FK cascade | **PARTIAL** | Code + migration correct, but migration 012 NOT applied to live DB (stuck at 009) |
| H2: Backup container crash-loop | **FIXED** | Container stable (0 restarts), no setpgid errors, `init: true` applied |
| M1: Stale routes (health/backup, google/authorize) | **FIXED** | Both routes respond (200 and 401 respectively, not 404) |
| M2: OpenAPI docs gated on environment | **FIXED** | 5/5 tests pass; /docs returns 200 in dev |
| M3: traceability.py sentinel preservation | **FIXED** | 3/3 tests pass; sentinel survives two consecutive runs |

---

## H1: DELETE /threads/{id} FK cascade -- PARTIAL

**Code changes verified:**
- `src/noa/db/models/usage.py` line 38: `ForeignKey("runs.id", ondelete="SET NULL")` -- correct
- `alembic/versions/012_usage_stats_run_id_on_delete_set_null.py` -- exists, valid, uses `batch_alter_table` for SQLite compat

**Unit tests:** 5/5 pass (`test_audit_fixes.py`)
- `test_usage_stats_run_id_has_on_delete_set_null` -- passes (checks ORM metadata)
- `test_delete_thread_returns_200` -- passes (uses in-memory DB with correct schema)

**Live DB status: NOT FIXED**
- `alembic_version` in production postgres: `009`
- Migrations 010, 011, 012 have NOT been applied
- Live `usage_stats` FK: `FOREIGN KEY (run_id) REFERENCES runs(id)` -- no `ON DELETE` clause
- The actual DELETE /threads/{id} bug **still exists in the running system**

**Action required:** Run `alembic upgrade head` against the production database to apply migrations 010-012.

---

## H2: Backup container crash-loop -- FIXED

**docker-compose.yml changes verified:**
- `cap_drop: ALL` removed
- `read_only: true` removed
- `init: true` added (prevents crond PID 1 / setpgid issue)

**Live verification:**
- Container status: `Up 6 minutes`, `running`
- Restart count: 0
- Container logs: empty (no errors)
- `/health/backup` endpoint: returns `200` with valid JSON response

---

## M1: Previously stale routes -- FIXED

**GET /health/backup:**
- Status: `200`
- Response: `{"ok":true,"data":{"status":"never_run",...}}`
- Previously returned 404 due to stale container

**GET /api/v1/auth/google/authorize:**
- Status: `401` (Not authenticated) -- route exists and auth middleware fires
- Previously returned 404 due to stale container
- 401 is correct behavior when called without auth token

---

## M2: OpenAPI docs gated -- FIXED

**Code verified:** `src/noa/api/app.py` lines 372-381:
- `docs_url=None if _is_production else "/docs"`
- `redoc_url=None if _is_production else "/redoc"`
- `openapi_url=None if _is_production else "/openapi.json"`

**Tests:** 5/5 pass (3 doc gating + 2 FK cascade)
- `test_docs_hidden_in_production` -- PASS
- `test_docs_visible_in_development` -- PASS
- `test_docs_visible_when_env_not_set` -- PASS

**Live:** `GET /docs` returns `200` (dev container, ENVIRONMENT != "production")

---

## M3: traceability.py sentinel preservation -- FIXED

**Tests:** 3/3 pass (`test_qe5_traceability.py::TestSentinelPreservation`)
- `test_manual_section_preserved_on_second_run` -- PASS
- `test_no_sentinel_writes_normally` -- PASS
- `test_second_run_does_not_duplicate_generated_content` -- PASS

**Live verification:**
- Ran `tools/traceability.py` twice in succession
- `<!-- MANUAL SECTIONS -->` sentinel present (count: 1, not duplicated)
- Content below sentinel ("Test Quality Baselines (QE6)") preserved after both runs

---

## Environment Note

The noa-api container has a DB password mismatch (`change-me-in-production` vs actual postgres password), causing all DB-dependent endpoints to return 500. This prevented a full live HTTP flow test for H1 (register -> chat -> delete). However, the unit tests adequately test the FK constraint behavior using in-memory DB with the corrected schema. The critical gap is that migration 012 has not been applied to the live database.
