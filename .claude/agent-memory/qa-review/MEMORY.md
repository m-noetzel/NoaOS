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

**"Migration chain broken across worktree branches" (FR3):** When two concurrent worktrees add migrations, the later worktree may reference a `down_revision` that only exists on main (from the earlier merged worktree). `alembic history` crashes with `KeyError`. Tests pass because they use `create_all`. Add a test that verifies every migration's `down_revision` points to an existing file (pure file parsing, no DB needed). Check this every time a migration's `down_revision` != the numerically preceding migration file.

**flush-without-commit:** get_db_session does NOT auto-commit. Every write endpoint needs session.commit().

**"Scope reduction without plan update" (DE1):** Phase plan specifies 5 deliverables, only 1 delivered (ci.yml). cd.yml/web-ci.yml/ios-ci.yml all missing. Always compare delivered files against PHASE_DETAILS.md file table, not just "does the one file that exists look correct."

**"CI env points to unreachable service" (DE1):** DATABASE_URL in CI workflow points to postgresql://localhost:5432 but no `services:` block configures a Postgres container. Tests that don't override the URL will fail. Always check that CI env vars point to reachable services.

**"State set but never read" (DE3):** `app.state.workers_degraded` set at startup but no endpoint or middleware reads it. Variant of HD anti-pattern. Always grep for consumers of any state flag being added.

**"Config-only tests miss runtime behavior" (DE1-DE3):** Three consecutive deployment phases validated by parsing YAML/Dockerfile text. No real Docker Compose execution. First real deployment is the actual integration test.

**"Route dict overwrite when enumerating routes" (smoke test pattern):** When building `{r.path: r.methods for r in router.routes}`, paths with multiple HTTP methods (e.g. PATCH and DELETE on same path) will overwrite each other — only the last one survives. Always use `any(r.path == path and method in r.methods for r in router.routes)` to check for a specific method.

**"Enum-expansion causes endpoint to accept invalid-but-registered keys" (MVP-H2):** When TOOL_CAPABILITIES dict is extended with auto-generated function-level keys (e.g. `memory__remember`), any endpoint that validates `name not in TOOL_CAPABILITIES` now accepts function-level keys as valid tool names. The resulting DB grant uses the function-key as tool_name, which has_capability() never matches (it checks tool-level name). Effect: no-op grants with 200 response. Fix: validate against `TOOL_SCHEMAS.keys()` (top-level only) for tool-level endpoints.

**"Partial dispatch implementation creates UX promise not delivered" (MVP-H3):** The enqueue path (user sees "queued" SSE) works, but the drain path (task actually executed) is deferred. Users get a promise ("your request will run when available") that is never fulfilled. Always check BOTH sides of a queue: producer path AND consumer path. If drain doesn't dispatch, the feature is decorative.

**"Capability dict used for two different purposes" (MVP-H2):** TOOL_CAPABILITIES serves as both (a) the authoritative capability→tool mapping for has_capability() and (b) the validation set for enable_tool(). When function-level keys are added for purpose (a), they accidentally expand the validation surface for purpose (b). Separate concerns: use different collections for different validation purposes.

**"Intermediate state not recovered on crash" (MVP-L3):** A queue/pipeline that sets status="processing" before doing work must also have a recovery path for tasks stuck in "processing" if the process crashes mid-work. DurableQueue.poll() only returns status="queued" tasks; tasks stuck in "processing" are permanently lost. Any time intermediate state is persisted (e.g. "processing", "locked", "in_flight"), verify there is a timeout-based recovery that resets it to the retry state. Without recovery, a container restart creates silent data loss.

### Security Checks (run every review)
1. `except Exception:` blocks -- pre-existing or new? Do they log?
2. Domain isolation: no cross-domain imports
3. user_id filtering on ALL endpoints in a file (not just some)
4. No unsafe fallback defaults (`or ""`, `or "dev"` on secrets)
5. Wiring: new services instantiated in app.py startup

**"DB column retained after service moves to file-backed storage" (sp-transparency):** When a service switches from DB-backed to file-backed storage, the ORM model column and migration may be left behind. The service comment says "no DB column" but the column exists in migration 013 and models.py. Always add a cleanup migration to drop the unused column, or explicitly document its retention. Dead ORM columns mislead future developers about where data is stored.

**"Asymmetric validation across write paths for same resource" (sp-transparency):** PUT /system-prompt enforces a 10,000-char limit but PATCH /settings (which also writes system_prompt via update_settings()) does not. When the same data can be written via multiple endpoints, all write paths must have consistent validation. Check: grep for all routes that call the same service method and verify they share validation.

**"prompts/ directory absent from Docker COPY" (FR4):** Path-relative file loading (`__file__.parent.parent.parent.parent.parent / "prompts"`) works in dev worktree but silently fails (OSError caught, returns "") in Docker because only `src/`, `alembic/`, `pyproject.toml` are COPYed. Always verify that repo-relative file lookups are either included in the Dockerfile or have a documented production fallback.

**"Fail-closed breaks test that relied on factory=None=skip" (FR1):** Adding fail-closed domain check (returns error when factory=None) breaks existing tests that patch factory=None expecting the check to be skipped. Always run full test suite when adding fail-closed behavior to an existing function. Check if existing tests rely on the old fallback semantics.

**"Health check skips store validation when tool IS registered" (FR2):** `ToolHealthChecker.check("memory")` only calls `_check_memory_health()` when the tool is NOT registered in the gateway. When the tool IS registered, no probe is defined for memory tools, so it returns "ok" immediately without verifying the store's data_dir or accessibility. A health check that returns "ok" by absence-of-probe rather than positive verification is a false-positive risk. Always verify that health checks make a POSITIVE assertion, not just "no probe defined = ok".

**"FINDINGS.md count not decremented after resolve" (FR1):** Findings rows correctly marked Resolved, but the `**Open:** N` footer count was not decremented. test_qe3_findings.py::test_findings_open_count_consistent catches this. Always update the count line at `Plan/FINDINGS.md:164` when resolving findings.

**"SQLAlchemy column default=value does NOT apply at Python object creation" (FR1):** `mapped_column(..., default="external")` in SQLAlchemy only applies the default when the INSERT executes. At Python object creation time, `conv.domain is None` (not "external"). Always use explicit values when instantiating ORM objects, or use `Conversation(domain=privacy_mode, ...)` at write sites. Tests that check `conv.domain` right after construction without committing will see None.

**"SQLite CHECK constraints not enforced in-memory" (FR1):** SQLite does not enforce CHECK constraints on column values. A `domain IN ('private', 'external')` CHECK constraint in the migration will be enforced by Postgres but not by in-memory SQLite tests. Don't rely on CHECK constraint enforcement in unit tests.

### Pre-existing Violations (not new-phase blockers)
- `auth.py:179`: `except Exception: pass` in logout (noqa BLE001+S110)
- `chat.py:226`: `except Exception:` in _make_run_service -- does debug log
- `chat.py:157-162`: outer SSE handler leaks str(exc) to client (pre-existing CP3)
- Pre-existing test failures: test_orchestrator, test_mr8, test_mr9, test_cp4 (langgraph)
- Pre-existing test failures (pre-existing, not FR1): test_mr5_tool_permissions (2), test_qc2_security_hardening (1), test_qc8_architecture (2)
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
- **FR1 (2026-03-13):** Cycle 1 FAIL, Cycle 2 PASS_WITH_NOTES. 30 tests (real SQLite DB). Domain isolation: thread scoping (BE-C3), tool visibility (BE-H8), provider filtering (BE-H11). Fixes: seeded real Conversation row in regression test (correct pattern), updated FINDINGS.md count to 35 open. Notes: fail-open on DB exception in _check_thread_domain (FR1-L1), cascade delete not tested at DB level, pytest.mark.fr1 unregistered.
- **FR2 (2026-03-13):** PASS_WITH_NOTES. 27 tests. BE-H6 (volume mount), BE-H7 (memory approval wiring), BE-H9 (external memory store + noa.memory shared layer), BE-H10 (health check), BE-H12 (logout cookie deletion). Notes: M5b FAIL — FINDINGS.md not updated (5 findings still Open). pytest.mark.fr2 unregistered. Memory health false-positive when tool IS registered but store has no data_dir. noa.memory transitive coupling pattern not yet in ARCH_INVARIANTS.md.
- **FR3 (2026-03-13):** PASS_WITH_NOTES. 14 tests. W21-H1 (FK cascade), W21-H2 (backup cap_drop), W21-M1 (/docs gating), W21-M2 (traceability --check). Gap: migration chain broken in worktree (015 refs 014, but 014 missing). Works post-merge. New finding FR3-L1: migration chain not tested. datetime.utcnow deprecation in traceability.py.
- **FR4 (2026-03-13):** PASS_WITH_NOTES. 19 backend + 18 frontend tests. UX-H1/H2/H3/H5/H9/H10. Keepalive 15s asyncio.Queue pattern. tool_start/tool_end intentionally live-only (not in VALID_EVENT_TYPES, correctly excluded from DB). prompts/ absent from Docker COPY — default system prompt empty in production. M5b: 6 findings not marked Resolved in FINDINGS.md (CI-015 violation).
- **FR5 (2026-03-13):** PASS_WITH_NOTES. 12 Python + 11 frontend tests. UX-H4/H7/H8/H11/M1/M5/M6/M7. Cost dashboard, pricing endpoint, budget progress bar, empty states, run links. 2 ruff E501 in cost.py. CostRecord.run_id typed string in types.ts but backend returns null (type lie, JSX handles it defensively). No negative test for invalid period param (422). Findings properly updated. S5 PASS (real SQLite integration).
- **FR6 (2026-03-14):** PASS_WITH_NOTES. 19 Python + 18 frontend + 8 Swift tests. Thread rename (PATCH /threads/{id}), governance toggle + agent limits (settings), tool scopes (GET+PATCH /tools/scopes), Notion auto-grant, iOS backend health (BackendConnectionStatus). All pass. Notes: max_tool_calls/max_retries/timeout_seconds accept negative values (no Pydantic bounds). _scope_overrides in-memory only (FR6-L1). iOS T-FR6-04 soft assertion accepts both reachable/unreachable. Wave 22 UX cleanup effectively complete (FR1-FR6). 4 open findings (all Low).
- **sp-transparency (2026-03-14):** PASS_WITH_NOTES. 53 tests pass. Targeted refactor: system_prompt single source of truth (prompts/system_prompt.txt). 3-way duplication (DB, hardcoded runner, file) eliminated. Two orchestrator bugs fixed (agent empty-content response, responder empty-message skip). Notes: UserSettings.system_prompt DB column still in ORM + migration 013 (schema drift). PATCH /settings has no length limit on system_prompt (PUT /system-prompt has 10k limit). No non-mocked integration test for PATCH→file write path.
- **MVP-fixes (2026-03-14):** PASS_WITH_NOTES. 1966 unit tests pass, 0 failures. 8 fixes: MVP-H2 (memory tool visibility), MVP-H3 (queue+drain), W22-H1 (agent limits wiring), W22-H2 (approvals toggle), W22-M1 (privacy_mode domain filter), W22-M2 (Pydantic bounds), FR3-L1 (migration chain test), FR6-L1 (scope persistence). Notes: QueueDrainWorker._drain_one never calls self._runner — queued tasks permanently stuck in "processing" state (Phase 2 deferred). enable_tool accepts function-level keys from TOOL_CAPABILITIES (no-op grants). No meta event in queued SSE stream. No Run/Conversation rows created for queued chats. 4 new medium/low findings added.
- **MVP-fixes-2 (2026-03-14):** PASS_WITH_NOTES. 1981 unit tests pass. 4 fixes: MVP-M1 (drain dispatch+retry), MVP-M2 (Run rows for queued path), MVP-L1 (TOOL_SCHEMAS validation in enable_tool), MVP-L2 (meta event before queued in SSE). Pre-existing test mocks updated (scalar_one_or_none→scalars().first(), approved=True for approval gate). New finding: MVP-L3 (task stuck in "processing" on crash — DurableQueue.poll() has no recovery for processing state). Mypy union-attr warning in drain.py:129 (safe at runtime, typing gap).
- **AU1 (2026-03-15):** PASS_WITH_NOTES. 13 tests. AUTH-H1/H2/M1/M2 all resolved. Rate limiting removed, 7-day/90-day tokens, /auth/me endpoint, skipAuthRetry on login, localStorage flag removed (no-op stub). Pre-Wave 23 phase. M5b: FINDINGS.md not updated — blocking; resolved during QA. Gap: au1-auth-stability.test.ts docstring claims AuthContext/AuthGuard component tests but none exist. test_logout_then_me_returns_401 is a naming misnomer (no logout call). Cookie max_age hardcoded instead of derived from settings.

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
