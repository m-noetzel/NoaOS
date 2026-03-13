# QA Review: Phase QE2

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 5/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 25 tests trace to QE2 deliverables (mypy config, CI gate, type annotations) |
| M2 | Negative Tests | PASS | test_require_session_raises_without_session tests error path; test_mypy_not_continue_on_error is a negative gate check |
| M3 | Security Boundaries | PASS | No secrets introduced. No auth surface changed. 11 `type: ignore` comments all have specific error codes. |
| M4 | Determinism | PASS | No wall-clock time, network, or randomness in tests |
| M5 | Implementation Completeness | PASS | All 4 deliverables present: 72 src files fixed (exceeds plan's 18), pyproject.toml, ci.yml, pre-push-hook.sh |
| M5b | Findings Currency | PASS | W19-M6 already resolved by PR7. No new findings to track. |
| M5c | Related-Issue Scope | PASS | Phase fixes ALL mypy errors (0 remaining across 166 files), not a subset |
| M6 | No Silent Error Swallowing | PASS | No new bare except blocks introduced. All pre-existing have `noqa: BLE001` |
| M7 | Wiring Completeness | PASS | Mypy is wired in CI (static-analysis job, continue-on-error: false) and pre-push hook |
| M8 | Domain Isolation | PASS | No cross-domain imports found |
| M2b | Write-Path Fidelity | PASS | N/A — no write paths in this phase |
| M2c | Source-Inspection Gate | PASS | Source-inspection tests (pyproject.toml, ci.yml) verify config infrastructure, not executable code — M2c exemption applies. Remaining tests are behavioral (import + runtime checks). |
| M4b | Mock Interface Accuracy | PASS | Only 1 mock used (MagicMock for session in test_require_session_returns_session_when_set) — correct usage |
| M8b | Cross-Language Optionality | PASS | N/A — no request models changed |
| S1 | Error Handling & Boundaries | PASS | AuditService._require_session raises specific RuntimeError with message |
| S2 | Code Consistency | PASS | `strict = true` is a superset of plan's `warn_return_any + disallow_untyped_defs` — more rigorous |
| S3 | Migration & Rollback | PASS | N/A — no DB changes |
| S4 | Documentation | PASS | pyproject.toml mypy config is self-documenting with override comments |
| S5 | Integration Smoke Test | PASS | mypy itself validates 166 files as an integration check; 25 tests import and exercise real classes at runtime |

## Test Plan Coverage
No test plan was pre-written for QE2. Review conducted independently against spec and phase plan.

## Spec Compliance

| Requirement | Status |
|-------------|--------|
| Fix all 51 mypy errors → 0 | PASS — `mypy src/noa/ --ignore-missing-imports` returns "Success: no issues found in 166 source files" |
| Add mypy to CI as blocking gate | PASS — ci.yml static-analysis job: `mypy src/noa/` with `continue-on-error: false` |
| `pyproject.toml` [tool.mypy] with `warn_return_any`, `disallow_untyped_defs` | PASS — `strict = true` (superset) + `warn_return_any = true` + `warn_unused_configs = true` + pydantic plugin |
| Specific `# type: ignore[code]` only | PASS — 11 instances, all with specific codes (union-attr, assignment, attr-defined, no-any-return, arg-type, func-returns-value) |
| Update pre-push hook | PASS — mypy check in tools/pre-push-hook.sh |

## Test Coverage

| Test | Spec Requirement |
|------|-----------------|
| TestPyprojectMypy (6 tests) | pyproject.toml config presence and correctness |
| TestCIGate (3 tests) | CI mypy step present, not advisory, targets src/noa/ |
| TestAgentState (3 tests) | AgentState TypedDict has new typed fields |
| TestAuditService (2 tests) | AuditService._require_session behavior (positive + negative) |
| TestDBModelTyping (3 tests) | Checkpoint.state, CustomTool.functions, engine typed |
| TestToolTyping (4 tests) | All 4 tool classes have async execute() |
| TestSettingsServiceTyping (2 tests) | get_settings/update_settings have return annotations |
| TestPublicEndpointAnnotations (2 tests) | health/chat endpoints have return types |

Gap: No test directly verifies mypy returns 0 errors as an automated assertion. The meta-test is "run mypy manually and check output." This is acceptable because mypy is now a CI gate — the gate IS the test.

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- `except:` (bare): 0 instances found
- `except Exception:`: 41 instances found — all pre-existing with `noqa: BLE001` annotations. No new instances introduced.

**M7: Wiring:**
- ci.yml: `mypy src/noa/` step present with `continue-on-error: false`
- pre-push-hook.sh: `mypy src/ --ignore-missing-imports` present
- 18+ routers registered in app.py (no new routers in this phase)

**M8: Domain isolation:**
- `from noa.private_worker` in `src/noa/external_worker/`: 0 matches
- `from noa.external_worker` in `src/noa/private_worker/`: 0 matches

## Smoke Test Results

```
$ docker exec noa-dev python -m mypy src/noa/ --ignore-missing-imports
Success: no issues found in 166 source files

$ docker exec noa-dev python -m pytest tests/unit/test_qe2_mypy.py -v --override-ini="pythonpath=src"
25 passed in 0.22s

$ docker exec noa-dev python -m ruff check src/noa/ tests/
All checks passed!

$ docker exec noa-dev python -c "from noa.api.app import create_app; print('Import OK')"
Import OK
```

## Security
- No new secrets or credentials introduced
- No auth surface changes
- All 11 `type: ignore` comments use specific error codes — no blanket ignores
- No unsafe fallback defaults introduced
- Domain isolation intact

## Code Quality

**Positive:**
- `strict = true` in mypy config exceeds the plan requirement — enforces `disallow_untyped_defs`, `disallow_any_generics`, `warn_return_any`, and more
- pydantic mypy plugin configured for proper Pydantic model type checking
- Per-module overrides for third-party libraries without stubs (jose, jwt, yaml, langgraph, langchain_core)
- 72 source files modified (far exceeding the planned 18) — comprehensive cleanup

**Notes:**
- 11 `type: ignore` comments remain, all with specific error codes. These appear to be genuine third-party type gaps or SQLAlchemy dynamic attribute issues — acceptable.

## Beyond the Test Plan

1. **Pre-push hook targets `src/` but CI targets `src/noa/`**: The pre-push hook runs `mypy src/ --ignore-missing-imports` while CI runs `mypy src/noa/`. The pre-push is actually stricter (broader scope). Both pass. No issue — just a minor inconsistency. If a `src/` file outside `noa/` is added later, pre-push would catch it but CI wouldn't. Low risk since `src/noa/` is the only package.

2. **`strict = true` may cause friction for future phases**: New code must be fully typed from the start. This is intentional and good — but developers should be aware. Not a blocker.

3. **No automated mypy-zero regression test in the test suite**: The test suite doesn't run `mypy` as a subprocess to assert 0 errors. This is by design — CI is the gate. But a flaky `type: ignore` addition in a future phase would only be caught at CI time, not locally in `pytest`. Acceptable given the pre-push hook exists.

## Notes (PASS_WITH_NOTES)

1. **Minor inconsistency in mypy target scope**: Pre-push hook checks `src/` while CI checks `src/noa/`. Both pass. Consider aligning to the same target for consistency, though this is cosmetic since only `src/noa/` has Python code.

2. **11 `type: ignore` comments**: All justified with specific error codes. Worth periodic review as library stubs improve — some may become unnecessary.

## Decision Review

Phase QE2 delivers exactly what was planned and more. The mypy gate is now enforced in both CI and pre-push, covering the "greatest risk" identified in the QE1 health brief. The `strict = true` choice is more aggressive than the plan required but appropriate for a project of this maturity.
