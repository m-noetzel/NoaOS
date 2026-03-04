# QA Checklist — Deterministic Review Criteria

Every QA review evaluates against these criteria. PASS requires ALL must-haves green. PASS_WITH_NOTES allows should-haves to be open.

---

## Must-Haves (BLOCKING — any failure = FAIL verdict)

### M1: Spec Traceability
- [ ] Every test class/method has a docstring citing SPEC.md §X.Y or MASTER_PLAN Phase ID
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

### M4: Determinism
- [ ] No tests depend on wall-clock time (`time.time()`, `datetime.now()` without injection)
- [ ] No tests depend on network access
- [ ] No tests depend on random values without seeding
- [ ] Tests pass consistently when run 3x in sequence

### M5: Implementation Completeness
- [ ] All files listed in phase plan's file table are created/modified
- [ ] All deliverables listed in phase plan are present and functional
- [ ] No TODO/FIXME/HACK comments that defer required work to "later"

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

---

## Scoring (for review report)

Count must-haves passed: `{passed}/{total}` — all must be green for PASS.
Count should-haves passed: `{passed}/{total}` — informational.

If must-have fails: verdict = FAIL with specific blocking issues listed.
If all must-haves pass but should-haves open: verdict = PASS_WITH_NOTES.
If all pass: verdict = PASS.
