# CLAUDE.md — Project Instructions

## Session Start

1. Read `Plan/PLAN.md` for current project state (~125 lines, status table).
2. For phase details, search `Plan/PHASE_DETAILS.md` for the specific phase ID — never read the full file.

After milestones (phase/wave completion, QA verdicts), update:
- `Plan/PLAN.md` — status table row
- MEMORY.md — project state summary

## Project Overview

Noa is a governed personal AI agent with dual-domain architecture (private + external). Container-based domain isolation (Phase 1), scales to physical machine isolation (Phase 2). See SPEC.md for full spec.

### Key Directories (CI-004)

| Directory | Purpose |
|-----------|---------|
| `src/noa/` | Python backend (API, orchestrator, workers, tools, DB) |
| `web/` | React/TypeScript frontend |
| `tests/` | Test suite (unit, integration) |
| `tools/` | Utility scripts (notify.py, keychain_store.sh, pre-push-hook.sh) |
| `Plan/` | Project planning artifacts (PLAN.md, reviews, retros, CI) |
| `docker/` | Per-service Dockerfiles |
| `alembic/` | Database migrations |
| `.claude/skills/` | Agent skill definitions |
| `.claude/agents/` | Agent definitions |

## Session Focus (CI-001)

When the user asks you to implement, fix, or build something, start the work immediately. Do not spend the session exploring the codebase, creating plans, or asking clarifying questions unless:
1. The request is genuinely ambiguous (multiple valid interpretations)
2. The user explicitly asks for a plan or analysis first
3. A required dependency is missing and you cannot proceed

If exploration is needed, limit it to the minimum necessary to unblock implementation. Never let exploration consume more than ~20% of the session.

## Canonical Output Locations (CI-002)

Always write plans, waves, and task updates directly to `Plan/PLAN.md` and `Plan/PHASE_DETAILS.md` unless the user explicitly specifies a different file. Never create separate planning files.

When working within the multi-agent pipeline:
- Phase plans go in `Plan/PLAN.md` + `Plan/PHASE_DETAILS.md`
- Decisions go in `Plan/DECISION_LOG.md`
- Findings go in `Plan/FINDINGS.md`
- Reviews go in `Plan/REVIEWS/`
- Retros go in `Plan/RETROS/`
- CI analyses go in `Plan/CI/`

Never commit directly to `main` during phase work — use feature branches per the Git Workflow section.

## Docker Environment Awareness (CI-003)

This project runs in Docker containers (see `docker-compose.yml` and `docker-compose.dev.yml`). When suggesting commands, debugging steps, or code changes:

1. **All runtime behavior happens inside containers.** Code changes require a container rebuild or restart to take effect.
2. **File paths differ between host and container.** The repo is mounted at `/workspace` inside the dev container.
3. **SQLite WAL mode is incompatible with VirtioFS** (macOS Docker). Never suggest WAL journal mode for SQLite in Docker.
4. **Network context matters.** `localhost` inside a container refers to the container itself, not the host. Use Docker service names for inter-container communication.
5. **Never suggest deleting or dropping databases without first creating a backup.**

## Secret Hygiene

**Never output secrets in plaintext** — not in terminal, logs, or files. If unavoidable: explain what/why, wait for approval, prefer masked alternatives.

## Protected Documents

**SPEC.md** and **STRATEGY.md** govern all design decisions. **Never modify without explicit human approval.** Propose first, wait for approval, change only what's approved.

---

## Multi-Agent Pipeline

### Agents & Skills

| Agent/Skill | Role | Writes To |
|-------------|------|-----------|
| `/phase-planning` | Plan phases with spec-traceability | `Plan/PLAN.md` + `Plan/PHASE_DETAILS.md` |
| `implement` | Full-cycle agent: builds production-quality features (code + tests + wiring). Quality bar: "could you demo this right now?" | `tests/` + `src/` + `web/src/` |
| `code-reviewer` | Fast code review, pre-QA | stdout |
| `qa-review` | Adversarial review (post-impl) + health brief. **MANDATORY for every phase — never skip.** | `Plan/REVIEWS/` |
| `ci` | Continuous improvement. **Runs at wave boundary** (after retrospective). Finds recurring patterns across the full wave, proposes process fixes. P1 proposals = human gate. | `Plan/CI/` |
| `system-auditor` | Full-system audit at wave boundaries. Real HTTP requests, E2E flows, security, dead code, cross-phase integration. Read-only (never edits source). | `Plan/REVIEWS/` |
| `/retrospective` | Wave-level retro, estimation accuracy | `Plan/RETROS/` |

### Phase Pipeline

```
/phase-planning → implement agent → verify → code-reviewer → fix → qa-review (MANDATORY) → findings sync → complete
```

**Findings Sync (CI-015 — blocking):** Before marking a phase complete, update `Plan/FINDINGS.md` for every finding the phase resolves. Skipping this is a pipeline violation (same class as skipping QA).

### Wave Boundary

```
last phase complete → system-auditor → /retrospective → ci agent → human gate (wave review) → next wave planning
```

**Gates:**
- **Verify**: All tests pass + `ruff check` + `mypy` + app loads + feature is wired and callable
- **Integration**: Data flows end-to-end (stored data is readable where needed, UI actions produce real backend effects). "Could you demo this to the user right now?"
- **Code Review**: Fix Critical issues before QA
- **QA Review (MANDATORY — never skip)**: Adversarial review against `Plan/QA_CHECKLIST.md` (M1-M8, S1-S5). Max 2 cycles; on 2nd FAIL write `Plan/RCA/rca_{phase-id}.md`. After verdict, generates `Plan/REVIEWS/health_{date}.md`
- **CI Agent (wave boundary only)**: Runs after the retrospective at wave end. Reads `Plan/CI/signals.md`, `Plan/REVIEWS/audit_{date}.md`, and session facets (`~/.claude/usage-data/facets/*.json`) for cross-wave pattern analysis. P1 proposals become a human gate. **Enforcement:** Do not start next-wave planning until `Plan/CI/analysis_{date}_{wave-id}.md` exists.
- **System Audit (wave boundaries)**: Full-system health check before starting next wave.
- **Retrospective (wave boundaries — never skip)**: Runs after system-auditor at every wave boundary. **Enforcement:** Do not start next-wave planning until `Plan/RETROS/retro_{wave-id}.md` exists.

**Implementation rules:**
- Code must be wired into the running system
- No bare `except` blocks
- >=1 non-mocked integration test per phase that tests real user-visible behavior
- **Minimize mocks**: only mock system boundaries (external APIs, network, filesystem). Never mock internal services, DB, or the function under test.
- **No dead-end stores**: if data is stored somewhere, something must read it. If nothing reads it, don't store it.
- **Tool-specific behavior**: each tool must be tested for its actual auth model (OAuth vs API key vs token), not generic one-size-fits-all.
- **iOS↔backend contract audit**: For phases that modify iOS↔backend contracts: before implementation, audit ALL Pydantic request model fields for Swift-encoder compatibility (required vs optional, types). A field left required when iOS may omit it is a P1 bug. Swift's `JSONEncoder` omits `Optional` fields by default — assume any Swift-facing endpoint may omit any optional Swift field.
- **S5 integration baseline (CI-016)**: Each phase with DB-touching endpoints must have ≥1 non-mocked integration test using real DB (or ASGI test client with real DB). S5 OPEN is acceptable only for inherently untestable surfaces (CI/CD workflows, shell scripts, iOS device-only flows).
- **Pre-QA deliverable check (CI-033)**: Before submitting for QA, verify every planned file deliverable listed in PHASE_DETAILS.md exists on disk. This is a 2-minute check that prevents completeness FAIL verdicts.

### Cross-Cutting Verification (After Parallel Merge)

Import all modified modules together, run full test suite, check domain isolation (`grep -rn "from noa.private_worker" src/noa/external_worker/` and vice versa). Rollback on failure.

### Human Gates

Pause and wait at:
1. Wave planning approval
2. Architectural FAIL from QA
3. CRITICAL issue in `Plan/FINDINGS.md`
4. P1 proposals from CI agent
5. Wave completion review (after system-auditor)

**At every human gate, immediately notify before pausing:**
```bash
python3 tools/notify.py "<Gate Name>" "<What decision is needed>"
```
Example: `python3 tools/notify.py "Wave Planning" "Wave 15 plan ready for approval"`

### Escalation

| Situation | Action |
|-----------|--------|
| Implement agent can't derive tests from spec | STOP, ask human to clarify spec |
| Implement agent fails 2x on same feature | Orchestrator tries once, then escalates |
| QA fails once | Fix blocking issues, re-run QA (cycle 2) |
| QA fails twice | Write RCA (`Plan/RCA/rca_{phase-id}.md`), escalate |
| QA review skipped | **Pipeline violation** — go back and run QA before marking complete |
| CI agent skipped at wave boundary | **Pipeline violation** — run CI before starting next wave |
| Security concern | Immediate CRITICAL escalation |

### Continuous Improvement

**CI agent runs at wave boundary — after the retrospective, before next-wave planning.** This is mandatory and not optional. It analyzes the full wave's signal log for patterns, not individual phase incidents. P1 proposals become human gates. Human approves all proposals before application.

### Findings Lifecycle

`Plan/FINDINGS.md` is the single source of truth for all audit findings.

**When resolving a finding:**
1. Update the finding's row in the **Tracking Summary** table: set Status to `**Resolved**`, set Resolved By to the phase ID
2. Update the **Open/Resolved counts** at the bottom of the table
3. Do this immediately after the fix passes tests — not later, not in batch

**When discovering a new finding:**
1. Add a row to the **Tracking Summary** table with Status `Open`
2. Add the detailed description in the appropriate severity section below
3. Update the **Open/Resolved counts**

### Status Documents

Keep current at all times:
- `Plan/PLAN.md` — status table, updated before/after each phase
- `Plan/PHASE_DETAILS.md` — detailed phase descriptions (append new phases here)
- `Plan/FINDINGS.md` — tracking summary + detailed findings (update on resolve/discover)

### Wave-Level E2E Gate

After Wave 16 (Playwright), every wave must pass `cd web && npm run test:e2e`.

## Git Workflow

- **No GitHub push** — only human pushes to remote
- **Worktrees** for agent isolation (never share between agents)
- **Branch**: `agent/<agent_id>-<task_slug>`
- **Commit**: `<scope>: <summary>`
- **Merge**: only after tests + static gates pass

Process: acquire lock → merge `--no-ff` → ruff + mypy → tests → release lock. On failure: abort, keep branch, write report.
