# CLAUDE.md — Project Instructions

## Session Start

1. Read `Plan/PLAN.md` for current project state (~125 lines, status table).
2. For phase details, search `Plan/PHASE_DETAILS.md` for the specific phase ID — never read the full file.

After milestones (phase/wave completion, QA verdicts), update:
- `Plan/PLAN.md` — status table row
- MEMORY.md — project state summary

## Project Overview

Noa is a governed personal AI agent with dual-domain architecture (private + external). Container-based domain isolation (Phase 1), scales to physical machine isolation (Phase 2). See SPEC.md for full spec.

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
| `/write-tests` | Failing tests from spec (red phase) | `tests/` |
| `/write-code` | Make tests pass (green phase) | `src/` |
| `/retrospective` | Wave-level retro, estimation accuracy | `Plan/RETROS/` |
| `qa-review` | Test planning (pre-impl) + adversarial review (post-impl) + health brief | `Plan/REVIEWS/` |
| `code-reviewer` | Fast code review (sonnet), pre-QA | stdout |
| `continuous-improvement` | Cross-wave patterns, fix tracking | `Plan/CI/` |

### Phase Pipeline

```
/phase-planning → qa-review (test-plan) → /write-tests → verify red → /write-code → verify green → verify integration → code-reviewer → fix → qa-review (review) → fix/iterate → complete
```

**Gates:**
- **Verify Red**: >=1 new test FAIL with assertion error (not ImportError/NotImplementedError)
- **Verify Green**: All tests pass + `ruff check` + `mypy`
- **Verify Integration**: Import main modules, verify wiring (routers registered, services instantiated)
- **Code Review**: Fix Critical issues before QA
- **QA Review**: Adversarial review against `Plan/QA_CHECKLIST.md` (M1-M8, S1-S5). Max 2 cycles; on 2nd FAIL write `Plan/RCA/rca_{phase-id}.md`. After verdict, generates `Plan/REVIEWS/health_{date}.md` (project score 1-10, greatest risk, decisions needed, security posture)

**Implementation rules:**
- Code must be wired into the running system
- No bare `except` blocks
- >=1 non-mocked integration test per phase

### Cross-Cutting Verification (After Parallel Merge)

Import all modified modules together, run full test suite, check domain isolation (`grep -rn "from noa.private_worker" src/noa/external_worker/` and vice versa). Rollback on failure.

### Human Gates

Pause and wait at:
1. Wave planning approval
2. Architectural FAIL from QA
3. CRITICAL issue in `Plan/FINDINGS.md`
4. Skill patches from retrospective
5. Wave completion review

**At every human gate, immediately notify before pausing:**
```bash
python3 tools/notify.py "<Gate Name>" "<What decision is needed>"
```
Example: `python3 tools/notify.py "Wave Planning" "Wave 15 plan ready for approval"`

### Escalation

| Situation | Action |
|-----------|--------|
| Test agent can't derive tests | STOP, ask human to clarify spec |
| Code agent fails 2x | Orchestrator tries once, then escalates |
| QA fails once | Launch `continuous-improvement` agent |
| QA fails twice | Write RCA, launch CI agent, escalate |
| Security concern | Immediate CRITICAL escalation |

### Continuous Improvement

**Mandatory CI triggers:** after every retrospective, QA FAIL, RCA report, or `/insights` report. Skipping = pipeline violation. Human approves all proposals before application.

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
