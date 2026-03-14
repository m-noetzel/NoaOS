# Project Health Brief — 2026-03-14 (FR6)

**Score: 7/10**
Starting at 5: +0 (Wave 22 not yet complete — FR6 just done, no FR7 declared, but 5 of 6 planned findings phases now complete), +0 (FR6 verdict was PASS_WITH_NOTES, not PASS), +1 (zero critical findings open — 4 open, all Low), +1 (application security fully green — auth, secrets, domain isolation, error handling), +0 (infrastructure has two warns carried since QE6 — prompts/ Docker gap and no lockfile), +1 (E2E integration: 18 Playwright + 30+ Postgres integration tests), -1 (infrastructure warn: prompts/ Docker gap + no lockfile, both unresolved). Score: 5+1+1+1-1=7. Trajectory: stable at 7 (same as FR4). Infrastructure gap keeps score from rising to 8.

## What Happened (since last brief)

1. **Wave 22 UX/findings cleanup is effectively complete.** FR1 (domain isolation) → FR2 (memory fixes) → FR3 (data integrity + infra) → FR4 (chat UX) → FR5 (cost dashboard) → FR6 (tools, settings, iOS backend health) — 9 spec requirements resolved in a single wave.
2. **FR6 closed 9 long-standing findings**: UX-H6 (Notion auto-grant), iOS-H5 (iOS not connected to backend), UX-M2/M3/M4/M8/M9/M10 (governance toggle, thread rename, agent limits, tools page filter/search/scopes), UX-L1 (logo flex-shrink-0). FINDINGS.md now shows 4 open (all Low).
3. **FR5 health brief was skipped.** FR4 was the last brief. FR5 and FR6 are both delivered since then. Key FR5 additions: cost/pricing endpoint, budget_limit_usd in summary, empty states for Artifacts/Queue pages.

## Greatest Risk

**No dependency lockfile and the `prompts/` Docker gap remain unaddressed after 5 consecutive waves.** The Docker gap (`prompts/system_prompt.txt` not COPY'd into the image) means every deployed container silently serves an empty default system prompt. This has been flagged in FR4's brief and carried since. It is a 1-line Dockerfile fix. The lockfile absence means any `pip install` in CI could pull a different transitive version than what was tested, silently breaking the build. Both are simple operational risks with easy fixes that keep getting deferred to "next wave." If Wave 22 closes without fixing these, they become permanently deferred risk.

## Decisions Needed

- **Wave 22 closure**: Is FR6 the last phase of Wave 22, or is there an FR7? If Wave 22 is complete, the wave boundary pipeline (system-auditor → retrospective → CI agent) must run before Wave 23 planning.
- **Docker prompts/ gap**: A 1-line `COPY prompts/ ./prompts/` in `docker/noa-api/Dockerfile` has been deferred since FR4. Decide: fix now in Wave 22-cleanup, or accept the production behavior (empty default system prompt)?

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All FR6 endpoints auth-gated: PATCH /threads/{thread_id}, PATCH /settings, GET+PATCH /tools/scopes, POST /tools/{name}/credentials. iOS health check uses unauthenticated /health endpoint — correct, by design. |
| Secrets | ok | No hardcoded secrets. Credential store is in-memory (pre-existing TM1 limitation). Auto-grant idempotency verified. No unsafe `or ""` fallbacks on secrets. |
| Domain isolation | ok | Thread rename scoped to user_id at query level (IDOR impossible). Scope overrides keyed by uid. No cross-domain imports. |
| Input validation | ok | Thread title: empty (422) and >256 chars (422) both enforced in handler. New settings fields: no bounds on integer values (S1, non-blocking for single-user). |
| Error handling | ok | All 3 new except BLE001 blocks log with exc_info=True. None return HTTP 200 on DB error. _auto_grant_capability is explicitly best-effort with documented silent degradation. |

## Security Posture — Infrastructure

N/A — mid-wave. Last fully audited at QE6 (2026-03-12). Carrying forward from FR4 brief.

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 107 scoped allow rules (QE6 baseline). No dangerous patterns. No change since FR4. |
| Docker config | warn | `prompts/system_prompt.txt` still absent from Docker image — 1-line Dockerfile fix deferred since FR4. No root user, no privileged, no secrets in ENV. |
| CORS / network exposure | ok | Explicit localhost origins. No changes in FR5/FR6. |
| Secrets in repo | ok | `.env`/`.env.secrets` gitignored. No tracked env files. |
| Dependency pinning | warn | Loose `>=` pins, no lockfile. Unresolved since Wave 19. |

## Risks You Are Taking

1. **Docker prompts/ gap (low probability, low-medium impact):** `prompts/system_prompt.txt` not included in the production Docker image. Every deployed instance serves an empty system prompt on first use. This silently degrades the agent's default behavior without an error. Easy 1-line fix. Has been deferred for 4 waves.

2. **Scope overrides lost on restart (low probability, low impact — single-user):** `_scope_overrides` in `tools.py` is in-memory. Any scope configuration via `PATCH /tools/scopes/{scope_name}` is lost on server restart. For a single-user personal assistant, this is a minor annoyance but not a data safety risk. Tracked as FR6-L1.

3. **No dependency lockfile (ongoing, medium probability, medium impact):** Transitive dependency drift could silently break the build on any `pip install`. With Wave 22 essentially complete and Wave 23 upcoming, this is the right moment to generate a lockfile and pin everything before starting new feature work.
