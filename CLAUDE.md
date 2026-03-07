# CLAUDE.md — Project Instructions for AI Assistants

## Project Overview

Noa is a governed personal AI agent with dual-domain architecture (private + external) running on local hardware. It starts on a single machine with container-based domain isolation (Phase 1) and is designed to scale to physical machine isolation (Phase 2). See SPEC.md for the full technical specification.

## Secret Hygiene

**Never suggest commands that output secrets, passwords, API keys, or tokens in plaintext** — not in terminal output, logs, or file contents. This includes commands like `env | grep PASSWORD`, `cat .env`, or any command that would display credentials on screen.

If inspecting a secret value is unavoidable for debugging:
1. Tell the user **what** the command will reveal and **why** it's needed.
2. Wait for explicit approval before suggesting it.
3. Prefer masked alternatives (e.g., check if a variable is set without printing its value).

Transparency is everything. When in doubt, ask first.

---

## Protected Documents

**STRATEGY.md** and **SPEC.md** are foundational documents that govern all design and implementation decisions across the Noa ecosystem.

- **SPEC.md** defines the complete technical specification for Noa — architecture, security model, execution invariants, contracts, and requirements. It is the single source of truth for what Noa is and how it works.
- **STRATEGY.md** is the cross-project strategy linking Noa and TheCoach. It defines product positioning, dependency direction, integration contracts, phasing, kill metrics, and design invariants that inform both projects.

### Rule: Never modify STRATEGY.md or SPEC.md without explicit human approval.

These documents must not be edited, rewritten, or have content added/removed by an AI assistant unless the human owner has clearly and specifically approved the change. This applies to all modifications — including "minor" fixes, formatting changes, rewording, or structural reorganization.

If a change to either document seems necessary:
1. Describe the proposed change and the reasoning to the human.
2. Wait for explicit approval before making any edit.
3. Make only the approved change — nothing more.

---

## Multi-Agent Orchestration Protocol

Noa uses a multi-agent pipeline where specialized agents handle distinct roles. The orchestrator (Claude in the main conversation) coordinates the pipeline, enforces gates, and maintains transparency.

### Agent Roster

**Skills** (invoked via `/skill-name {args}`, run in forked context):

| Skill | Role | Writes To |
|-------|------|-----------|
| `/phase-planning` | Plan phases with spec-traceability | `Plan/MASTER_PLAN.md` |
| `/write-tests` | Write failing tests from spec (red phase) | `tests/` |
| `/write-code` | Make tests pass with minimal code (green phase) | `src/` |
| `/retrospective` | Wave-level retro, estimation accuracy, skill patches | `Plan/RETROS/` |

**Agents** (invoked via Agent tool, have persistent memory):

| Agent | Role | Writes To |
|-------|------|-----------|
| `qa-review` | Adversarial QA — two modes: (1) test planning before implementation, (2) final review after implementation | `Plan/REVIEWS/` |
| `code-reviewer` | Code review for diffs/branches before merge | stdout (structured review) |
| `continuous-improvement` | Cross-wave pattern analysis, improvement proposals, fix tracking | `Plan/CI/` |

### Phase Execution Pipeline

Each phase follows this exact sequence:

```
/phase-planning → qa-review (test plan) → /write-tests (from plan) → verify red → /write-code → verify green → verify integration → qa-review (final review) → fix/iterate → mark complete
```

1. **Plan** (`/phase-planning {id}`): Create phase entry in MASTER_PLAN.md
2. **Test Plan** (launch `qa-review` agent in `test-plan` mode): QA agent reads the spec and phase plan, then produces an independent test plan defining behaviors to test, edge cases, security scenarios, and expected error paths. Written to `Plan/REVIEWS/test-plan_{phase-id}.md`. The orchestrator and `/write-tests` skill use this plan as input.
3. **Test** (`/write-tests {id}`): Write failing tests derived from the QA test plan. Must include at least one non-mocked integration test. Tests must cover the behaviors specified in the test plan.
4. **Verify Red**: Run tests — at least one new test must FAIL with an assertion error (not ImportError/NotImplementedError). Tests for already-existing helpers/utilities may pass. Log which tests failed and why.
5. **Implement** (`/write-code {id}`): Write code to make tests pass. Code MUST be wired into the running system (registered routers, instantiated services). No bare `except` blocks.
6. **Verify Green**: Run tests — all phase tests PASS. Also run `ruff check` + `mypy` (static gates must pass before merge).
7. **Verify Integration**: Import the main modules and call key functions to verify they work beyond mocked tests. Check that new routers are registered, services are instantiated, and endpoints are reachable. If imports crash or functions return wrong types, fix before proceeding.
8. **Review** (launch `qa-review` agent in `review` mode): QA agent evaluates against `Plan/QA_CHECKLIST.md` (M1-M8, S1-S5) and produces verdict. This is an adversarial review — NOT limited to checking against its own test plan. The agent runs code, scans for anti-patterns, verifies wiring, and tries to find issues the test plan missed. See `Plan/RETROS/retro_project_audit.md` for quality lessons.
9. **Iterate**: If FAIL, fix blocking issues and re-review (max 2 cycles). On 2nd FAIL, write `Plan/RCA/rca_{phase-id}.md` (cause, fix, prevention rule).
10. **Complete**: Update MASTER_PLAN.md status, write changelog entry

### Cross-Cutting Verification (After Parallel Merge)

When multiple phases execute in parallel and merge into main, the orchestrator MUST run a cross-cutting verification step:

1. **Import all modified modules together** — catches import errors and circular dependencies
2. **Call the highest-level function** that connects the parallel pieces (e.g., if 3 tool phases merged, dispatch all 3 through the registry)
3. **Run the full test suite** — not just individual phase tests
4. **Check domain isolation** — `grep -rn "from noa.private_worker" src/noa/external_worker/` (and vice versa)

If cross-cutting verification fails, the merge is rolled back and the failing phase is fixed before re-merge. This gate exists because parallel agents optimize locally — each passes its own tests but nobody verifies the pieces work together.

### Human Gates

The orchestrator MUST pause and wait for the human at these points:

1. **Wave planning** — After planning a new wave, before starting its first phase
2. **Architectural FAIL** — After QA returns FAIL requiring architectural changes
3. **CRITICAL issue** — When any CRITICAL-severity issue is logged to `Plan/ISSUES.md`
4. **Skill patches** — After retrospective proposes changes to skill files
5. **Wave completion** — Before marking a wave complete (human reviews wave summary)

### Push Notifications (ntfy)

The orchestrator MUST send a push notification before pausing or waiting for human input. Use:

```bash
python /workspace/tools/notify.py "Title" "Message"
```

**Required notification triggers:**

1. **Human gates** — Before pausing at any gate listed above. Title: `Gate: <gate name>`. Message: what happened and what approval is needed.
2. **Permission prompts** — Before attempting any tool call or action that is NOT in the allow-list. Title: `Approval Needed`. Message: which tool/action and why.
3. **Escalations** — On any escalation to human (test failures, QA failures, security concerns). Title: `Escalation`. Message: the situation and what is needed.
4. **Pipeline milestones** — When a phase or wave completes. Title: `Phase Complete` or `Wave Complete`. Message: summary and next steps.

The topic is configured via `NTFY_TOPIC` env var (default: `noaos-by2lnbzr`). Never skip a notification — the human may not be watching the terminal.

### Escalation Protocol

| Situation | Action |
|-----------|--------|
| Agent returns unexpected result | Orchestrator investigates, logs to `Plan/ISSUES.md` |
| Test agent can't derive tests from spec | STOP, ask human to clarify spec |
| Code agent can't pass tests after 2 attempts | Orchestrator tries once, then escalates to human |
| QA fails a phase once | Launch `continuous-improvement` agent to check for recurring pattern |
| QA fails a phase twice | Write `Plan/RCA/rca_{phase-id}.md` (cause, fix, prevention rule), launch CI agent, then escalate to human |
| Security concern raised by any agent | Immediate CRITICAL escalation to human |

### Status Transparency

The orchestrator maintains these documents at all times:

- **`Plan/MASTER_PLAN.md`** — Always current. Updated before and after each phase.
- **`Plan/DECISION_LOG.md`** — Every non-trivial choice by agents or orchestrator.
- **`Plan/ISSUES.md`** — All problems and their resolutions.
- **Phase changelog** — After each phase, orchestrator writes a 3-line status summary to MASTER_PLAN.md.

### Wave-Level E2E Gate (After Wave 16)

Once Wave 16 (Playwright E2E Testing) is complete, every subsequent wave must pass Playwright smoke tests before the wave is marked complete. Run:

```bash
cd web && npm run test:e2e
```

If E2E tests fail after a wave, the wave is not complete — fix the regressions first. This catches the "pieces don't connect" class of bugs that unit tests miss.

### Continuous Improvement Loop

```
Execute wave → /retrospective → continuous-improvement agent → Human approves proposals → Apply patches → Next wave
```

- **`/retrospective`** (skill): Runs after every wave. Analyzes estimation accuracy, what went well/poorly, proposes skill patches.
- **`continuous-improvement`** (agent): Runs after retros, QA failures, or RCA reports. Analyzes cross-wave patterns, tracks fix effectiveness, maintains `Plan/CI/IMPROVEMENT_BACKLOG.md`.

**Mandatory CI Agent Triggers — the orchestrator MUST launch the `continuous-improvement` agent in these situations:**

1. **After every `/retrospective`** — the retro skill includes a trigger reminder; the orchestrator executes it immediately
2. **After every QA FAIL verdict** — to check if the failure is a recurring pattern
3. **After every RCA report** (`Plan/RCA/rca_*.md`) — to correlate with past failures and propose preventive measures
4. **After `/insights` report** — to translate usage friction data into actionable CI proposals

Skipping the CI agent trigger is a pipeline violation. The CI agent's proposals still require human approval — but the analysis must happen automatically.
- Both produce PROPOSALS — human approves before application
- The CI agent has persistent memory and tracks whether past fixes actually reduced problems
- Prior retros and CI analyses are checked for trend analysis

### Planning Gates

- Human approves the **wave plan as a whole**
- Individual phases execute autonomously within an approved wave
- Orchestrator has discretion to reorder phases within a wave if dependencies require it

### Git Workflow (Worktree-Based Isolation)

The orchestrator runs inside a Docker container with access to `/workspace` (git repo) and `/artifacts` (output).

**Non-negotiable rules:**
1. **No GitHub push.** Only the human pushes to remote after review.
2. **No Docker/compose/mount modifications.**
3. **Git worktrees** for agent isolation. Never have multiple agents editing the same worktree.
4. **Merge lock**: `/workspace/.agent_locks/merge.lock` (directory-based lock).
5. **Merge into main only after tests pass.** If tests fail, do not merge; leave branch and write a failure report.

**Worktree layout:**
- Agent worktrees: `/workspace/.agent_worktrees/<agent_id>-<task_slug>`
- Branch naming: `agent/<agent_id>-<task_slug>`

**Process:**
1. Create branch from main: `agent/<agent_id>-<task_slug>`
2. Create worktree under `.agent_worktrees/`
3. Run worker agent in that worktree
4. Worker commits with message: `<scope>: <summary>`
5. Acquire merge lock → checkout main → merge `--no-ff` → run static gates (`ruff check`, `mypy`) → run tests → release lock
6. If merge/static gates/tests fail: abort, keep branch, write report to `/artifacts/merge_failure_<branch>.md`
7. Cleanup: remove merged worktrees, delete merged branches (local only)

**Required outputs:**
- `/artifacts/plan.md` — tasks, branches, worktrees
- `/artifacts/integration_report.md` — what merged, test results, what left unmerged
