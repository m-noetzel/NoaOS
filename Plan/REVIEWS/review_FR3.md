# QA Review: Phase FR3

**Date:** 2026-03-13
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)
**Cycle:** 1

## Checklist Score
**Must-haves:** 11/11 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Module docstring cites SPEC.md §10.1, §28.7, §20.1. Each finding (W21-H1, W21-H2, W21-M1, W21-M2) has a dedicated test class. |
| M2 | Negative Tests | PASS | Negative tests: 404 on /openapi.json in production (test_openapi_endpoint_returns_404_in_production), docs suppressed when NOA_ENV=production or ENVIRONMENT=production, --check does not overwrite file. |
| M2b | Write-Path Test Fidelity | PASS | TestDeleteThreadWithData verifies DB state post-delete via real SQLite session.execute(select(Conversation)); not a vacuous mock round-trip. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. test-secret is a test-only dummy set via monkeypatch.setenv (not committed). OpenAPI gating is correctly default-deny in production. |
| M3b | Write-Path User Scoping | PASS | No new write paths added. Existing UsageStats and Run writes already include user_id. |
| M4 | Determinism | PASS | No wall-clock assertions. No network calls. uuid4() used only for unique IDs, not seeded randomness. All 14 tests pass consistently. |
| M4b | Mock Interface Accuracy | PASS | Tests use real AsyncSession via ASGI TestClient + in-memory SQLite. No mock misuse. |
| M5 | Implementation Completeness | PASS | All 4 planned deliverables present: migration 015, app.py NOA_ENV gating, traceability.py --check mode, docker-compose.yml backup fix. FINDINGS.md updated (W21-H1/H2/M1/M2 all Resolved by FR3). |
| M5b | Findings Currency | PASS | W21-H1, W21-H2, W21-M1, W21-M2 all marked Resolved by FR3 in worktree's FINDINGS.md. Open count updated to 34. |
| M6 | No Silent Error Swallowing | PASS | No new bare except blocks. Migration files have no exception handling. traceability.py uses specific OSError/ValueError catches. |
| M7 | Wiring Completeness | PASS | No new routers or services created. docs_url/redoc_url/openapi_url gating is directly in create_app(). |
| M8 | Domain Isolation | PASS | No cross-domain imports. Grep confirmed no noa.private_worker imports in external_worker and vice versa. |
| S1 | Error Handling & Boundaries | PASS | boundary conditions covered: ENVIRONMENT=production (legacy var), NOA_ENV=development (allow), check_mode=True with None output, check_mode=True with manual sentinel sections. |
| S2 | Code Consistency | OPEN | traceability.py line 277 uses `datetime.utcnow()` which is deprecated in Python 3.12+ and triggers DeprecationWarning in tests. Pre-existing issue, not introduced by FR3, but touched file inherits the warning. |
| S3 | Migration & Rollback | PASS | Migration 015 has downgrade() that restores the FK without ondelete (reverting to default behavior). |
| S4 | Documentation | PASS | Migration has detailed docstring explaining why 015 exists alongside 012 (Postgres DuplicateObject edge case). app.py gating has clear comments citing W21-M1 and the env var hierarchy. |
| S5 | Integration Smoke Test | PASS | TestDeleteThreadWithData uses real ASGI TestClient + in-memory SQLite (no mocked internals). This is a non-mocked integration path that tests the actual cascade behavior end-to-end. |

## Spec Compliance

**SPEC.md §10.1 (Threads/Conversations):** DELETE /threads cascades correctly — runs → usage_stats chain verified. ORM model has `ondelete="CASCADE"` on runs.thread_id and `ondelete="SET NULL"` on usage_stats.run_id. Behavioral test confirms 200 response even with a run+usage_stats row present.

**SPEC.md §20.1 (Security):** OpenAPI docs gated behind NOA_ENV. Both `NOA_ENV=production` and `ENVIRONMENT=production` (legacy) suppress docs_url, redoc_url, and openapi_url. Verified by HTTP client (404 on /openapi.json in production mode).

**SPEC.md §8.1 (Container hardening, exemption):** Backup service is exempt from cap_drop per the exemption noted in the compose file. `dcron` requires SETUID/SETGID to fork cron jobs. `init: true` added to prevent crond becoming PID 1.

**SPEC.md §28.7 (Data integrity):** usages_stats.run_id FK SET NULL correctly prevents cascade-delete 500. No data loss on thread deletion.

## Test Coverage

| Test | Spec Requirement | Negative? |
|------|-----------------|-----------|
| test_delete_thread_with_run_succeeds | W21-H1 / §10.1 DELETE cascade | Integration path |
| test_delete_thread_with_usage_stats_succeeds | W21-H1 / §28.7 data integrity | Integration path + DB state verify |
| test_usage_stats_fk_model_has_set_null | W21-H1 ORM model verification | Model inspection |
| test_migration_015_exists | W21-H1 migration exists | File existence |
| test_backup_service_has_no_cap_drop_all | W21-H2 / §8.1 container config | Config inspection |
| test_backup_service_has_init_true | W21-H2 / §8.1 PID 1 fix | Config inspection |
| test_docs_hidden_when_noa_env_production | W21-M1 / §20.1 | NEGATIVE |
| test_docs_visible_when_noa_env_development | W21-M1 positive path | Positive |
| test_docs_hidden_when_environment_production | W21-M1 legacy var | NEGATIVE |
| test_openapi_endpoint_returns_404_in_production | W21-M1 HTTP 404 | NEGATIVE HTTP |
| test_check_mode_does_not_write_output_file | W21-M2 no-overwrite | NEGATIVE write |
| test_check_mode_none_output_still_works | W21-M2 None path | Boundary |
| test_non_check_mode_writes_file | W21-M2 normal mode unchanged | Positive |
| test_check_mode_preserves_manual_sections | W21-M2 sentinel preservation | NEGATIVE modify |

**Gap:** `test_migration_015_exists` verifies the file exists but does NOT verify that migration 014 (the prerequisite) also exists in the worktree. Running `alembic history` in the worktree crashes with `KeyError: '014'` because migration 014 was added to main by FR1 after this worktree was branched. Tests pass because they use `Base.metadata.create_all` (not alembic), so the broken chain never surfaces in the test suite.

## Anti-Pattern Scan Results

**M6 — bare except blocks:**
```
grep 'except:' src/noa/api/app.py: no results
grep 'except:' alembic/versions/015_cascade_thread_delete.py: no results
grep 'except:' tools/traceability.py: no results
```
No new bare except blocks introduced.

**M7 — router registration:**
```
app.include_router(health_router)        ✓
app.include_router(auth_router)          ✓
app.include_router(threads_router)       ✓
... (all routers registered)
```
No new router added — wiring complete.

**M8 — domain isolation:**
```
grep 'from noa.private_worker' src/noa/external_worker/: no results
grep 'from noa.external_worker' src/noa/private_worker/: no results
```
No violations.

## Smoke Test Results

```
PASS: docs gated in production mode
PASS: docs visible in development mode
PASS: UsageStats.run_id FK ondelete=SET NULL
PASS: Run.thread_id FK ondelete=CASCADE
PASS: traceability --check does not overwrite file

Migration presence: 014=MISSING, 015=PRESENT
WARNING: Migration 014 missing from worktree — chain BROKEN (015 references 014 as down_revision)
When merging to main (which has 014), alembic chain will be reconstructed correctly.
```

```
# Full test suite (FR3 file):
============================= 14 passed, 4 warnings in 0.57s ============================
```

```
# ruff check (FR3 test file):
All checks passed!
```

```
# ruff check src/:
5 pre-existing violations (E501 in tools.py:46-47, openai.py:77; BLE001 in test_qc3)
None introduced by FR3.
```

```
# mypy:
1 pre-existing error: src/noa/orchestrator/nodes/agent.py:122 — arg-type (not FR3)
```

```
# alembic history (in worktree):
KeyError: '014' — CRASH
Migration 015 references down_revision="014" but 014 not in worktree.
Will be resolved when FR3 branch is merged to main (which has 014_conversation_domain_column.py).
```

## Security

- No hardcoded secrets. `"test-secret"` is a test-only dummy injected via `monkeypatch.setenv`.
- OpenAPI docs correctly default to disabled in production (default-deny principle per L11).
- `NOA_ENV` check at call time in `create_app()`, not module import — no caching issue.
- Backup service no longer has `cap_drop: ALL` — dcron requires SETUID/SETGID to fork cron jobs.
- No new security boundaries introduced or violated.

## Code Quality

1. `datetime.utcnow()` on traceability.py:277 — deprecated in Python 3.12+, triggers DeprecationWarning in tests. Pre-existing in the file; recommend fixing to `datetime.now(UTC)` in a follow-up.
2. Migration 015 is semantically redundant with migration 012 (both set `usage_stats.run_id ON DELETE SET NULL`). The difference is `recreate="always"` in 015, intended to handle Postgres FK naming edge cases. The comment in 015 explains this clearly but the real-world benefit is unclear given 012 already applies the same constraint.
3. `test_migration_015_exists` would be stronger if it also verified `014_conversation_domain_column.py` exists (chain integrity), not just 015.
4. `test_check_mode_none_output_still_works` asserts only `isinstance(result, int)` — it will pass even if `run()` returns 1 (critical orphans found). This is a weak assertion. The test does not verify the specific exit code.

## Deep Dive

**Migration chain broken in worktree (informational, not blocking for merge):**
Migration 015 references `down_revision="014"`. Migration 014 (`014_conversation_domain_column.py`) was created by FR1, which merged to main after this worktree was branched. As a result, `alembic history` crashes in the worktree with `KeyError: '014'`. However, when FR3 is merged to main, the chain becomes `001→...→013→014→015` and alembic works correctly. The tests are not affected because they use `Base.metadata.create_all`.

**Migration 015 redundancy risk:**
On a fresh production Postgres database that already ran migration 012 (SET NULL), migration 015 will drop and recreate the same FK constraint with identical semantics. This is idempotent but increases migration time and risk surface. On databases that never ran 012 (e.g., a bug caused 012 to fail in a specific deployment), 015 provides a safety net.

**`ENVIRONMENT` fallback: security implication:**
The `ENVIRONMENT=production` check provides backward compatibility. However, if an environment uses both `NOA_ENV=development` and `ENVIRONMENT=production`, the code correctly suppresses docs (OR logic). If `NOA_ENV` is set to anything non-"production", docs are still suppressed only if `ENVIRONMENT=production`. The OR logic is correct and conservative (fail-safe).

**traceability --check still prints "FAIL" to stderr even in test context:**
When `test_check_mode_none_output_still_works` calls `run(output_path=None, check_mode=True)`, the function prints critical orphans to stderr. The test does not capture stderr, so "FAIL — the following critical sections..." will appear in test output. This is cosmetic but could confuse readers of CI logs.

## Notes (PASS_WITH_NOTES)

1. **Migration chain test gap:** `test_migration_015_exists` should also verify that `014_conversation_domain_column.py` exists in the same `alembic/versions/` directory, to catch chain breakage early. Current test only verifies 015's existence.

2. **Weak assertion in test_check_mode_none_output_still_works:** The test asserts `isinstance(result, int)` but not the specific value. If the SPEC coverage degrades and check mode starts returning 1 (failure), this test will still pass. Consider asserting `result == 0` or that a known minimum coverage threshold is met.

3. **Migration 015 + 012 redundancy:** Document explicitly in migration 015's docstring that this migration intentionally re-applies what 012 did, with `recreate="always"` as the Postgres-safe variant. The current comment mentions "DuplicateObject" but could be clearer: "This migration is safe to apply on top of 012 because `recreate='always'` drops and recreates — idempotent."

4. **datetime.utcnow() deprecation:** `tools/traceability.py:277` uses deprecated `datetime.utcnow()`. Causes DeprecationWarning in tests. Should be changed to `datetime.now(UTC)` in a follow-up (not blocking for FR3).

## Decision Review

The four findings targeted (W21-H1, W21-H2, W21-M1, W21-M2) are all correctly addressed:

- **W21-H1:** ORM model has correct `ondelete="SET NULL"` on `usage_stats.run_id` and `ondelete="CASCADE"` on `runs.thread_id`. Migration 015 provides a Postgres-safe application path. Behavioral tests confirm DELETE /threads succeeds with cascaded data.
- **W21-H2:** `cap_drop` removed from backup service; `init: true` added. Compose config tests verify both properties are present.
- **W21-M1:** `create_app()` gates docs_url/redoc_url/openapi_url behind env check. Both `NOA_ENV` and `ENVIRONMENT` vars checked. Tests verify 404 response on /openapi.json in production mode via real ASGI client.
- **W21-M2:** `traceability.py` `run()` function does not write to disk when `check_mode=True`. File sentinel content is preserved.
