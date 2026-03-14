# Project Health Brief — 2026-03-14 (sp-transparency)

**Score: 7/10**
Starting at 5: +0 (Wave 22 still in progress — FR5/FR6 remain), +0 (last QA verdict PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), +1 (application security posture fully green), +0 (infrastructure security has warn — no lockfile, one old curl rule — mid-wave, not re-audited), +1 (E2E + integration tests exist: Playwright + real-DB integration). Subtract: -1 for infrastructure warn (carried from QE6). Score = 5+1+1+1-1 = 7. Stable at 7/10, same as FR4 brief. No change expected until Wave 22 closes.

## What Happened (since last brief)

1. **System prompt transparency refactor landed** — eliminated 3-way duplication (DB, hardcoded in runner, and file). `prompts/system_prompt.txt` is now the single source of truth. GET /settings, PATCH /settings, GET/PUT /system-prompt, and the orchestrator runner all read from the same file.
2. **Two orchestrator bugs fixed** — agent node: `if not tool_calls and content:` was missing the empty-content case after a tool round; responder node: was picking up empty-content assistant messages as the final response. Both have regression tests.
3. **53 tests pass, ruff clean** — the refactor removed all old dead code (_build_system_prompt, load_default_system_prompt, is_default) without breaking any existing tests. Tool context and personality are now explicitly separated.

## Greatest Risk

**The system_prompt DB column is now a silent ghost.** Migration 013 added it, the ORM model still declares it, but the service never reads or writes it anymore. The service comment says "there is no DB column" — which is false. Any user who stored a system prompt in the DB (before this refactor) now has orphaned data that is silently ignored. More practically: a future developer reading `UserSettings` in models.py will see `system_prompt: Mapped[str | None]` and assume it's the authoritative value — which could reintroduce the dual-source problem this refactor was designed to fix. A cleanup migration removing the column would eliminate this confusion before it compounds.

## Decisions Needed

- **Drop system_prompt DB column:** Add migration 017 to drop `user_settings.system_prompt` and remove the column from the ORM model. This closes the schema drift and makes the code match its comments. Low effort, high clarity.
- **Add length limit to PATCH /settings:** The dedicated PUT /system-prompt enforces 10,000 chars; PATCH /settings does not. Add `Field(max_length=10_000)` to `UpdateSettingsRequest.system_prompt` to keep both write paths consistent.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All endpoints (GET/PUT /system-prompt, GET/PATCH /settings) require require_auth. No auth changes. |
| Secrets | ok | No hardcoded secrets. System prompt is user-provided text, not credentials. |
| Domain isolation | ok | No cross-domain imports in any changed files. Isolation from FR1 intact. |
| Input validation | warn | PUT /system-prompt enforces 10,000-char limit; PATCH /settings does not. An authenticated user can write an arbitrarily large file via PATCH. Single-user agent so self-inflicted, but inconsistent. |
| Error handling | ok | read_system_prompt OSError handled gracefully. All runner except blocks log. No success-on-error. |

## Security Posture — Infrastructure

N/A — mid-wave. Last audited at QE6 (2026-03-12).

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 107 scoped allow rules (QE6 baseline). No changes in this refactor. |
| Docker config | ok | `docker/noa-api/Dockerfile:13` now includes `COPY prompts/ ./prompts/`. Resolved FR4 gap. |
| CORS / network exposure | ok | No changes. Explicit localhost origins from QE6. |
| Secrets in repo | ok | `.env`/`.env.secrets` gitignored. No tracked env files. |
| Dependency pinning | warn | Loose `>=` pins, no lockfile. Carried from prior waves. |

## Risks You Are Taking

1. **Schema drift — ghost DB column (medium probability, medium impact):** `UserSettings.system_prompt` column exists in DB and ORM model but is never used. A future developer reading the model may trust this column, silently reintroducing the dual-source problem. Fix requires a migration and ORM cleanup. Probability it causes confusion: medium. Impact of confusion: medium (data integrity regression).

2. **PATCH /settings length bypass (low probability, low impact):** An authenticated user can send an arbitrarily large system_prompt via PATCH /settings, bypassing the 10,000-char limit on the dedicated endpoint. Since this is a personal agent, blast radius is self-inflicted. Fix: 1-line Field annotation change.

3. **No lockfile (ongoing, medium probability, medium impact):** Transitive dependency drift could silently break the build or introduce vulnerabilities. Wave 22 correctness/UX work is a good window to generate a lockfile before the next feature wave.
