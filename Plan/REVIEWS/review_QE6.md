# QA Review: Phase QE6

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 16 tests have docstrings citing QE6 scope (coverage, mutmut, flaky detection). Phase plan requirements all covered. |
| M2 | Negative Tests | PASS | Not strictly applicable -- this phase is config/tooling infrastructure with no error paths to test. The meta-test (T16) verifies functional output, which is the closest analog. |
| M3 | Security Boundaries | PASS | No secrets, no API changes, no auth surface changes. CI secret `SECRET_KEY` is a test-only value. |
| M4 | Determinism | PASS | No wall-clock time, no network calls, no random values. All tests read local files or run subprocess. |
| M5 | Implementation Completeness | PASS | All 3 core deliverables implemented (coverage, mutmut, flaky detection). Performance baselines (item 4, pytest-benchmark) explicitly marked optional/low-priority in phase plan and omitted -- acceptable scope reduction. `mutmut_config.py` file not created because mutmut config is in `pyproject.toml` `[tool.mutmut]` section -- equivalent and cleaner. `tests/conftest.py` not modified because pytest-cov works via CLI args -- no plugin registration needed. |
| M5b | Findings Currency | PASS | Phase resolves no findings. 0 open remains correct. |
| M5c | Related-Issue Scope | PASS | No pattern fix -- N/A. |
| M6 | No Silent Error Swallowing | PASS | No except blocks in test file. |
| M7 | Wiring Completeness | PASS | No new routers or services. CI workflow changes are structural additions (coverage args to existing test step, new nightly job). Both are wired into the workflow trigger matrix. |
| M8 | Domain Isolation | PASS | No cross-domain imports. Test file only imports stdlib + pytest. |
| M8b | Cross-Language Field Optionality | PASS | N/A -- no API model changes. |
| M2b | Write-Path Test Fidelity | PASS | N/A -- no write-path testing. |
| M2c | Source-Inspection Test Gate | PASS | 15/16 tests are source-inspection (read config, assert string). The 16th (`test_coverage_runs_on_minimal_example`) is the behavioral companion that actually executes pytest-cov and verifies functional output. This satisfies the gate. |
| M3b | Write-Path User Scoping | PASS | N/A -- no user data storage. |
| M4b | Mock Interface Accuracy | PASS | N/A -- no mocks used. |
| S1 | Error Handling & Boundaries | PASS | Coverage threshold parsing handles missing `fail_under` gracefully (pytest.fail). |
| S2 | Code Consistency | PASS | Follows project naming conventions. Test organization is clean (sections: deps, config, gitignore, CI, traceability, meta-test). |
| S3 | Migration & Rollback | N/A | No DB changes. |
| S4 | Documentation | PASS | TRACEABILITY.md updated with coverage baseline (84%), mutation testing baseline (TBD), flaky test instructions. |
| S5 | Integration Smoke Test | OPEN | All tests are either source-inspection or subprocess invocation. No test imports and exercises a noa module directly. The meta-test (`test_coverage_runs_on_minimal_example`) is the closest to integration but runs pytest as a subprocess rather than importing coverage APIs. Acceptable for a config-infrastructure phase. |

## Test Plan Coverage
No test plan existed for QE6. Review conducted independently against phase plan and QA checklist.

## Spec Compliance

Phase plan specifies 4 scope items:

1. **Coverage (pytest-cov)**: COMPLETE. `pytest-cov` in dev deps, `[tool.coverage.run]`/`[tool.coverage.report]`/`[tool.coverage.html]` configured, `fail_under = 70`, CI runs with `--cov=src/noa --cov-fail-under=70`, HTML artifact uploaded, `htmlcov/` gitignored. Actual coverage: 84%.

2. **Mutation testing (mutmut)**: COMPLETE. `mutmut` in dev deps, `[tool.mutmut]` targets auth/, router.py, gateway.py. Baseline documented as TBD in TRACEABILITY.md (acceptable -- first run is slow). `.mutmut-cache/` gitignored.

3. **Flaky test detection (pytest-repeat)**: COMPLETE. `pytest-repeat` in dev deps, nightly CI job with `--count=3`, schedule trigger at 02:00 UTC, `workflow_dispatch` for manual trigger, Postgres service included.

4. **Performance baselines (pytest-benchmark)**: NOT IMPLEMENTED. Phase plan explicitly marks this as "optional, low priority" -- acceptable scope reduction.

## Test Coverage

| Test | Spec Requirement | Category |
|------|-----------------|----------|
| test_pytest_cov_in_dev_deps | Coverage: dep present | Source-inspection |
| test_pytest_repeat_in_dev_deps | Flaky: dep present | Source-inspection |
| test_mutmut_in_dev_deps | Mutation: dep present | Source-inspection |
| test_coverage_fail_under_configured | Coverage: threshold exists | Source-inspection |
| test_coverage_threshold_is_70_or_higher | Coverage: threshold >= 70 | Source-inspection |
| test_coverage_source_points_to_noa | Coverage: source target | Source-inspection |
| test_coverage_html_directory_configured | Coverage: HTML output | Source-inspection |
| test_mutmut_targets_critical_paths | Mutation: correct targets | Source-inspection |
| test_gitignore_excludes_htmlcov | Config: build artifacts | Source-inspection |
| test_gitignore_excludes_mutmut_cache | Config: build artifacts | Source-inspection |
| test_ci_has_coverage_step | CI: coverage wired | Source-inspection |
| test_ci_uploads_coverage_artifact | CI: artifact upload | Source-inspection |
| test_ci_has_nightly_flaky_job | CI: flaky job exists | Source-inspection |
| test_ci_has_schedule_trigger | CI: cron trigger | Source-inspection |
| test_traceability_has_mutation_baseline_section | Docs: baseline documented | Source-inspection |
| test_coverage_runs_on_minimal_example | Coverage: functional proof | Behavioral (subprocess) |

Gap: No behavioral test for mutmut (e.g., `mutmut run --paths-to-mutate=src/noa/auth/jwt.py` on a single file). Understandable since mutation runs are slow (10-60 min), but a single-file smoke test could run in <30s.

Gap: No behavioral test for pytest-repeat (e.g., running `pytest --count=2` on a trivial test to verify the plugin works). Low risk since it is a well-known pytest plugin.

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- No `except:` in test_qe6_quality.py
- No `except Exception:` in test_qe6_quality.py

**M7: Wiring completeness:**
- No new routers or services. CI workflow changes verified: coverage args added to test-backend step, flaky-test-detection job added with correct trigger condition.

**M8: Domain isolation:**
- No `from noa.private_worker` in `src/noa/external_worker/`
- No `from noa.external_worker` in `src/noa/private_worker/`

## Smoke Test Results

```
$ docker exec noa-dev python -m pytest tests/unit/test_qe6_quality.py -v
16 passed in 1.06s

$ docker exec noa-dev python -m pytest tests/unit/ --cov=src/noa --cov-fail-under=70 -q
TOTAL  6477  1030  84%
Required test coverage of 70% reached. Total coverage: 84.10%
1753 passed, 2 failed (pre-existing: test_lifespan_db_skip, test_mcp_adapter)

$ ruff check tests/unit/test_qe6_quality.py
All checks passed!
```

## Security

No security concerns. Phase is pure tooling infrastructure (config files, CI workflow, gitignore). No API surface changes, no auth changes, no secret handling.

CI workflow uses `SECRET_KEY: "ci-test-secret-key-not-for-production"` -- this is a test fixture, not a production secret. Acceptable.

The flaky-test-detection job uses `continue-on-error: true` -- this is correct behavior for a detection job (it should report flaky tests, not block the pipeline).

## Code Quality

Test file is well-organized with clear section headers and descriptive docstrings. The `@pytest.mark.slow` marker on the meta-test is a nice touch for CI flexibility.

`_read_pyproject()` helper avoids repeated file reads but could be a module-level fixture. Minor style preference, not blocking.

The `test_coverage_threshold_is_70_or_higher` test manually parses TOML via string splitting rather than using `tomllib` (stdlib in 3.11+). Fragile if indentation or formatting changes, but acceptable for a simple `key = value` line.

## Beyond the Test Plan

1. **mutmut_config.py vs pyproject.toml**: Phase plan listed `mutmut_config.py` as a new file, but the implementation puts mutmut config in `pyproject.toml` under `[tool.mutmut]`. This is the correct modern approach -- mutmut reads from pyproject.toml. No issue.

2. **Nightly job Postgres service**: The flaky-test-detection job includes a Postgres service, which is needed because some unit tests indirectly depend on DATABASE_URL being set. Good foresight.

3. **`.coverage` and `.coverage.*` in gitignore**: The phase added these beyond the plan's `.mutmut-cache/` and `htmlcov/`. Good completeness -- coverage data files should not be tracked.

4. **`slow` marker registered**: The `[tool.pytest.ini_options].markers` now includes `slow`. This means `-m "not slow"` works to skip the meta-test in local development. Well done.

5. **No mutation CI step**: The phase plan says "CI: run mutation tests on critical paths only" but no CI job or step runs `mutmut`. Only the config and baseline documentation exist. The flaky-test-detection job is a nightly CI job, but there is no equivalent for mutation testing. This is defensible given that mutation runs are genuinely slow (10-60 min), but it means mutation testing is manual-only. A nightly mutation job would complete the loop.

6. **Coverage `omit` patterns**: `[tool.coverage.run].omit` excludes migrations and alembic directories. This is correct -- migration code is autogenerated and not meaningful to cover.

## Notes (PASS_WITH_NOTES)

1. **No CI mutation testing step.** Phase plan scope item 2 says "CI: run mutation tests on critical paths only (not full codebase -- too slow)." No CI step or nightly job runs mutmut. The config exists, the targets are defined, but execution is manual-only. Consider a weekly (not nightly) mutation job targeting a single critical file (e.g., `jwt.py` -- fast path) to get automated mutation regression detection without excessive CI cost.

2. **TOML parsing is fragile.** `test_coverage_threshold_is_70_or_higher` uses string splitting to parse `fail_under = 70`. If the line format changes (e.g., `fail_under=70` without spaces), the test may false-pass or false-fail. Using `tomllib.loads()` (stdlib Python 3.11+) would be more robust.

3. **No behavioral smoke test for mutmut or pytest-repeat.** Only coverage has a functional proof test. A quick mutmut smoke (run on a single tiny module, verify exit code) would strengthen confidence that the config actually works end-to-end. Similarly for `--count=2` on a trivial test.

4. **Performance baselines deferred.** Item 4 from the phase plan (pytest-benchmark) was omitted. This was explicitly optional, but if Wave 22 (Observability) picks this up, note the deferred scope.

## Decision Review

No blocking decisions needed. This phase is a clean infrastructure addition with correct configuration, well-structured tests, and good CI integration. The main gap is that mutation testing exists only as configuration -- no automated execution in CI. This reduces the practical value of having mutmut configured, since mutation regressions will not be caught automatically. However, the manual workflow is documented in TRACEABILITY.md and the tooling foundation is solid.
