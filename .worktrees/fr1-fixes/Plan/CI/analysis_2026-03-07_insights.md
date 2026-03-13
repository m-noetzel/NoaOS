# CI Analysis: Claude Code Insights Report

**Date:** 2026-03-07
**Source:** Claude Code Insights Report (169 sessions, 23 days)
**Analyst:** continuous-improvement agent

---

## 1. Executive Summary

The Insights Report surfaces three friction categories from 169 sessions: wrong initial approach, buggy code (24 instances, #1 friction source), and ignoring explicit instructions on output location. Cross-referencing these against the existing CLAUDE.md, ARCH_INVARIANTS.md, QA_CHECKLIST.md, skill files, and FINDINGS.md reveals that some friction categories are already partially addressed by post-audit process improvements, while others represent genuinely new gaps that no existing rule covers.

**Key finding:** The post-audit overhaul (2026-03-07) focused on *code quality gates* (exception handling, wiring, domain isolation, integration tests). The Insights Report surfaces *workflow and session-level friction* — a category the current rules barely touch. The two are complementary: quality gates catch bugs in the pipeline, but nothing prevents Claude from wasting an entire session on exploration instead of implementation, or writing plans to the wrong file.

---

## 2. Gap Analysis: Insights vs Existing Rules

### 2.1 Already Covered (no new proposal needed)

| Insight Suggestion | Existing Coverage |
|---|---|
| "Always run tests after making code changes before committing" | CLAUDE.md Phase Pipeline step 5 ("Verify Green: run tests — all phase tests PASS. Also run ruff check + mypy"). write-code skill Step 5 requires pytest before completion. |
| "Never suggest deleting or dropping databases" (partial) | Secret Hygiene section covers destructive operations on secrets. However, the *database* aspect is not explicitly covered — see CI-001 below. |

### 2.2 Partially Covered (existing rule exists but is insufficient)

| Insight Suggestion | Gap |
|---|---|
| "Always write plans to MASTER_PLAN.md" | The phase-planning skill writes to MASTER_PLAN.md by design (Step 3). But when Claude operates *outside* a skill invocation (ad-hoc planning, wave-level updates), there is no rule preventing it from creating separate planning files. The friction data confirms this happens. |
| "This project runs in Docker" | CLAUDE.md mentions Docker in Git Workflow section but purely for worktree/container context. No rule tells Claude to account for Docker when suggesting commands, file paths, or debugging steps. The Insights Report shows Docker-unaware suggestions (e.g., CORS fix not rebuilt in container). |

### 2.3 Not Covered (new proposals needed)

| Insight Suggestion | Status in Current Rules |
|---|---|
| "When asked to implement, start implementing — don't spend the session exploring/planning" | No rule. Nothing in CLAUDE.md or skills addresses session-level focus or the explore-vs-implement bias. |
| "Always write plans to MASTER_PLAN.md unless told otherwise" | No explicit rule outside skill context. Skills enforce it; ad-hoc work does not. |
| Docker-awareness for all suggestions | Not covered beyond the Git Workflow section. |
| Database safety (no DROP/DELETE without backup) | Not covered. |
| Custom `/wave` skill for MASTER_PLAN.md updates | No skill exists for wave-level operations. |

---

## 3. Friction Quantification

### 3.1 Wrong Initial Approach

- **Frequency:** Most common friction category across 169 sessions
- **Subtypes observed:**
  - Claude recommends non-existent commands/paths (e.g., `/think`, `scripts/` instead of `tools/`)
  - Entire session spent on exploration/planning instead of implementation
  - Over-exploration of codebase before starting work
- **Impact:** HIGH — wastes entire sessions, requires human correction
- **Root cause:** No rule establishes "implementation-first" bias or constrains exploration time

### 3.2 Buggy Code

- **Frequency:** 24 instances (#1 friction source by count)
- **Subtypes observed:**
  - Missing DB columns (maps to FINDINGS C4 — schema drift)
  - Timezone mismatches
  - Exact-match instead of ILIKE/partial
  - CORS fixes not rebuilt in Docker container
  - SQLite corruption requiring multiple rounds
- **Impact:** HIGH — each bug requires debugging cycles
- **Existing mitigation:** Post-audit quality gates (M6, M7, L9, L10) address the *systematic* causes. But the Docker-rebuild gap and the database-safety gap remain.

### 3.3 Ignoring Output Location Instructions

- **Frequency:** Recurring (not quantified in report, but flagged as distinct category)
- **Subtypes observed:**
  - Plans written to wrong file instead of MASTER_PLAN.md
  - Commits on main instead of feature branch
  - Code written before plan documented
- **Impact:** MEDIUM — causes confusion, requires manual correction
- **Existing mitigation:** Skills enforce output location. Ad-hoc work does not.

---

## 4. Proposals

Each proposal follows CI-XXX format. Only proposals that address gaps NOT already covered by existing rules are included.

### CI-001: CLAUDE.md — Implementation-First Bias Rule

**Priority:** P1 (HIGH)
**Target:** CLAUDE.md (new section)
**Evidence:** "Wrong Initial Approach" is the most common friction category. Sessions wasted on exploration/planning when user expects implementation.

**Proposed addition** (new section after "Secret Hygiene"):

```markdown
## Session Focus

When the user asks you to implement, fix, or build something, start the work immediately. Do not spend the session exploring the codebase, creating plans, or asking clarifying questions unless:
1. The request is genuinely ambiguous (multiple valid interpretations)
2. The user explicitly asks for a plan or analysis first
3. A required dependency is missing and you cannot proceed

If exploration is needed, limit it to the minimum necessary to unblock implementation. Never let exploration consume more than ~20% of the session.
```

**Expected improvement:** Eliminates the "entire session spent on exploration" friction pattern. Sets clear expectation that implementation is the default mode.

---

### CI-002: CLAUDE.md — Canonical Output Locations Rule

**Priority:** P1 (HIGH)
**Target:** CLAUDE.md (new section)
**Evidence:** "Ignoring Explicit Instructions on Output Location" friction category. Plans written to wrong files, commits on wrong branches.

**Proposed addition** (new section after "Session Focus"):

```markdown
## Canonical Output Locations

Always write plans, waves, and task updates directly to `Plan/MASTER_PLAN.md` unless the user explicitly specifies a different file. Never create separate planning files (e.g., `plan.md`, `TODO.md`, `wave_plan.md`).

When working within the multi-agent pipeline:
- Phase plans go in `Plan/MASTER_PLAN.md`
- Decisions go in `Plan/DECISION_LOG.md`
- Issues go in `Plan/ISSUES.md`
- Reviews go in `Plan/REVIEWS/`
- Retros go in `Plan/RETROS/`
- CI analyses go in `Plan/CI/`

Never commit directly to `main` during phase work — use feature branches per the Git Workflow section.
```

**Expected improvement:** Eliminates the "wrong output location" friction by making canonical locations explicit outside of skill context.

---

### CI-003: CLAUDE.md — Docker Environment Awareness Rule

**Priority:** P1 (HIGH)
**Target:** CLAUDE.md (new section)
**Evidence:** 24 buggy-code instances include Docker-specific issues: CORS fixes not rebuilt in container, SQLite/VirtioFS incompatibility, host-only solutions suggested for containerized services.

**Proposed addition** (new section after "Canonical Output Locations"):

```markdown
## Docker Environment Awareness

This project runs in Docker containers (see `docker-compose.yml` and `docker-compose.dev.yml`). When suggesting commands, debugging steps, or code changes:

1. **All runtime behavior happens inside containers.** Code changes require a container rebuild (`docker compose build`) or restart (`docker compose restart <service>`) to take effect. Never assume a code change is live without a rebuild step.
2. **File paths differ between host and container.** The repo is mounted at `/workspace` inside the dev container. Use container paths in runtime commands, host paths in git/editor commands.
3. **SQLite WAL mode is incompatible with VirtioFS** (macOS Docker). Never suggest WAL journal mode for SQLite in Docker. If SQLite corruption occurs, attempt recovery/backup-based restoration before suggesting database deletion.
4. **Network context matters.** `localhost` inside a container refers to the container itself, not the host. Use Docker service names for inter-container communication.
5. **Never suggest deleting or dropping databases without first creating a backup.** Always attempt recovery-based restoration before destructive operations.
```

**Expected improvement:** Eliminates Docker-unaware suggestions and the database-deletion anti-pattern. Prevents the "CORS fix didn't take effect" class of bugs.

---

### CI-004: CLAUDE.md — Project Path Reference

**Priority:** P2 (MEDIUM)
**Target:** CLAUDE.md (addition to existing section)
**Evidence:** Wrong Initial Approach friction includes Claude suggesting non-existent paths like `scripts/` instead of `tools/`. This indicates lack of project structure awareness.

**Proposed addition** (append to "Project Overview" section):

```markdown
### Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/noa/` | Python backend (API, orchestrator, workers, tools, DB) |
| `web/` | React/TypeScript frontend |
| `tests/` | Test suite (unit, integration) |
| `tools/` | Utility scripts (notify.py, keychain_bootstrap.sh) |
| `Plan/` | Project planning artifacts (MASTER_PLAN, reviews, retros, CI) |
| `docker/` | Per-service Dockerfiles |
| `alembic/` | Database migrations |
| `.claude/skills/` | Agent skill definitions |
| `.claude/agents/` | Agent definitions |
```

**Expected improvement:** Reduces wrong-path suggestions by giving Claude an explicit directory map. Particularly prevents the `scripts/` vs `tools/` confusion.

---

### CI-005: Skill — `/wave` Skill for MASTER_PLAN.md Wave Operations

**Priority:** P2 (MEDIUM)
**Target:** `.claude/skills/wave/SKILL.md` (new skill)
**Evidence:** Feature suggestion from Insights Report. Currently wave-level updates to MASTER_PLAN.md are done ad-hoc, leading to inconsistencies and the "wrong output location" friction.

**Proposed skill scope:**
- Read current MASTER_PLAN.md state
- Add new wave header + phase entries
- Update wave status (mark complete, add summary)
- Enforce the canonical format from phase-planning skill
- Never create separate planning files

**Note:** This proposal requires human approval to create a new skill file. The skill definition should follow the existing pattern in `.claude/skills/phase-planning/SKILL.md`.

**Expected improvement:** Standardizes wave-level operations the same way `/phase-planning` standardizes phase-level operations. Removes the ad-hoc path that causes output location friction.

---

### CI-006: write-code Skill — Docker Rebuild Reminder

**Priority:** P2 (MEDIUM)
**Target:** `.claude/skills/write-code/SKILL.md` (addition to Step 5: Verify)
**Evidence:** Buggy code friction includes changes not taking effect because containers were not rebuilt.

**Proposed addition** to write-code skill, Step 5 (Verify):

```markdown
### Step 5b: Docker Rebuild Note

If the code you modified runs inside a Docker container (API, workers), remind the orchestrator:
> "Container rebuild or restart required for changes to take effect: `docker compose restart <service>`"

Do not assume code changes are live without a container lifecycle step.
```

**Expected improvement:** Prevents the "fix applied but not rebuilt" class of bugs.

---

### CI-007: Hook — Auto-Test on Commit (PostToolUse)

**Priority:** P3 (LOW)
**Target:** Claude Code hooks configuration (`~/.claude/settings.json`)
**Evidence:** Feature suggestion from Insights Report. Currently tests are run manually as part of the pipeline. A PostToolUse hook on `git commit` could auto-trigger `pytest`.

**Proposed hook:**
```json
{
  "event": "PostToolUse",
  "matcher": "Bash(git commit*)",
  "command": "pytest tests/ -x -q --tb=short 2>&1 | head -30"
}
```

**Note:** This is a convenience enhancement, not a process gap. The pipeline already requires test verification. The hook adds a safety net for ad-hoc commits outside the pipeline. Risk: adds latency to every commit. Recommend human evaluates the tradeoff.

**Expected improvement:** Catches the "committed without running tests" pattern automatically.

---

## 5. Non-Proposals (Rejected / Already Covered)

| Suggestion | Reason Not Proposed |
|---|---|
| "Always run tests after code changes before committing" | Already in CLAUDE.md pipeline (Step 5) and write-code skill (Step 5). Adding it again would be redundant. |
| "Headless mode for batch task execution" | Infrastructure feature, not a process improvement. Out of scope for CI proposals. |
| "Sessions fokussiert halten (1 Ziel pro Session)" | User-side behavior, not an instruction for Claude. CI-001 addresses the Claude-side of this. |
| "Docker-Kontext am Anfang der Session mitgeben" | User-side behavior. CI-003 embeds Docker context permanently in CLAUDE.md so it does not need to be repeated per session. |
| "'Implement this' statt offene Anfragen" | User-side behavior. CI-001 addresses the Claude-side bias toward implementation. |

---

## 6. Priority Summary

| ID | Title | Priority | Target | Status |
|----|-------|----------|--------|--------|
| CI-001 | Implementation-First Bias Rule | P1 | CLAUDE.md | PROPOSED |
| CI-002 | Canonical Output Locations Rule | P1 | CLAUDE.md | PROPOSED |
| CI-003 | Docker Environment Awareness Rule | P1 | CLAUDE.md | PROPOSED |
| CI-004 | Project Path Reference | P2 | CLAUDE.md | PROPOSED |
| CI-005 | `/wave` Skill for MASTER_PLAN.md | P2 | .claude/skills/ | PROPOSED |
| CI-006 | Docker Rebuild Reminder in write-code | P2 | .claude/skills/write-code/ | PROPOSED |
| CI-007 | Auto-Test PostToolUse Hook | P3 | ~/.claude/settings.json | PROPOSED |

**Recommended application order:** CI-001, CI-002, CI-003 (all P1, can be applied in one CLAUDE.md edit), then CI-004, CI-005, CI-006 (P2), then CI-007 (P3, requires human tradeoff evaluation).

---

## 7. Relationship to Existing Findings

The Insights Report's "buggy code" friction overlaps with FINDINGS.md but does not duplicate it:

- **Schema drift (C4):** Insights confirms this is a recurring friction source (missing DB columns). Already tracked in FINDINGS.md.
- **Exception handling (H5):** Not surfaced in Insights Report — the post-audit ruff rules may have already reduced this.
- **Domain isolation (C2):** Not surfaced in Insights Report — suggests this is not a session-level friction source.
- **Docker-specific bugs:** NEW pattern not in FINDINGS.md. Addressed by CI-003 and CI-006.
- **Database safety:** NEW pattern not in FINDINGS.md. Addressed by CI-003.

No proposals in this analysis duplicate items in FINDINGS.md or the (empty) IMPROVEMENT_BACKLOG.md.
