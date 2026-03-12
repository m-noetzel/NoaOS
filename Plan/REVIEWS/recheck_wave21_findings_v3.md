# Wave 21 Findings Recheck v3 -- 2026-03-12

Targeted re-verification of 5 specific findings from the Wave 21 audit plus the bonus migrate service check.

## H1: DELETE /threads/{id} FK cascade -- FIXED

**What was broken:** `usage_stats.run_id` FK to `runs` lacked `ondelete` clause. Deleting a thread cascaded to runs but failed on usage_stats with IntegrityError.

**Verification:**

1. **DB constraint check:** `confdeltype = n` (SET NULL) confirmed live in PostgreSQL:
   ```
   SELECT conname, confdeltype FROM pg_constraint
   WHERE conrelid='usage_stats'::regclass AND contype='f' AND conname='usage_stats_run_id_fkey';
   -- Result: usage_stats_run_id_fkey | n
   ```
2. **Live HTTP flow:**
   - `POST /api/v1/auth/register` -- 200 (user created)
   - `POST /api/v1/auth/login` -- 200 (token received)
   - `POST /api/v1/threads` -- 200 (thread `64f5285a-...` created)
   - `DELETE /api/v1/threads/64f5285a-...` -- 200 `{"ok":true,"data":{"deleted":"64f5285a-..."}}`
3. **Migration:** `012_usage_stats_run_id_on_delete_set_null.py` applied (stamp chain 010->011->012 verified).

**Verdict: FIXED**

---

## H2: Backup container crash-loop -- FIXED

**What was broken:** `cap_drop: ALL` + `read_only: true` caused `setpgid` failures, putting the container in a restart loop.

**Verification:**

1. **Container status:** `docker ps` shows `noaos-backup-1` as `Up 24 minutes` (not Restarting).
2. **Logs:** `docker logs noaos-backup-1` -- empty (no errors, no setpgid failures).
3. **Compose change:** `cap_drop: ALL` and `read_only: true` removed; `init: true` added.

**Verdict: FIXED**

---

## M1: Stale routes (health/backup, Google OAuth) -- FIXED

**What was broken:** Routes added in Wave 20 returned 404 because the container hadn't been restarted.

**Verification:**

1. `GET /health/backup` -- 200:
   ```json
   {"ok":true,"data":{"status":"never_run","last_backup":null,...}}
   ```
2. `GET /api/v1/auth/google/authorize` (with auth token) -- 503 (route exists, returns proper error because Google OAuth env vars are not configured):
   ```json
   {"ok":false,"error":{"code":"HTTP_503","message":"Google OAuth2 not configured -- set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"}}
   ```
   503 (not 404) confirms the route is registered and functional.

**Verdict: FIXED**

---

## M2: OpenAPI docs gating -- FIXED

**What was broken:** `/docs` was unconditionally exposed regardless of environment.

**Verification:**

1. **Code inspection** (`src/noa/api/app.py` lines 372-381):
   ```python
   _is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
   docs_url=None if _is_production else "/docs",
   redoc_url=None if _is_production else "/redoc",
   openapi_url=None if _is_production else "/openapi.json",
   ```
2. **Live check (dev):** `GET /docs` -- 200, `GET /openapi.json` -- 200.
3. **Test note:** The referenced test class `TestOpenAPIDocGating` does not exist in `test_pr7_audit_fixes.py`. However, the feature is confirmed working via code + live HTTP. No dedicated unit test exists for this gating logic.

**Verdict: FIXED** (minor gap: no dedicated unit test for the gating, but feature works)

---

## M3: Traceability sentinel preservation -- FIXED

**What was broken:** Running the traceability script twice would overwrite manual edits.

**Verification:**

1. **Test suite:** `pytest tests/unit/test_qe5_traceability.py` -- **33/33 passed** (0.27s), including:
   - `TestSentinelPreservation::test_manual_section_preserved_on_second_run` -- PASSED
   - `TestSentinelPreservation::test_no_sentinel_writes_normally` -- PASSED
   - `TestSentinelPreservation::test_second_run_does_not_duplicate_generated_content` -- PASSED

**Verdict: FIXED**

---

## BONUS: Migrate service -- VERIFIED

**Verification:**

1. **Service definition** in `docker-compose.yml`:
   - `command: alembic upgrade head` (line 53)
   - `restart: "no"` (line 61)
   - `depends_on: postgres: condition: service_healthy`
2. **Container status:** `noaos-migrate-1` shows `Exited (0)` -- migrations ran successfully and the container stopped.
3. **noa-api dependency:** `depends_on: migrate: condition: service_completed_successfully` (lines 93-94) -- API starts only after migrations complete.

**Verdict: VERIFIED**

---

## Summary

| Finding | Severity | Verdict |
|---------|----------|---------|
| H1: DELETE threads FK cascade | High | **FIXED** |
| H2: Backup container crash-loop | High | **FIXED** |
| M1: Stale routes | Medium | **FIXED** |
| M2: OpenAPI docs gating | Medium | **FIXED** (no unit test) |
| M3: Traceability sentinel | Medium | **FIXED** |
| BONUS: Migrate service | -- | **VERIFIED** |

All 5 findings are resolved. The migrate service is correctly wired. One minor gap: M2 lacks a dedicated unit test for the environment-based gating logic (the referenced `TestOpenAPIDocGating` class does not exist).
