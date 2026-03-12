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

**"Scope reduction without plan update" (DE1):** Phase plan specifies 5 deliverables, only 1 delivered (ci.yml). cd.yml/web-ci.yml/ios-ci.yml all missing. Always compare delivered files against PHASE_DETAILS.md file table, not just "does the one file that exists look correct."

**"CI env points to unreachable service" (DE1):** DATABASE_URL in CI workflow points to postgresql://localhost:5432 but no `services:` block configures a Postgres container. Tests that don't override the URL will fail. Always check that CI env vars point to reachable services.

**"State set but never read" (DE3):** `app.state.workers_degraded` set at startup but no endpoint or middleware reads it. Variant of HD anti-pattern. Always grep for consumers of any state flag being added.

**"Config-only tests miss runtime behavior" (DE1-DE3):** Three consecutive deployment phases validated by parsing YAML/Dockerfile text. No real Docker Compose execution. First real deployment is the actual integration test.

### Security Checks (run every review)
1. `except Exception:` blocks -- pre-existing or new? Do they log?
2. Domain isolation: no cross-domain imports
3. user_id filtering on ALL endpoints in a file (not just some)
4. No unsafe fallback defaults (`or ""`, `or "dev"` on secrets)
5. Wiring: new services instantiated in app.py startup

### Pre-existing Violations (not new-phase blockers)
- `auth.py:179`: `except Exception: pass` in logout (noqa BLE001+S110)
- `chat.py:226`: `except Exception:` in _make_run_service -- does debug log
- `chat.py:157-162`: outer SSE handler leaks str(exc) to client (pre-existing CP3)
- Pre-existing test failures: test_orchestrator, test_mr8, test_mr9, test_cp4 (langgraph)
- Pre-existing frontend failures: qc7-fixes.test.tsx UI-M8 (2 tests, settings freshness SSE mock issue)
- threads.py:45 E501 ruff violation (line too long, not in PR1)

### Phase Review Notes (see topic files for iOS details)
- **iOS reviews:** See `ios-reviews.md`
- **System-Final (2026-03-10):** FAIL then PASS_WITH_NOTES. AuthUser migration orphaned callers. Approval IDOR. Push pipeline decorative.
- **TM1/TM2 (2026-03-11):** Both PASS_WITH_NOTES. Missing migration 009. Stub probes. In-memory credential store.
- **PR1 (2026-03-11):** PASS_WITH_NOTES. 19 tests. Runs join usage_stats. Memory user-scoped. RunService async. Gap: store() lacks user_id.
- **PR2 (2026-03-11):** PASS_WITH_NOTES. 10 tests. PATCH settings endpoint, Chat thread race fix (mutateAsync), RunDetail type cast removal. 4 ruff violations in test file. No non-mocked integration test. FINDINGS.md now 7 entries stale.
- **PR4 (2026-03-11):** PASS_WITH_NOTES. 24 tests. Path traversal guard, ProviderRouter hot-reload (full_settings), structured log context, MemoryStore public persist(). 1 ruff E501 in test. FINDINGS.md now 10+ entries stale (5th consecutive brief flagging).
- **PR7 (2026-03-11):** PASS_WITH_NOTES. 20 tests. Wave 19 audit fix cleanup: privacy_mode Optional+Literal, JWT error sanitized, noa.coding deleted, nosniff header, success_envelope list support, L14 added. FINDINGS.md updated (10 open, 97 resolved). Wave 19 complete.
- **DE1 (2026-03-12):** Cycle 1 FAIL, Cycle 2 PASS_WITH_NOTES. 74 tests. All 4 workflow files + pre-push hook. Postgres service added. Coverage gate (pytest-cov) not implemented. E2E step advisory (continue-on-error: true).
- **DE2 (2026-03-12):** PASS_WITH_NOTES. 22 tests. Caddyfile + compose + CORS + TLS docs. Caddy hardening flagged as gap.
- **DE3 (2026-03-12):** PASS_WITH_NOTES. 18 tests. All containers hardened (cap_drop ALL, no-new-privileges, resource limits, log rotation). Caddy hardening addressed per DE2 recommendation. workers_degraded flag is write-only (HD anti-pattern). backup service missing logging config. noa-dev container read-only (can't docker cp into it).
- **QE1 (2026-03-12):** PASS_WITH_NOTES. 39 tests. All 33 CI proposals triaged (26 APPLIED, 2 RESOLVED, 3 DEFERRED, 2 REJECTED). Process gates embedded in CLAUDE.md, QA_CHECKLIST.md, ARCH_INVARIANTS.md. FINDINGS.md tracking gap: W20-MED-3/4 referenced in PLAN.md but never added to FINDINGS.md.
- **QE4 (2026-03-12):** PASS_WITH_NOTES. 30 integration tests (6 suites) against real Postgres. Alembic migrations 010+011 fix schema drift (GO1 google_refresh_token, TM5 custom_tools). CI `test-integration` job added. Validates that create_all() hides drift that real migrations expose.
- **QE6 (2026-03-12):** PASS_WITH_NOTES. 16 tests. Coverage 84% (threshold 70%), mutmut configured (auth/router/gateway), pytest-repeat nightly CI. Notes: no CI mutation step (manual-only), TOML parsing fragile, no behavioral smoke for mutmut/repeat. Wave 21 complete.

### Infrastructure Security Baseline (2026-03-12)
- Claude Code: ~102 allow rules. `Bash(curl:*)` in allow conflicts with `Bash(curl)` in deny. `Bash(sed:*)` allows arbitrary file edits.
- Docker: No root user, no privileged, no secrets in ENV.
- CORS: Explicit localhost origins, wildcard rejected.
- Secrets: .env/.env.secrets gitignored. Only .env.example tracked.
- Deps: Loose >= pins with upper bounds. No lockfile.

### File Paths
- Reviews: `Plan/REVIEWS/review_{phase-id}.md`
- Health briefs: `Plan/REVIEWS/health_{date}.md`
- QA Checklist: `Plan/QA_CHECKLIST.md`
- Arch Invariants: `Plan/ARCH_INVARIANTS.md`
