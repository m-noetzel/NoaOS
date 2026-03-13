# Project Health Brief — 2026-03-13 (FR4)

**Score: 7/10**
Starting at 5: +0 (Wave 22 still in progress — FR2-FR6 remain Planned), +0 (last QA was PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), +1 (application security posture fully green), +0 (infrastructure security has warn — curl wildcard allow rule, no lockfile — mid-wave, not re-audited), +1 (E2E + integration tests: 18 Playwright + 30+ Postgres integration tests). No open criticals. Subtract: -1 for infrastructure warn (carried from QE6/FR1). Score: 5+1+1+1-1=7. Trajectory: stable at 7/10 (same as FR1). Mid-wave, no change expected until FR6 closes the wave.

## What Happened (since last brief)

1. **FR4 delivered all 6 UX fixes**: SSE keepalive pings (UX-H1), send button always-enabled (UX-H2), system prompt file-backed + Settings save button (UX-H3), tool call details expandable in EventTimeline (UX-H5), optimistic user message (UX-H9), and ActivityStream tool lifecycle events (UX-H10). 19 backend + 18 frontend tests.
2. **FR1 findings closed**: BE-C3 (Critical), BE-H8 (High), BE-H11 (High) resolved by domain isolation enforcement. Domain column added, thread/memory endpoints filtered by domain.
3. **Wave 22 is now 1/6 complete (FR1 done)**. FR2-FR6 remain Planned. The wave delivers correctness and UX fixes across backend data integrity, infra hardening, and frontend polish.

## Greatest Risk

**Wave 22 has 5 phases remaining and FR4 phase findings not synced.** FR4 resolved 6 findings (UX-H1, UX-H2, UX-H3, UX-H5, UX-H9, UX-H10) but FINDINGS.md still shows them Open — a CI-015 violation. If finding sync discipline degrades further, FINDINGS.md will lose utility as the source of truth for open issues. The `prompts/` Docker gap found in FR4 (default system prompt silently absent in deployed containers) is an additional example of a feature that tests green in dev but partially fails in production. Both issues compound if FR2-FR6 also ship without fixing them.

## Decisions Needed

- FINDINGS.md must be updated for FR4 (UX-H1/H2/H3/H5/H9/H10 → Resolved/FR4) before marking FR4 complete. This is a CI-015 pipeline requirement.
- `docker/noa-api/Dockerfile` needs `COPY prompts/ ./prompts/` or a documented decision to accept the empty default. Low effort, high clarity.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All new endpoints (GET/PUT /system-prompt) gated by require_auth. No auth changes. |
| Secrets | ok | No hardcoded secrets. System prompt content is user-provided text, not sensitive. |
| Domain isolation | ok | FR1 enforced domain isolation on threads/memory. No cross-domain imports. FR4 adds no new domain surfaces. |
| Input validation | ok | System prompt bounded to 10,000 chars (422 on over-limit). Empty input handled gracefully (toast). |
| Error handling | ok | All except blocks log and return. No success responses on DB error. noqa BLE001 annotated throughout. |

## Security Posture — Infrastructure

N/A — mid-wave. Last audited at QE6 (2026-03-12).

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 107 scoped allow rules (from QE6 baseline). No dangerous patterns. |
| Docker config | warn | `prompts/system_prompt.txt` not in Docker image — discovered FR4. No root, no privileged, no secrets in ENV. |
| CORS / network exposure | ok | Explicit localhost origins from QE6. No changes in FR4. |
| Secrets in repo | ok | `.env`/`.env.secrets` gitignored. No tracked env files. |
| Dependency pinning | warn | Loose `>=` pins, no lockfile. Carried from prior waves. |

## Risks You Are Taking

1. **FINDINGS.md drift (medium probability, medium impact):** Six findings resolved by FR4 have not been marked Resolved. If this pattern continues through FR2-FR6, the findings count becomes unreliable and CI-015 violations accumulate. Fix: enforce findings sync as blocking before each phase completion.

2. **prompts/ absent from Docker image (low probability, low-medium impact):** In a deployed container, `_load_default_system_prompt()` silently returns `""`. New users will see a blank system prompt until they save a custom one. The feature works in dev. Unlikely to cause crashes but degrades first-run experience. Fix: 1-line Dockerfile change.

3. **No lockfile (ongoing, medium probability, medium impact):** Transitive dependency drift could silently break the build or introduce vulnerabilities. Now Wave 21 complete and Wave 22 is mostly correctness/UX work, this is the right window to generate a lockfile before the next feature wave.
