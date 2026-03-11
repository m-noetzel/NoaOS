# QA Review Agent Memory

## Project: NoaOS

### How to Run Tests
```bash
source .venv/bin/activate && python3 -m pytest tests/unit/test_NAME.py -v --override-ini="pythonpath=src"
```
Note: `--override-ini="pythonpath=src"` needed to avoid langsmith pydantic_core crash.

### Recurring Anti-Patterns (most important)

**"Read-path scoped, write-path unscoped" (PR1):** PR1 added user_id filtering to MemoryStore read methods (list_all, get_by_id, update_status, delete) but store() -- the write path -- never sets user_id. Facts stored via orchestrator are invisible to the user-scoped API. Always check BOTH read and write paths when adding access control.

**"Wired in class, not at startup" (QC5/QC8):** Implementation exists but never connected in app.py. Tests pass because they inject manually. After review, grep app.py for new class names.

**"Wired at startup, hooks log but never call" (iOS1):** Service instantiated, hooks exist, but hooks only log and never call the external service. Verify ENTIRE call chain.

**"Wired at startup, never called in run()" (HD):** Dependency injected but consuming code never invokes it.

**Half-fixes on security findings (QC2):** Backend fixed but frontend untouched. Tests exist but don't cover the finding.

**Making sync methods async breaks existing tests (QC5):** Always run full test suite, not just phase tests.

**Module re-export breaks patch targets (QC4):** Moving a module leaves old test patches silently missing.

**Missing migration pattern (C4, TM2):** Column added to ORM model but no alembic migration. Tests pass via create_all.

**flush-without-commit:** get_db_session does NOT auto-commit. Every write endpoint needs session.commit().

### Security Checks (run every review)
1. `except Exception:` blocks -- pre-existing or new? Do they log?
2. Domain isolation: no cross-domain imports
3. user_id filtering on ALL endpoints in a file (not just some)
4. No unsafe fallback defaults (`or ""`, `or "dev"` on secrets)
5. Wiring: new services instantiated in app.py startup

### Pre-existing Violations (not new-phase blockers)
- `auth.py:179`: `except Exception: pass` in logout (noqa BLE001+S110)
- `chat.py:211`: `except Exception:` in _make_run_service -- does rollback, no log
- Pre-existing test failures: test_orchestrator, test_mr8, test_mr9, test_cp4 (langgraph)
- Pre-existing frontend failures: qc7-fixes.test.tsx UI-M8 (2 tests, settings freshness SSE mock issue)
- threads.py:45 E501 ruff violation (line too long, not in PR1)

### Phase Review Notes (see topic files for iOS details)
- **iOS reviews:** See `ios-reviews.md`
- **System-Final (2026-03-10):** FAIL then PASS_WITH_NOTES. AuthUser migration orphaned callers. Approval IDOR. Push pipeline decorative.
- **TM1/TM2 (2026-03-11):** Both PASS_WITH_NOTES. Missing migration 009. Stub probes. In-memory credential store.
- **PR1 (2026-03-11):** PASS_WITH_NOTES. 19 tests. Runs join usage_stats. Memory user-scoped. RunService async. Gap: store() lacks user_id.
- **PR2 (2026-03-11):** PASS_WITH_NOTES. 10 tests. PATCH settings endpoint, Chat thread race fix (mutateAsync), RunDetail type cast removal. 4 ruff violations in test file. No non-mocked integration test. FINDINGS.md now 7 entries stale.

### Infrastructure Security Baseline (2026-03-07)
- Claude Code: 107 allow rules, all scoped. Deny blocks dangerous patterns.
- Docker: No root user, no privileged, no secrets in ENV.
- CORS: Explicit localhost origins, wildcard rejected.
- Secrets: .env/.env.secrets gitignored. Only .env.example tracked.
- Deps: Loose >= pins with upper bounds. No lockfile.

### File Paths
- Reviews: `Plan/REVIEWS/review_{phase-id}.md`
- Health briefs: `Plan/REVIEWS/health_{date}.md`
- QA Checklist: `Plan/QA_CHECKLIST.md`
- Arch Invariants: `Plan/ARCH_INVARIANTS.md`
