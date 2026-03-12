# Project Health Brief -- 2026-03-12 (DE1 Cycle 2)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: 6 of 7 phases remain), +0 (last QA PASS_WITH_NOTES, not PASS), +0 (10 open findings including 2 high -- no critical), -1 (application security warn: BE-M5, FE-L1 carried from PR7), +0 (infrastructure security N/A mid-wave, prior baseline had warn), +1 (E2E exists: 18 Playwright + 22 Python integration + 8 Swift integration), +1 (DE1 cycle 2 resolved all prior blockers -- CI pipeline now structurally complete). Result: 6, clamped to 6/10. Recovered from 4 at DE1 cycle 1, back to PR7 level.

## What Happened (since last brief)
1. DE1 cycle 2 resolved all 3 blocking issues from cycle 1: cd.yml, web-ci.yml, ios-ci.yml now delivered; Postgres service block added to ci.yml; pre-push hook upgraded to loud WARNING.
2. Full CI/CD pipeline now structurally complete: 4 workflow files, 74 tests (43 + 31), pre-push hook with installer.
3. QA verdict upgraded from FAIL to PASS_WITH_NOTES. Remaining notes: coverage gate not implemented, E2E step is advisory (continue-on-error: true), PLAN.md test count stale.

## Greatest Risk
**The CI pipeline has never been executed in GitHub Actions.** All 74 tests validate YAML structure locally, and the smoke test confirms correct file properties. But until someone pushes to a GitHub repo with Actions enabled, the workflows are untested in their actual runtime environment. The Postgres service, action versions, and npm/pip caching could fail in ways that local YAML parsing cannot detect. The first real push is the true integration test -- and it should happen soon after commit.

## Decisions Needed
- **When to enable GitHub Actions?** The workflows are ready. The first push to a GitHub remote with Actions enabled will be the real validation. Plan for this before relying on CI for merge protection.
- **Harden E2E gate?** web-ci.yml runs E2E with continue-on-error: true. Once Playwright tests prove stable in CI, flip to false to make the E2E gate enforcing.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT sanitized, httpOnly cookies, rate limiting, no secret fallbacks |
| Secrets | ok | No hardcoded secrets in src/. CI SECRET_KEY clearly labeled non-production. cd.yml uses secrets.GITHUB_TOKEN. |
| Domain isolation | ok | No cross-domain imports |
| Input validation | ok | Pydantic validation on all endpoints |
| Error handling | warn | BE-M5 (MemoryStore.store user_id gap), FE-L1 (stack trace in ErrorBoundary) -- carried from PR7 |

## Security Posture -- Infrastructure
N/A -- mid-wave. Reusing Wave 19 boundary baseline (PR7 brief). Key items: 100+ Claude Code allow rules (warn), loose dep pinning (warn), Docker/CORS/secrets all ok. New: all 4 GitHub Actions workflows use explicit permissions blocks with least-privilege (contents: read on CI, packages: write only on CD).

## Risks You Are Taking
1. **CI pipeline untested in real GitHub Actions environment (medium impact, medium likelihood).** Structural validation passes but runtime behavior (Postgres service startup, action version compatibility, npm/pip cache behavior) is unverified. Mitigated by the thorough YAML validation tests.
2. **Two high-severity findings still open (medium impact).** BE-H4 (SSE replay cursor instability) and BE-H5 (raw UPDATE bypassing RunService). Both affect user experience but are not security issues. Carried since Wave 19.
3. **Coverage gate not implemented (low impact).** The planned pytest-cov >=60% threshold is absent. Tests run without coverage measurement. Quality enforcement is structurally weaker than planned. Can be added incrementally.
