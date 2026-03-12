# QA Review: Phase QE3

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 5 tests trace to specific finding IDs (iOS-L2, W20-MED-3, W20-MED-4). Module docstring lists all three findings. |
| M2 | Negative Tests | PASS | W20-MED-3 test asserts absence of `continue-on-error` (negative check). Phase scope is documentation/config, not new runtime behavior. |
| M3 | Security Boundaries | PASS | No new secrets, no new endpoints, no new auth surface. iOS-L2 fix adds compile-time warning for disabled cert pinning. |
| M4 | Determinism | PASS | All tests read files from disk. No time, network, or randomness dependency. |
| M5 | Implementation Completeness | PASS | All 3 remaining open findings addressed. FINDINGS.md at 0 open. Scope correctly reduced from original 10-finding plan (7 were already resolved by Wave20-cleanup/PR7). |
| M6 | No Silent Error Swallowing | PASS | No new exception handlers. tools.py and mcp_adapter.py raise explicitly. |
| M7 | Wiring Completeness | PASS | No new routers, services, or endpoints. Changes are documentation/config only. |
| M2b | Write-Path Test Fidelity | PASS | No write-path tests in this phase. |
| M3b | Write-Path User Scoping | PASS | No new storage paths. |
| M4b | Mock Interface Accuracy | PASS | No mocks used. |
| M5b | Findings Currency | PASS | iOS-L2, W20-MED-3, W20-MED-4 all marked Resolved by QE3. Count updated to Open:0. |
| M5c | Related-Issue Scope | PASS | All remaining open findings addressed in a single phase. No siblings left unaddressed. |
| M2c | Source-Inspection Test Gate | PASS | All 5 tests are source-inspection. Behavioral companions not applicable: iOS-L2 is a Swift compile-time directive, W20-MED-3 is CI YAML config, W20-MED-4 is docstring/error-message content. Smoke test verified execute_tool actually raises with correct message. |
| M8b | Cross-Language Field Optionality | PASS | No endpoint changes. |
| M8 | Domain Isolation | PASS | No cross-domain imports. |
| S1 | Error Handling & Boundaries | PASS | execute_tool error message is actionable (tells developer to check set_gateway/set_registry). |
| S2 | Code Consistency | PASS | Docstring style matches existing codebase conventions. |
| S3 | Migration & Rollback | N/A | No DB changes. |
| S4 | Documentation | PASS | MCPToolAdapter has thorough deprecation docs. tools.py execute_tool has clear fallback explanation. |
| S5 | Integration Smoke Test | OPEN | All tests are source-inspection. No non-mocked integration test. This is an audit-fix phase (exempt per CI-010/CI-029 S5 streak rule). Smoke test was run manually and passed. |

## Test Plan Coverage
No formal test plan existed for QE3. The 5 tests directly verify the 3 finding resolutions plus FINDINGS.md integrity.

## Spec Compliance
QE3 scope per PHASE_DETAILS.md listed 10 findings. Seven were already resolved by Wave20-cleanup and PR7. The 3 remaining (iOS-L2, W20-MED-3, W20-MED-4) are all correctly addressed:

- **iOS-L2**: `#warning` directives added to both `#if DEBUG` blocks in `ServiceFactory.swift` (lines 55, 72). Clear message: "DEBUG build: certificate pinning is disabled -- do not connect to production endpoints".
- **W20-MED-3**: `continue-on-error: true` removed from E2E step in `web-ci.yml`. E2E failures now block the pipeline.
- **W20-MED-4**: `execute_tool` in `tools.py` has updated docstring and error message referencing tool gateway wiring. `MCPToolAdapter` in `mcp_adapter.py` has comprehensive DEPRECATED markers with McpRemoteAdapter references.

## Test Coverage
| Test | Finding | Category |
|------|---------|----------|
| test_ios_l2_warning_present | iOS-L2 | Source-inspection |
| test_w20_med3_no_continue_on_error | W20-MED-3 | Source-inspection |
| test_w20_med4_tools_py_message | W20-MED-4 (tools.py) | Source-inspection |
| test_w20_med4_mcp_adapter_deprecation | W20-MED-4 (mcp_adapter.py) | Source-inspection |
| test_findings_zero_open | FINDINGS.md integrity | Source-inspection |

All finding IDs mapped to tests. No untested findings.

## Anti-Pattern Scan Results
```
M6 - bare except / blind exception:
  tools.py: No bare except blocks. BLE001 exception on line 205 has noqa annotation and returns error dict (pre-existing).
  mcp_adapter.py: No exception handlers at all.

M7 - Wiring completeness:
  No new routers or services. N/A.

M8 - Domain isolation:
  grep "from noa.private_worker" src/noa/external_worker/ → No matches
  grep "from noa.external_worker" src/noa/private_worker/ → No matches
```

## Smoke Test Results
```
OK: tools.py imports
OK: execute_tool raises with gateway guidance
OK: mcp_adapter.py imports
OK: MCPToolAdapter deprecation markers
OK: FINDINGS.md Open: 0
All smoke tests passed.
```

## Security
- No new secrets, credentials, or API keys introduced.
- iOS-L2 fix improves security posture by making cert pinning bypass visible at compile time.
- W20-MED-3 fix improves CI gate strength by making E2E failures blocking.
- No new attack surface.

## Code Quality
- `tools.py`: execute_tool docstring is clear and actionable. Error message guides developers to check set_gateway/set_registry.
- `mcp_adapter.py`: Module-level, class-level, and method-level deprecation documentation. References replacement (McpRemoteAdapter) and original phase (TM6).
- `web-ci.yml`: Clean removal. No other changes to workflow structure.
- `ServiceFactory.swift`: `#warning` directives are idiomatic Swift for compile-time developer alerts.
- Ruff: all files pass (0 violations).
- Mypy: both modified Python files pass (0 errors).

## Beyond the Test Plan
1. **FINDINGS.md has "Open" entries in Section 6 (user-reported issues)**: Lines 1071-1073 show L10, L11, L12 as "Open". These are in a separate legacy table ("User-Reported Issues") and are feature requests, not audit findings. The main Tracking Summary table correctly shows 0 open. This is cosmetically confusing but not a blocking issue.
2. **Scope reduction from 10 to 3 findings**: The phase plan listed 10 findings but 7 were already resolved. The implementation correctly adapted. PLAN.md reflects the actual 5-test delivery.
3. **`except Exception as exc` in tools.py line 205**: Pre-existing BLE001 noqa. Returns error dict, does not swallow silently. Not a QE3 regression.

## Notes (PASS_WITH_NOTES)
1. **S5 OPEN (exempt)**: All 5 tests are source-inspection only. This is acceptable for an audit-fix phase per CI-010/CI-029 exemption. The smoke test verified runtime behavior outside pytest.
2. **FINDINGS.md Section 6 cosmetic inconsistency**: The legacy "User-Reported Issues" table (lines 1060-1075) contains 3 items marked "Open" (L10, L11, L12) which are feature requests. While the main Tracking Summary correctly shows Open:0, the presence of "Open" text elsewhere could confuse automated checks. Consider cleaning up Section 6 in a future phase.
3. **Original QE3 scope vs delivery**: PHASE_DETAILS.md lists 10 findings with substantial code changes (chat.py, cost.py, Settings.tsx, etc.). Only 3 were still open. The delta should be noted in PHASE_DETAILS.md for future reference.
