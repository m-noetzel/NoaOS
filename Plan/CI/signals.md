# CI Signal Log

QA review agents append one row per phase after verdict.

| Phase | Date | Verdict | Summary |
|-------|------|---------|---------|
| GO1 | 2026-03-12 | PASS_WITH_NOTES | 28 tests, Google OAuth2 backend (4 endpoints + CSRF + encrypted tokens). 23 ruff violations in test file. _oauth_states no TTL. _get_live_google_client fragile (4 private attrs). |
| GO2 | 2026-03-12 | PASS_WITH_NOTES | 15 tests, Google OAuth web UI (Settings section + GoogleCallback page + route). All mocked (no integration). Missing test for authorize-failure path. No real OAuth flow tested across GO1+GO2. |
| GO3 | 2026-03-12 | PASS_WITH_NOTES | 16 Swift tests (9 service + 7 ViewModel), iOS Google OAuth via ASWebAuthenticationSession. S5 open (no non-mocked integration test -- inherent to iOS). Missing ViewModel error-path tests (loadStatus/disconnect failure). Backend platform=ios redirect untested. Wave 20 complete. |
| FR5 | 2026-03-13 | PASS_WITH_NOTES | 12 Python + 11 frontend tests. Cost/Runs/Dashboard UX (UX-H4/H7/H8/H11/M1/M5/M6/M7). All tests pass, wiring clean, auth-gated, user-scoped. 2 ruff E501 in cost.py. CostRecord.run_id typed string in types.ts but backend returns null. No negative test for invalid period param (422). |
| FR6 | 2026-03-14 | PASS_WITH_NOTES | 19 Python + 18 frontend + 8 Swift tests. Thread rename, governance/agent-limit settings, tool scopes, Notion auto-grant, iOS backend health. All pass. Top issue: max_tool_calls/max_retries/timeout_seconds have no Pydantic bounds (accept negative values). Scope overrides in-memory only (lost on restart). |
| CI-W22 | 2026-03-14 | CI ANALYSIS | Wave 22 boundary. 6 phases (FR1-FR6), all PASS_WITH_NOTES. Dead-end stores recur (W20 DE3 + W22 FR6) -- CI-042 (P1) broadens M7 to cover DB-persisted fields. CI-043 (P2) adds tsc --noEmit to verify gate. CI-044 (P3) signal log completeness. CI-031 partially effective (app.state only). CI-023 still not effective (0% test plan compliance). System-auditor: 7.2/10 (container-blind). 27 findings resolved, 4 open (all Low). |
