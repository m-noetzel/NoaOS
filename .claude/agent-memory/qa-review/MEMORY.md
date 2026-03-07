# QA Review Agent Memory

## Project: NoaOS

### How to Run Tests
```bash
source .venv/bin/activate && python3 -m pytest tests/unit/test_NAME.py -v --override-ini="pythonpath=src"
```
Note: `.pip_libs/langsmith` has a broken pydantic_core in this env — pytest fails with ModuleNotFoundError unless you use `--override-ini="pythonpath=src"` (drops .pip_libs from PYTHONPATH at collection time). The langsmith pytest plugin auto-loads and crashes. Using `--override-ini` works.

### How to Import Modules
```bash
source .venv/bin/activate && python3 -c "from noa.X import Y"  # Works from project root
```

### Recurring Anti-Patterns in This Codebase

**Half-fixes on security findings:** QC2 showed that "C6: token storage" was addressed only on the backend (httpOnly cookies) while the frontend (`tokens.ts`, `AuthContext.tsx`) was left unchanged. The fix passed all 24 tests because **there were zero tests for C6 despite it being listed as covered**. Always verify: when a finding is listed as "covered," does a test class actually exist for it?

**CORS env var bypass:** `CORS_ALLOWED_ORIGINS=*` passes directly to `CORSMiddleware(allow_origins=[...])` without validation. Starlette accepts wildcard. Combined with `allow_credentials=True` this is a critical vulnerability. Pattern to check: any env var feeding into security config must be validated at startup.

**Source inspection tests are weak:** Tests in QC2 used `inspect.getsource()` to verify `with_for_update` and `nh3` usage. These pass even if the code path is unreachable. Prefer behavioral tests calling real functions with assertions on outcomes.

**Tokens in JSON body + cookies = dual path:** When a backend sets httpOnly cookies AND returns tokens in the JSON body, the frontend will use whichever is more convenient — typically the JSON body. The cookies become decoration. To truly fix C6, the response body must not contain raw tokens.

### Security Checks That Catch Real Bugs (run these every review)
1. `CORS_ALLOWED_ORIGINS=*` env var → does app reject wildcard origins?
2. Login endpoint → do cookies get set? Do tokens ALSO appear in JSON body?
3. `web/src/auth/tokens.ts` → does it use localStorage?
4. `except Exception:` blocks — are they pre-existing or new? Do they log?
5. Domain isolation: `grep -rn "from noa.private_worker" src/noa/external_worker/`

**Lifespan tests that don't test lifespan:** FastAPI's lifespan `asynccontextmanager` only runs when the ASGI server starts — not on module import. Tests that patch a function, import `app`, then check `caplog` are actually testing `create_app()` (which runs eagerly), NOT the lifespan body. Always check: does the lifespan actually execute in the test, or does it only import?

**noqa suppresses linter but not ARCH_INVARIANTS:** `# noqa: BLE001` prevents ruff from flagging `except Exception:` blocks, but ARCH_INVARIANTS.md L9 rule 2 still requires logging or re-raise. Always manually check that each suppressed `except Exception:` block has a log call or re-raise — the noqa just hides violations from the static gate.

**N806 ruff error from UPPER_SNAKE_CASE inside functions:** When adding constants inside function bodies (e.g. `_SAFE_KEYS = {...}`), ruff N806 fires because the `N` ruleset is selected. The fix is either: move the constant to module scope, or use lowercase `_safe_keys`. This breaks the `ruff check` merge gate.

**Partial H5 fix pattern:** When H5 ("bare except blocks") is a phase deliverable, check ALL except blocks in touched files — not just the one that was `except: pass`. Developers tend to fix the explicit `pass` block but leave adjacent `except Exception:` blocks that also lack logging (e.g. `chat.py:163` inner except fixed the outer, left the inner).

**Module re-export breaks existing patch targets:** When moving a module's implementation to a new location (e.g. `private_worker/ollama_client.py` → `noa.llm.providers.ollama`) and leaving a thin re-export shim, existing tests that patch attributes on the OLD module (e.g. `patch("noa.private_worker.ollama_client.httpx.AsyncClient")`) silently miss — the old module no longer imports `httpx`. Always check test files that import from the moved module and update patch targets to the canonical path. QC4 broke 5 `test_llm_ollama.py` tests this way.

**Async method alias causes regression:** When aliasing a sync method to an async one at class level (`purge_expired = purge_expired_async`), any synchronous caller gets a coroutine object instead of the result. QC5 broke 3 `test_audit.py` tests with this pattern. When standardizing to async (M12), update ALL callers — including pre-existing tests.

**Making sync methods async breaks existing sync tests:** When QC5 converted `RunService.create_run` and `append_event` from sync to async, it broke 54 `test_runs.py` tests that call these methods without `await`. The M12 spec check (`asyncio.iscoroutinefunction`) passed, but the regression check (run full test suite) was either skipped or missed. Always run the full test suite, not just the phase's new tests.

**"Wired in class, not in app" pattern:** QC5 implemented `purge_expired_async` in `AuditService` and `approval_service` parameter in `RetentionScheduler`, but neither was connected in `app.py`'s lifespan. Tests mocked the services and passed. Check: is the real service object ever instantiated and passed in startup code? Always grep `app.py` lifespan for the class name after implementing a service fix.

**"Wired in class, not at startup" — the QC8 pattern:** QC8 repeated the QC5 anti-pattern at scale: 4 of 6 findings had the mechanism implemented (class/function/callback) but never connected in `app.py` startup wiring. `PolicyEngine` not set on `gateway.policy_engine`, `on_token_change` not passed in `registration.py`, `idempotency_key_ctx` never read in `chat.py`, `transactional()` never called anywhere. Tests all passed because they manually inject the dependency. To catch this: after reviewing implementation, grep `app.py` and each caller for the new class/function name. If it only appears in its own module and the test file, it is not wired.

**"Orphaned utility" pattern:** A5/A4 in QC8 — `NoOpCheckpointer` and `transactional()` exist in `src/` but are never imported by any production module. L10 (wiring completeness) requires every function/class in `src/` to be reachable from a running entry point. Grep for the symbol in all non-test files; if it only appears in its own file, it violates L10.

**Dead-code in dataclass alongside inline reimplementation:** gateway.py QC8 left `_RateLimit` dataclass (with `check()` method) unused after the inline per-user rate limiting was added in `dispatch()`. Two implementations of the same logic in the same class is a code smell that signals incomplete refactoring.

**SSE Last-Event-ID pattern:** "sending Last-Event-ID" has two parts — (1) assigning a reconnect URL, and (2) including the `Last-Event-ID` header. It is easy to implement part 1 (runId tracking) while forgetting part 2 (header in reconnect request). Always check both in sse.ts-style clients.

### Pre-existing Violations (not to flag as new-phase blockers)
- `src/noa/api/v1/auth.py:179`: `except Exception: pass` in logout best-effort path — pre-QC2, suppressed with noqa BLE001+S110
- `src/noa/api/v1/chat.py:163`: inner `except Exception:` in `_make_run_service` — does rollback only, no log — pre-QC3 but unaddressed
- Pre-existing failures (langgraph not installed): `test_orchestrator.py`, `test_mr8_model_routing.py`, `test_mr9_conditional_edges.py`, `test_cp4_startup.py` (partially)
- Pre-existing: `test_new_endpoints.py::TestArtifactsRoutes::test_route_count` — artifact route count mismatch

### QC4/QC5 State (post-review)
- C2 (domain isolation) FIXED: `noa.llm.providers.OllamaClient` is canonical; `private_worker/ollama_client.py` re-exports
- M8 (domain isolation imports): CLEAN — both AST scan and runtime confirm no cross-domain imports
- `src/noa/api/app.py:197-215`: `_PurgeProxy` still used — M3 fix never wired; retention still disabled in production
- `src/noa/api/app.py:209-215`: `approval_service` not passed to `RetentionScheduler` — M6 not wired in production
- `alembic/versions/`: migration 006 (H2 performance indexes) never created

### E2E Testing Patterns (Wave 16, 2026-03-07)
- **page.route() over mock mode**: Playwright's page.route() is superior to VITE_USE_MOCKS because it covers raw fetch() calls (SSE) that the app's mock interceptor cannot.
- **Positional selectors are fragile**: `locator('input[type="number"]').first()` breaks when form layout changes. Prefer data-testid or label associations.
- **route.fulfill delivers SSE atomically**: Cannot test incremental streaming UX. Only end-state assertions are valid.
- **Missing route mocks cause proxy errors**: Unmocked routes hit Vite proxy -> ECONNREFUSED. Add comprehensive mocks in fixtures.ts.
- E2E config: `web/playwright.config.ts`, tests: `web/e2e/`, fixtures: `web/e2e/fixtures.ts`

### Infrastructure Security Baseline (2026-03-07)
- Claude Code: 107 allow rules, all scoped. Deny blocks curl, wget, ssh, rm -rf, python -c.
- Docker: No root user, no privileged, no secrets in ENV.
- CORS: Explicit localhost origins, wildcard rejected.
- Secrets: .env/.env.secrets gitignored. Only .env.example tracked.
- Deps: Loose >= pins with upper bounds. No lockfile -- risk for production.

### File Paths
- Reviews go to: `Plan/REVIEWS/review_{phase-id}.md`
- Health briefs: `Plan/REVIEWS/health_{date}.md`
- QA Checklist: `Plan/QA_CHECKLIST.md`
- Arch Invariants: `Plan/ARCH_INVARIANTS.md`
- Domain isolation tokens MUST use httpOnly cookies (L11), not localStorage (ARCH_INVARIANTS.md)
- No DECISION_LOG.md or MASTER_PLAN.md in Plan/ — check `Plan/PLAN.md` and `Plan/PHASE_DETAILS.md` instead
