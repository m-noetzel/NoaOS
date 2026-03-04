# CLAUDE.md — Project Instructions for AI Assistants

## Project Overview

Noa is a governed personal AI agent with dual-domain architecture (private + external) running on local hardware. It starts on a single machine with container-based domain isolation (Phase 1) and is designed to scale to physical machine isolation (Phase 2). See SPEC.md for the full technical specification.

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

| Skill | Role | Writes To | Context |
|-------|------|-----------|---------|
| `/phase-planning` | Plan phases with spec-traceability | `Plan/MASTER_PLAN.md` | fork |
| `/write-tests` | Write failing tests from spec (red phase) | `tests/` | fork |
| `/write-code` | Make tests pass with minimal code (green phase) | `src/` | fork |
| `/qa-review` | Review spec compliance, coverage, security | `Plan/REVIEWS/` | fork |
| `/retrospective` | Analyze patterns, propose skill improvements | `Plan/RETROS/` | fork |

### Phase Execution Pipeline

Each phase follows this exact sequence:

```
/phase-planning → /write-tests → verify red → /write-code → verify green → /qa-review → fix/iterate → mark complete
```

1. **Plan** (`/phase-planning {id}`): Create phase entry in MASTER_PLAN.md
2. **Test** (`/write-tests {id}`): Write failing tests derived from spec
3. **Verify Red**: Run tests — at least one new test must FAIL with an assertion error (not ImportError/NotImplementedError). Tests for already-existing helpers/utilities may pass. Log which tests failed and why.
4. **Implement** (`/write-code {id}`): Write code to make tests pass
5. **Verify Green**: Run tests — all phase tests PASS. Also run `ruff check` + `mypy` (static gates must pass before merge).
6. **Review** (`/qa-review {id}`): QA agent evaluates against `Plan/QA_CHECKLIST.md` and produces verdict
7. **Iterate**: If FAIL, fix blocking issues and re-review (max 2 cycles). On 2nd FAIL, write `Plan/RCA/rca_{phase-id}.md` (cause, fix, prevention rule).
8. **Complete**: Update MASTER_PLAN.md status, write changelog entry

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
| QA fails a phase twice | Write `Plan/RCA/rca_{phase-id}.md` (cause, fix, prevention rule), then escalate to human |
| Security concern raised by any agent | Immediate CRITICAL escalation to human |

### Status Transparency

The orchestrator maintains these documents at all times:

- **`Plan/MASTER_PLAN.md`** — Always current. Updated before and after each phase.
- **`Plan/DECISION_LOG.md`** — Every non-trivial choice by agents or orchestrator.
- **`Plan/ISSUES.md`** — All problems and their resolutions.
- **Phase changelog** — After each phase, orchestrator writes a 3-line status summary to MASTER_PLAN.md.

### Continuous Improvement Loop

```
Execute wave → /retrospective → Propose skill patches → Human approves → Apply patches → Next wave
```

- Retrospectives run after every **wave**, not every phase
- Skill patches are PROPOSALS — human approves before application
- Prior retros are checked for trend analysis (are old issues improving?)

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
