# QA Checklist — Deterministic Review Criteria

Every QA review evaluates against these criteria. PASS requires ALL must-haves green. PASS_WITH_NOTES allows should-haves to be open.

---

## Must-Haves (BLOCKING — any failure = FAIL verdict)

### M1: Spec Traceability
- [ ] Every test class/method has a docstring citing SPEC.md §X.Y or PLAN Phase ID
- [ ] Every spec requirement listed in the phase plan has at least one corresponding test
- [ ] No orphan tests (tests that don't trace to any requirement)

### M2: Negative Tests
- [ ] At least 1 negative/error-path test per phase (invalid input, unauthorized access, boundary violation)
- [ ] Error tests verify specific error types or messages, not just "raises Exception"

### M3: Security Boundaries
- [ ] No hardcoded secrets, credentials, or API keys in src/ or tests/
- [ ] User input validated at system boundaries (API endpoints, CLI args, external data)
- [ ] Auth boundaries respected (unauthenticated access correctly rejected where required)
- [ ] Domain isolation model not violated (private domain code doesn't reach external services)
- [ ] No security-sensitive values with fallback defaults (`or ""`, `or "dev"`, `or None` on secrets)
- [ ] JWT/auth secrets validated at startup — app must refuse to start without them
- [ ] Token storage uses httpOnly cookies, not localStorage (frontend phases)
- [ ] CORS origins are explicitly configured, not wildcard `*`
- [ ] Tool/capability defaults are deny, not allow

### M4: Determinism
- [ ] No tests depend on wall-clock time (`time.time()`, `datetime.now()` without injection)
- [ ] No tests depend on network access
- [ ] No tests depend on random values without seeding
- [ ] Tests pass consistently when run 3x in sequence

### M5: Implementation Completeness
- [ ] All files listed in phase plan's file table are created/modified
- [ ] All deliverables listed in phase plan are present and functional
- [ ] No TODO/FIXME/HACK comments that defer required work to "later"

### M6: No Silent Error Swallowing
- [ ] No bare `except:` or `except Exception: pass` blocks
- [ ] Every exception handler either logs with trace_id, re-raises, or returns a specific error response
- [ ] No `except` blocks that return success responses (e.g., HTTP 200 on database error)
- [ ] Specific exception types caught — not blanket `Exception` unless re-raised

### M7: Wiring Completeness
- [ ] If the phase creates a FastAPI router, it is registered in `app.py`
- [ ] If the phase creates a service, it is instantiated during app startup
- [ ] If the phase creates an endpoint, the endpoint is reachable (not orphaned)
- [ ] If the phase creates a worker handler, it is connected to a route
- [ ] Code is callable from the running system, not just tested in isolation

### M8: Domain Isolation (Import Boundaries)
- [ ] No imports from `noa.private_worker` in `noa.external_worker` (or vice versa)
- [ ] No imports from `noa.api` in `noa.db` or worker packages
- [ ] No circular imports between packages
- [ ] Shared code lives in shared modules (`noa.constants`, `noa.llm.providers`), not cross-domain imports

---

## Should-Haves (NON-BLOCKING — note for improvement)

### S1: Error Handling & Boundaries
- [ ] Boundary conditions tested (empty collections, max values, unicode)
- [ ] Error messages are actionable (not generic "something went wrong")

### S2: Code Consistency
- [ ] Follows existing naming conventions in the codebase
- [ ] Follows layering rules in ARCH_INVARIANTS.md
- [ ] No duplicate abstractions (check if similar utility already exists)

### S3: Migration & Rollback
- [ ] If DB schema changes: migration is reversible (has downgrade)
- [ ] If config changes: old config values don't break startup

### S4: Documentation
- [ ] Public API functions have type annotations
- [ ] Non-obvious logic has brief inline comments

### S5: Integration Smoke Test
- [ ] At least one test per phase calls the main function/endpoint without mocking internal dependencies
- [ ] Async functions are tested with real `await` (not just mocked return values)
- [ ] Cross-module interactions tested (e.g., service → repository → model)

---

## Scoring (for review report)

Count must-haves passed: `{passed}/{total}` — all must be green for PASS.
Count should-haves passed: `{passed}/{total}` — informational.

If must-have fails: verdict = FAIL with specific blocking issues listed.
If all must-haves pass but should-haves open: verdict = PASS_WITH_NOTES.
If all pass: verdict = PASS.
