# Retrospective: Wave 1 (Project Foundation) + Wave 2 (Orchestration Core)

**Date:** 2026-03-04
**Phases covered:** F1, F2, F3, F4, OC1, OC2, OC3, OC4
**Total tests delivered:** 182 (17+21+15+20+26+37+18+28)
**QA verdicts:** 6 PASS, 2 PASS_WITH_NOTES (F4, OC3)
**Issues logged:** 0 (ISSUES.md clean)

---

## What Went Well

### 1. Consistent delivery ahead of estimates
Every phase came in at or under its time estimate. Several phases (F3, OC2, OC3, OC4) completed in roughly half the estimated time. The planning was conservative, which kept the pipeline moving without pressure.

### 2. Test counts exceeded plan estimates in every phase
Plan estimates totaled roughly 107 tests; actual delivery was 182. OC1 planned ~15 tests and delivered 26. OC2 planned ~20 and delivered 37. This is good — overdelivery on tests catches more regressions early.

### 3. Strong spec traceability
All 8 QA reviews scored M1 (Spec Traceability) as PASS. Every test class has docstrings citing SPEC.md sections. No orphan tests were found in any phase. This discipline pays off when tracing failures back to requirements.

### 4. Static gates caught nothing because code was clean
ruff and mypy passed on every phase with zero errors. This means the code agents are writing clean code from the start rather than relying on gates to catch issues.

### 5. Clean layering and architecture invariants
No layering violations (L1/L2) were found in any review. Dependency direction is consistently correct: API -> service -> data. Orchestrator code has no imports from API or DB layers.

### 6. Decisions documented in real time
The Decision Log captured 13 decisions across both waves, each with alternatives considered and rationale. QA reviews confirmed no undocumented architectural decisions. This creates a useful paper trail.

---

## What Could Improve

### 1. Missing deliverables: API endpoint gaps
OC3 was missing `src/noa/api/v1/audit.py` — the HTTP router for audit queries. The service layer and Pydantic schemas were complete but the thin wiring layer was skipped. QA flagged it but still passed the phase. Recommendation: code agents should check their file table as a final step before declaring done.

### 2. PASS_WITH_NOTES verdicts need follow-up tracking
F4 and OC3 received PASS_WITH_NOTES but the notes (mock session in production code, missing API endpoint, broad exception assertions, rate limiter class-level state) are not tracked anywhere as follow-up tasks. They risk being forgotten. Recommendation: add a "Follow-up Items" section to MASTER_PLAN.md or file them as LOW-severity items in ISSUES.md.

### 3. Broad exception assertions in tests (F4)
Several F4 auth tests use `pytest.raises(Exception)` instead of `pytest.raises(AuthError)` or `pytest.raises(TokenError)`. While functionally correct, this weakens the negative test contract — a test could pass even if the wrong exception type is raised. Should be tightened in a cleanup pass.

### 4. Missing Alembic migrations for new models
OC3 and OC4 both added or modified models (AuditLog table, Approval domain column) without creating Alembic migration files. The QA reviews noted this but did not block. Multiple phases deferring migrations creates a compounding debt. Recommendation: schedule a migration consolidation task before Wave 3 deploys or before any integration testing that needs a real database.

### 5. Placeholder/stub patterns accumulating
- F4: `_mock_session` using `unittest.mock.AsyncMock` in production code
- OC1: `checkpointer.py` is an empty placeholder
- OC1: `invoke_llm` and `execute_tool` raise `NotImplementedError`

These are all appropriate for skeleton phases but are now accumulating. Wave 3 (Domain Workers) will need to wire real implementations. Track these stubs explicitly.

---

## Specific Observations

### 7 test_orchestrator.py failures are an environment issue, not a code bug
The OC2 and OC4 reviews both note "7 pre-existing OC1 failures." These are `ImportError` failures in `test_orchestrator.py` caused by `langsmith`/`langgraph` native dependencies (`xxhash.so`, `ormsgpack.so`) that were installed to `/workspace/.pip_libs` due to a `noexec` constraint on `/home` in the container. When the Python path does not include this directory, the imports fail. This is purely an environment/dependency issue — not a code defect. Resolution: ensure `PYTHONPATH` or `sys.path` includes `/workspace/.pip_libs` in all test runner contexts, or pin the dependency installation in the container setup.

### Pytest warnings: async mocks and unknown marks
Test runs produce warnings about:
- **Async mocks** (`RuntimeWarning: coroutine ... was never awaited`): Some `unittest.mock.patch` usage on async functions creates coroutines that are not awaited. These are cosmetic but noisy. Fix by using `AsyncMock` explicitly where patching async callables.
- **Unknown pytest marks**: Custom marks (e.g., `@pytest.mark.slow`) used without registration in `pyproject.toml`. Fix by adding a `[tool.pytest.ini_options] markers` section.

Neither of these affect test correctness, but they add noise that obscures real warnings.

---

## Recommendations for Wave 3

### R1: Fix the langsmith/langgraph import issue before starting
The 7 failing OC1 tests should pass. Either fix the container `PYTHONPATH` configuration or add a `conftest.py` that extends `sys.path`. This should be a 5-minute fix, not carried as permanent baggage.

### R2: Register pytest markers and fix async mock warnings
Add a `markers` section to `pyproject.toml` and audit mock usage in `test_orchestrator.py` for proper `AsyncMock` usage. Clean warnings mean real warnings stand out.

### R3: Schedule a migration consolidation task
Before DW1-DW4 begin, run `alembic autogenerate` to capture all model changes from F2 through OC4 in a single migration. Wave 3 introduces Docker network isolation and will likely need a real database for integration tests.

### R4: Track follow-up items from PASS_WITH_NOTES reviews
Create entries in ISSUES.md for:
- Replace `_mock_session` in `src/noa/api/v1/auth.py` with real DB session (from F4 review)
- Create `src/noa/api/v1/audit.py` endpoint router (from OC3 review)
- Tighten exception assertions in `test_auth.py` (from F4 review)
- Wire real checkpointer in `orchestrator/checkpointer.py` (from OC1 review)

### R5: Wave 3 will wire real implementations — plan for integration testing
DW1 (Private Worker with Ollama) and DW3 (Docker Network Isolation) will need to move beyond unit tests with mocks. Plan for integration test infrastructure: a test compose file, database fixtures with real Postgres, and network isolation verification tests.

### R6: Keep the phase-under-estimate pattern
Conservative estimates worked well. Every phase finished early, which meant the pipeline never stalled. Continue estimating at the current level.
