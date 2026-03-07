# QA Review: Phase QC3

**Date:** 2026-03-07
**Verdict:** FAIL
**Reviewer:** qa-review agent

## Checklist Score
**Must-haves:** 7/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All test classes cite FINDINGS.md findings and ARCH_INVARIANTS.md §L9. No orphan tests. |
| M2 | Negative Tests | PASS | Error paths tested: 401 on missing/empty/non-UUID sub, 500 on DB error, CalledProcessError on non-zero exit, TimeoutExpired on long script. |
| M3 | Security Boundaries | PASS | M13 env whitelist prevents os.environ leakage. M11 AuthUser validates UUID at middleware boundary. No hardcoded secrets. Auth cookies correctly set httpOnly/Secure/SameSite=Strict. |
| M4 | Determinism | PASS | No wall-clock time in test assertions. No network calls. No unseeded randomness. |
| M5 | Implementation Completeness | PASS | All listed deliverables present: AuthUser dataclass, SettingsRepository no-commit, cost 500 on DB error, backup check=True + env whitelist, circular import fix via base.py. |
| M6 | No Silent Error Swallowing | FAIL | `src/noa/api/v1/chat.py:163` — inner `except Exception:` catches broad exception, calls `session.rollback()` only, no log statement, no re-raise. Violates ARCH_INVARIANTS.md L9 rule 2. No test covers this path. |
| M7 | Wiring Completeness | PASS | `cost_router` registered at `app.py:322`. `AuthUser` flows through all auth-dependent endpoints. No orphaned code. |
| M8 | Domain Isolation | PASS | Pre-existing violations (`external_worker/llm/router.py:114`, `private_worker/ollama_client.py:13`) noted as tracked. No new violations introduced by QC3. |
| S1 | Error Handling & Boundaries | PASS | UUID edge cases (empty, uppercase, non-UUID) all tested. CalledProcessError includes stderr. |
| S2 | Code Consistency | OPEN | `backup.py:112`: `_SAFE_KEYS` inside function violates naming convention (N806). Minor: `chat.py:58` declares `user: dict[str, Any]` but `require_auth` now returns `AuthUser` — type annotation lie. |
| S3 | Migration & Rollback | N/A | No DB schema changes in QC3. |
| S4 | Documentation | PASS | All new functions have docstrings. `AuthUser` fields annotated. |
| S5 | Integration Smoke Test | PASS | `TestQC3Integration.test_settings_upsert_persists_via_caller_commit` uses real SQLAlchemy + aiosqlite. Non-mocked. |

---

## Spec Compliance

Checked ARCH_INVARIANTS.md L9 (Exception Handling), L1 (Layering), L11 (Security Defaults).

- **L9 rule 2**: "No `except Exception: pass`. If you catch a broad exception, you must log it (with `trace_id`) or re-raise." — VIOLATED at `chat.py:163`. The inner except inside `_make_run_service` catches `Exception`, calls `session.rollback()`, and returns `svc` — no log, no re-raise. The `noqa: BLE001` suppresses the ruff rule, hiding the invariant violation from static gates.
- **L9 rule 1**: No bare `except:` — PASS, none found.
- **L9 rule 3**: No success responses on error — PASS for all QC3 changes.
- **L11**: AuthUser enforces UUID validation at middleware boundary — PASS.
- **H4**: `SettingsRepository.upsert()` no longer calls `session.commit()` — PASS.
- **M11**: `require_auth` returns `AuthUser` with validated `uuid.UUID` user_id — PASS.
- **M13**: `run_backup_script` uses `check=True`, env whitelist prevents leakage — PASS (with ruff warning noted below).

---

## Test Coverage

| Test Class | Finding Covered | Spec Reference | Coverage Quality |
|---|---|---|---|
| TestSettingsRepositoryTransactionBoundary | H4 | ARCH_INVARIANTS L1 | Good — 3 tests, includes rollback atomicity |
| TestExceptionHandlingQuality | H5 | ARCH_INVARIANTS L9 | Gap: test_lifespan_db_skip_emits_warning tests `create_app()`, not `lifespan()` — lifespan body never executed |
| TestCostEndpointErrorCodes | M8 | L9 rule 3 | Good — 500 on DB error, 200 on no-factory |
| TestAuthUserExtraction | M11 | ARCH_INVARIANTS L11 | Good — 8 tests cover UUID parsing edge cases |
| TestBackupScriptSafety | M13 | SPEC §10.5 | Good — 6 tests cover error propagation and env safety |
| TestQC3Imports | smoke | all modules | Good |
| TestQC3Integration | H4/S5 | H4 + QA_CHECKLIST S5 | Excellent — real SQLAlchemy + aiosqlite |

**Coverage gap — M6 inner except untested:** `_make_run_service` at `chat.py:163` catches a `create_run()` exception but only rolls back without logging. No test verifies this path, and the path violates L9 rule 2.

**Test correctness gap — `test_lifespan_db_skip_emits_warning`:** The test patches `create_async_engine_from_config` and imports `app`, then checks `caplog.records`. However, the lifespan context manager is an `asynccontextmanager` — it only runs when the ASGI server starts, not on import. The warning captured comes from the `create_app()` eager-check block (lines 244-253), **not from the lifespan block** (lines 148-152). The lifespan DB-skip path is not actually tested. The test passes vacuously and its docstring is misleading.

---

## Anti-Pattern Scan Results

```
# M6: Bare except blocks
$ grep -rn "except:" src/noa/api/ src/noa/auth/ src/noa/settings/ src/noa/maintenance/ src/noa/db/
No bare except found

# M6: except Exception: (QC3-touched files)
$ grep -rn "except Exception:" src/noa/api/v1/cost.py src/noa/api/v1/chat.py src/noa/api/app.py ...
src/noa/api/v1/chat.py:163:            except Exception:  # noqa: BLE001
  -> VIOLATION: no log or re-raise (L9 rule 2). Pre-existing but untouched by QC3.
src/noa/api/v1/chat.py:166:        except Exception:  # noqa: BLE001
  -> OK: logger.debug(..., exc_info=True) follows. Fixed by QC3.
src/noa/api/v1/chat.py:213:    except Exception:  # noqa: BLE001
  -> OK: logger.warning(...) follows.
src/noa/api/app.py:56,113,125,148,217,249: all have logger.warning following. OK.

# M7: Wiring
$ grep -n "include_router" src/noa/api/app.py | grep "cost_router"
322:    app.include_router(cost_router)   -> PASS

# M8: Domain isolation
src/noa/external_worker/llm/router.py:114: pre-existing violation (tracked, not introduced by QC3)
src/noa/private_worker/ollama_client.py:13: pre-existing violation (tracked, not introduced by QC3)
```

---

## Smoke Test Results

```
$ source .venv/bin/activate && python3 -c "
from noa.settings.repository import SettingsRepository  # OK
from noa.api.v1.cost import router as cost_router       # OK
from noa.api.v1.chat import router as chat_router       # OK
from noa.api.v1.settings import router as settings_router  # OK
from noa.api.v1.auth import router as auth_router       # OK
from noa.auth.middleware import require_auth, AuthUser  # OK
from noa.maintenance.backup import run_backup_script    # OK
from noa.db.models.base import Base                     # OK
from noa.db.models import Base as BaseFromInit          # OK
import uuid
u = AuthUser(user_id=uuid.UUID('550e8400-e29b-41d4-a716-446655440000'))
# AuthUser(user_id=UUID('550e8400-e29b-41d4-a716-446655440000'), session_id=None)
"
# All imports OK. AuthUser construction OK.

# require_auth runtime test — empty sub:
# await require_auth(sub='') -> HTTP 401  (OK)

# All 26 QC3 tests: PASS (1.34s)
# All 43 backup + mr1 auth tests: PASS
```

---

## Security

**No new vulnerabilities introduced.** Positive improvements:

1. `AuthUser` with validated `uuid.UUID` user_id eliminates the `uuid.UUID('')` crash path.
2. `run_backup_script` env whitelist prevents `SECRET_KEY`, `DATABASE_URL`, and other secrets from leaking to subprocess.
3. Login/refresh/logout endpoints now use httpOnly cookies (C6 fix from QC2 preserved).
4. CORS wildcard filter preserved (QC2).

**Residual concern (pre-existing, not QC3-introduced):** `auth.py:179` — `except Exception: pass` in logout best-effort path. The `# noqa: BLE001, S110` suppresses both ruff rules. This was pre-existing before QC2 and QC3. Not blocking for this phase.

---

## Code Quality

1. **`backup.py:112` — N806 naming violation:** `_SAFE_KEYS` is a module-level constant style name inside a function scope. Ruff N806 rule fires: "Variable in function should be lowercase." The fix is to move it to module scope or rename to `_safe_keys`. This is an **active ruff static gate failure** — `ruff check src/` exits non-zero (`Found 8 errors`, with the new N806 introduced by QC3). **This blocks the merge gate.**

2. **`chat.py:58` — Type annotation mismatch:** `user: dict[str, Any] = Depends(require_auth)` — `require_auth` now returns `AuthUser`, not `dict`. Same issue in `settings.py:42,57`. The runtime code adapts via `hasattr(user, 'user_id')` checks, but the type annotation is wrong. Not blocking (annotation lie, not runtime bug), but mypy would flag it.

3. **`_extract_user_id` legacy dict fallback in `cost.py:31`:** The legacy dict path `user.get('user_id', user.get('sub', ''))` followed by `uuid.UUID(raw)` would raise `ValueError` if `sub` is not a valid UUID. In production this is prevented by `require_auth` validating first, but the code is defensive-depth fragile. Non-blocking.

4. **Ruff pre-existing errors (not introduced by QC3):** 7 other errors in `src/` (`F401` in `audit.py`, `I001` in `runs.py`, multiple `S105`-equivalent in worker files). These pre-date QC3.

---

## Blocking Issues

1. **`src/noa/maintenance/backup.py:112` — N806 ruff error breaks static gate.**
   QC3 introduced `_SAFE_KEYS = {"PATH", "HOME", ...}` as a function-local variable with a UPPER_SNAKE_CASE name. Ruff rule N806 ("Variable in function should be lowercase") fires, causing `ruff check src/` to exit non-zero. The CLAUDE.md merge gate requires `ruff check` to pass. This is a new failure introduced by QC3.
   **Fix:** Move `_SAFE_KEYS` to module scope (above `run_backup_script`) or rename to `_safe_keys` inside the function.

2. **`src/noa/api/v1/chat.py:163` — Silent exception swallowing violates ARCH_INVARIANTS.md L9 rule 2.**
   The inner `except Exception:` inside `_make_run_service` catches a `create_run()` exception, calls `session.rollback()`, and returns `svc` — with no log statement and no re-raise. L9 rule 2 states: "If you catch a broad exception, you must log it (with `trace_id`) or re-raise." The `noqa: BLE001` suppresses the linter rule but does not excuse the invariant violation. No test covers this path.

   Note: This block is **pre-existing** (present in `d191701` commit, before QC3). QC3's stated scope was "H5 — bare `except: pass` blocks" and it correctly fixed the outer `except Exception: pass` at line 159 (pre-QC3) by adding `logger.debug(...)`. However, the inner `except` at line 163 remains an L9 violation that QC3 left unaddressed despite being in a file QC3 modified. Since QC3 touched this file and H5 is a QC3 deliverable, this residual violation falls within QC3's responsibility.
   **Fix:** Add `logger.debug("create_run failed, rolling back", exc_info=True)` before `session.rollback()` on line 164.

---

## Notes

1. **`test_lifespan_db_skip_emits_warning` is misleading.** It claims to test the lifespan DB-skip path but actually tests the `create_app()` eager-check block. The lifespan `asynccontextmanager` body is never invoked by the test. The test passes but does not verify the intended behavior. The lifespan DB-skip path (`app.py:148-152`) is untested. Low priority — the `create_app()` path does exercise the same WARNING log intent.

2. **Type annotation inconsistency in `chat.py`, `settings.py`.** After M11 changes, `user: dict[str, Any] = Depends(require_auth)` should be `user: AuthUser = Depends(require_auth)`. The runtime `hasattr` guards work, but annotating correctly would allow mypy to catch future regressions.

---

## Decision Review

No `Plan/DECISION_LOG.md` exists. Cannot review documented decisions. This is a pre-existing process gap — not introduced by QC3.
