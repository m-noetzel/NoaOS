# Wave 21 Findings Recheck — 2026-03-12

Targeted verification of 4 findings from the Wave 21 system audit.

---

## H1: DELETE /threads/{id} FK cascade — FIXED

| Check | Result |
|-------|--------|
| `usage.py` has `ondelete="SET NULL"` on `run_id` FK | PASS (line 38) |
| Migration `012_usage_stats_run_id_on_delete_set_null.py` exists | PASS |
| Migration uses `batch_alter_table` for SQLite compat | PASS |
| Unit tests pass (`test_audit_fixes.py::TestDeleteThreadFKCascade`) | PASS (2/2) |
| Live HTTP DELETE on running server | NOT TESTED — server is stale (see M1) |

**Verdict: FIXED** (code + migration + tests all correct; live verification blocked by stale container)

---

## H2: Backup container cap_add — PARTIAL

| Check | Result |
|-------|--------|
| `docker-compose.yml` has `cap_add: [SETPGID]` for backup | PASS |
| Container runtime has `cap_add` applied | FAIL — `docker inspect` shows `CapAdd: null` |
| Container status | FAIL — `Restarting (1)`, still crash-looping |
| Crash log | `setpgid: Operation not permitted` (repeated) |

**Root cause:** The `docker-compose.yml` change has not been applied to the running container. The container was never recreated after the compose file was updated. Need `docker compose up -d --force-recreate backup` (or full `docker compose up -d`).

Additionally, `no-new-privileges:true` in `security_opt` may conflict with `SETPGID`. The `no-new-privileges` seccomp policy can block `setpgid()` syscalls even when the capability is granted. This needs investigation — the cap_add alone may not be sufficient.

**Verdict: PARTIAL** (compose config correct, but container not recreated; may need further fix if no-new-privileges blocks setpgid)

---

## M1: Stale container — routes still 404 — STILL OPEN

| Check | Result |
|-------|--------|
| `GET /health/backup` | 404 |
| `GET /api/v1/auth/google/authorize` | 404 |
| Routes exist in code (fresh `create_app()`) | PASS — both `/health/backup` and all 4 Google OAuth routes register |
| Running server serves these routes | FAIL — stale uvicorn process |

The user stated "it was just restarted" but the running uvicorn process is still serving the old route table. The routes register correctly when `create_app()` is called fresh (verified via `PYTHONPATH=/workspace/src python -c "from noa.api.app import create_app; ..."`), but the actual running server does not have them.

This means either:
1. The container was restarted but loaded stale site-packages (not `/workspace/src`)
2. The restart did not actually occur, or uvicorn cached the old app

**Verdict: STILL OPEN** (routes exist in code but not in the running server; needs full container rebuild with `pip install -e .` or `PYTHONPATH=/workspace/src` in the entrypoint)

---

## M2: OpenAPI docs gating — FIXED

| Check | Result |
|-------|--------|
| `app.py` gates `docs_url`/`redoc_url`/`openapi_url` on `ENVIRONMENT` | PASS (lines 372-381) |
| Production: all three set to `None` | PASS |
| Non-production: all three set to defaults | PASS |
| `/docs` returns 200 in dev container | PASS |
| Unit tests pass (`test_audit_fixes.py::TestOpenAPIDocGating`) | PASS (3/3) |

**Verdict: FIXED**

---

## M3: traceability.py sentinel preservation — FIXED

| Check | Result |
|-------|--------|
| `tools/traceability.py` has sentinel preservation logic | PASS (lines 365-377) |
| `Plan/TRACEABILITY.md` contains `<!-- MANUAL SECTIONS -->` sentinel | PASS (line 174) |
| Manual section survives two consecutive runs | PASS (baselines table intact after double-run) |
| Unit tests pass (`test_qe5_traceability.py::TestSentinelPreservation`) | PASS (3/3) |

**Verdict: FIXED**

---

## Summary

| Finding | Severity | Verdict |
|---------|----------|---------|
| H1: DELETE /threads FK cascade | HIGH | **FIXED** |
| H2: Backup container cap_add | HIGH | **PARTIAL** (compose correct, container not recreated; potential no-new-privileges conflict) |
| M1: Stale container routes | MEDIUM | **STILL OPEN** (routes in code, not in running server) |
| M2: OpenAPI docs gating | MEDIUM | **FIXED** |
| M3: Traceability sentinel | MEDIUM | **FIXED** |

**3 of 5 FIXED, 1 PARTIAL, 1 STILL OPEN.**

The two remaining items (H2, M1) are both deployment/operations issues, not code issues. The code changes are correct in all cases. Resolution requires:
- H2: `docker compose up -d --force-recreate backup` + investigate `no-new-privileges` vs `setpgid` conflict
- M1: Full container rebuild or entrypoint fix to use `PYTHONPATH=/workspace/src`
