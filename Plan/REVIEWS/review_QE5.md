# QA Review: Phase QE5

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 5/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Test file cites SPEC.md SS34. All 30 tests map to traceability script behaviors. |
| M2 | Negative Tests | PASS | test_check_returns_nonzero_on_critical_orphans, test_ignores_files_without_spec_refs, test_orphaned_when_neither |
| M3 | Security Boundaries | PASS | No secrets, no API endpoints, no auth. Script is read-only analysis tool. |
| M4 | Determinism | PASS | No wall-clock time in assertions, no network calls, no randomness. |
| M5 | Implementation Completeness | PASS | All 3 files listed in phase plan delivered: tools/traceability.py, Plan/TRACEABILITY.md, ci.yml updated. |
| M6 | No Silent Error Swallowing | PASS | No except blocks in traceability.py. OSError on file read is caught with `continue` which is appropriate for graceful skip of unreadable test files. |
| M7 | Wiring Completeness | PASS | CI step added to static-analysis job in ci.yml. continue-on-error: true is justified by known Phase 2 orphans. |
| M8 | Domain Isolation | PASS | tools/traceability.py has no noa imports -- purely a standalone analysis script. |
| M2b | Write-Path Test Fidelity | PASS | N/A -- no DB writes. |
| M3b | Write-Path User Scoping | PASS | N/A -- no user-scoped data. |
| M4b | Mock Interface Accuracy | PASS | No mocks used -- tests operate on real or synthetic data. |
| M5b | Findings Currency | PASS | No findings resolved by this phase. |
| M2c | Source-Inspection Test Gate | PASS | The traceability script parses source files but the tests include behavioral companions (build_coverage, generate_markdown, run()). |
| S1 | Error Handling & Boundaries | PASS | Empty collections handled (empty phase map, empty test map produce Orphaned status). |
| S2 | Code Consistency | PASS | Follows project naming conventions. Clean module structure. |
| S3 | Migration & Rollback | PASS | N/A -- no DB changes. |
| S4 | Documentation | PASS | Module docstring with usage examples, all functions have docstrings with type annotations. |
| S5 | Integration Smoke Test | PASS | TestEndToEnd class runs against real SPEC.md, PHASE_DETAILS.md, and test files. test_check_mode_cli_exits_nonzero_on_real_gaps runs the script as a subprocess. |

## Test Plan Coverage
No test plan was written for QE5. Review conducted independently.

## Spec Compliance
Phase plan specified 3 deliverables:
1. `tools/traceability.py` -- delivered, functional, 409 lines
2. `Plan/TRACEABILITY.md` -- delivered, 128 sections analyzed, 97 covered (76%)
3. `.github/workflows/ci.yml` traceability check step -- delivered, lines 200-206

The phase plan estimated ~10 tests; 30 were delivered (3x over). Good coverage depth.

## Test Coverage

| Test Class | Count | What it covers |
|------------|-------|----------------|
| TestParseSpecSections | 4 | Section header extraction from SPEC.md (top-level, subsections, dedup, real file) |
| TestParsePhaseDetails | 4 | Phase-to-section mapping from PHASE_DETAILS.md (standard, QE-style, real file) |
| TestParseTestFiles | 4 | Spec ref extraction from test file docstrings (module, function, no-ref, real suite) |
| TestBuildCoverage | 8 | Status computation (Covered/Partial/Orphaned), parent inheritance, critical flag |
| TestGenerateMarkdown | 3 | Markdown table structure, orphan listing, summary counts |
| TestCheckMode | 3 | Non-zero exit on critical orphans, zero when all covered, CLI subprocess test |
| TestEndToEnd | 4 | Full pipeline on real codebase, coverage threshold guard, known phase/test checks |

Notably strong: 4 tests run against the real codebase (not just synthetic data), which prevents the script from passing with synthetic data but failing on the actual project.

## Anti-Pattern Scan Results

**M6: Bare except blocks:**
No `except:` or `except Exception:` in tools/traceability.py. One `except OSError: continue` which is appropriately specific.

**M7: CI wiring:**
```yaml
      - name: Requirements traceability check
        run: python tools/traceability.py --check --output /dev/null
        continue-on-error: true
```
Wired in static-analysis job. continue-on-error: true is justified -- the 9 critical orphans are all Phase 2 deferred or explanatory sections.

**M8: Domain isolation:**
tools/traceability.py imports only stdlib (re, sys, pathlib, argparse, collections, datetime). No noa imports.

## Smoke Test Results
```
Import OK
SPEC sections: 128
Phases with spec refs: 84
Test files with spec refs: 68
Coverage: 97 covered, 19 orphaned out of 128
Markdown generated: 14634 chars
run() OK, exit_code=0
run(check=True) correctly returns 1
All smoke tests PASSED
```

All 30 pytest tests pass. Script runs cleanly in both generate and check modes.

## Security
No security surface in this phase. The script reads files and generates a markdown report. No API endpoints, no auth, no user input beyond CLI args.

## Code Quality

**Ruff violation (non-blocking):** `tools/traceability.py:326` has E501 (line too long, 90 > 88 chars). This is in the `_indicators` dict literal. Minor.

**Deprecation warning:** `datetime.utcnow()` on line 277 is deprecated in Python 3.12+. Should use `datetime.now(datetime.UTC)`. Non-blocking but will eventually break.

**Code design:** The script is well-structured with clear separation: parsing, coverage computation, markdown generation, and main entry point. Parent-child inheritance logic is correct and tested. The regex patterns handle both `# N.` and `## N.M` header formats.

## Beyond the Test Plan

1. **Critical orphan justification is sound.** I verified all 9 critical orphans against SPEC.md:
   - SS2.3 "Why This Matters" -- explanatory prose, not a testable requirement
   - SS4.2 "Upgrade Path Invariant" -- Phase 1-to-2 upgrade procedure
   - SS4.3 "Phase 1 Machine Requirements" -- hardware specs
   - SS7.2 "Phase 2 -- Dual Machine" -- explicitly Phase 2
   - SS10.2 "No Raw Private Content on Control Plane" -- Phase 2 invariant (but the concept is partially testable in Phase 1 via domain isolation tests)
   - SS10.3 "Canary Token Tests" -- Phase 2 testing technique
   - SS11.4 "Compromise Response" -- operational procedure, not code
   - SS20.2 "Phase 2: macOS pf Firewall" -- explicitly Phase 2
   - SS20.5 "mTLS Operations (Phase 2 Only)" -- explicitly Phase 2

2. **Interesting gap: SS10.2 and SS10.3 describe invariants that are partially testable in Phase 1.** The "no raw private content on control plane" invariant is enforced by domain isolation (already tested elsewhere), and canary tokens could be a useful testing technique. These are correctly flagged as orphans because no phase or test explicitly cites them, but the underlying invariant IS tested via DW3/QC4 domain isolation tests. This is a traceability gap, not a coverage gap.

3. **The script does not detect transitive coverage.** If SS10.2 says "no raw private content on control plane" and that's tested via domain isolation tests that cite SS8.3 rather than SS10.2, the traceability matrix shows SS10.2 as orphaned even though the behavior is tested. This is a known limitation of text-matching traceability. Acceptable for Phase 1.

4. **TRACEABILITY.md is a generated file -- should it be gitignored?** Currently it's tracked. If the CI step regenerates it on every run (`--output /dev/null` avoids this), the committed version may drift from what CI sees. Since the CI step uses `--output /dev/null`, this is fine -- the committed TRACEABILITY.md is a reference snapshot, not a CI gate artifact.

## Notes (PASS_WITH_NOTES)

1. **Ruff E501 on line 326 of tools/traceability.py.** The `_indicators` dict literal is 90 chars (limit 88). Minor fix: split across lines.

2. **`datetime.utcnow()` deprecation on line 277.** Replace with `datetime.now(datetime.UTC)` to avoid future breakage. Currently produces a DeprecationWarning in Python 3.12+.

3. **SS10.2/SS10.3 are labeled "orphaned" but their invariants are partially covered by domain isolation tests.** Consider adding `SPEC.md SS10.2` citations to existing domain isolation test files (test_qc4_domain_isolation.py) to close the traceability gap without adding new tests.

## Decision Review
No architectural decisions needed. The continue-on-error approach for known Phase 2 orphans is the right call -- it avoids blocking CI while still surfacing the information. The 76% coverage rate is a reasonable baseline for a project that has significant Phase 2 deferred sections.
