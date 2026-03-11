---
name: phase-planning
description: Plan and track implementation phases. Reads SPEC.md and PLAN.md, writes structured phase entries with spec-traceability, file tables, and test gates.
argument-hint: [phase-id-and-description]
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit
---

# /phase-planning — Phase Planning & Tracking

Plan and document an implementation phase with full spec-traceability.

**Phase input:** `$ARGUMENTS`

---

## Process

### Step 1: Understand Current State

Read `Plan/PLAN.md` and extract:
- Which phases are completed (look for checkmark status markers)
- Which phases are in progress
- The dependency graph (what blocks what)
- The last phase number used (for numbering the new phase)
- The wave/section where the new phase belongs

### Step 2: Find Spec Requirements

Read `SPEC.md` and find sections relevant to `$ARGUMENTS`. Extract:
- Section numbers (e.g., §3.2, §7.4)
- Specific requirements that the phase must satisfy
- Data model definitions that the phase touches
- Acceptance criteria from §9 (Definition of Done) if applicable

**CRITICAL:** If no SPEC.md section supports this phase, STOP and tell the user:
> "No SPEC.md section covers this feature. The spec may need updating before planning this phase. Spec is human-only — please add the relevant section and re-run /phase-planning."

### Step 3: Write Phase Entry

Add a detailed phase section to `Plan/PHASE_DETAILS.md` using this EXACT format:

```markdown
### Phase {ID}: {Title} (~{est} min)

**Goal:** {1-2 sentence problem statement — what is wrong or missing, and what this phase fixes}

**Spec refs:** SPEC.md §{X.Y}, §{Z.W}

**Depends on:** {comma-separated phase IDs, or "None"}
**Blocks:** {comma-separated phase IDs, or "None"}

**Deliverables:**
1. {Major deliverable — what gets created or changed}
2. {Major deliverable}
3. {Major deliverable}

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/path/file.py` | **CREATE** | {What gets created and why} |
| `src/path/file.py` | **EDIT** | {What gets modified and why} |
| `tests/unit/test_file.py` | **CREATE** | {Test file covering this phase} |

**Tests (~{N}):**
- {Test category 1}: {what gets tested — e.g., "CRUD operations on new model"}
- {Test category 2}: {what gets tested — e.g., "Edge cases for empty input"}
- {Test category 3}: {what gets tested — e.g., "Integration with existing pipeline"}

**Test gate:**
```bash
pytest tests/unit/test_{name}.py -v
```
```

### Step 4: Update Status Table

Add a row to the Phase Status Summary table in `Plan/PLAN.md`:

```
| **{ID}** | **{Title}** | Pending | ~{N} | — | ~{est} min | — |
```

If this is a new wave, also add a wave header row:
```
| — | — **WAVE {N}: {WAVE TITLE}** — | — | — | — | — | — |
```

### Step 5: Mark In Progress (if starting now)

If the user indicates they want to start this phase immediately:
1. Change status from "Pending" to "In Progress" in the table
2. Add the current date as a note
3. Remind the user: "Launch the `implement` agent to build this phase."

---

## Phase ID Conventions

Phase IDs follow these patterns (match existing conventions):
- Core phases: `1`, `2`, `3`, etc.
- Remediation: `R1`, `R2`, `R3`
- Feature waves: `HP1`, `NP1`, `GR1`, `CE1`, `DQM1`, etc.
- Infrastructure: `COST1`, `EMB1`, `MCP1`, `SEC-C1`
- Skills/tooling: `SKL1`, `SKL2`, `SKL3`

Choose a prefix that reflects the feature area. Keep IDs short (2-4 chars + number).

---

## Duration Estimation Guidelines

| Scope | Typical Duration |
|-------|-----------------|
| New ORM model + CRUD service | ~30-45 min |
| New UI page with components | ~45-60 min |
| Pipeline step (ingestion/retrieval) | ~30-45 min |
| Integration + wiring existing components | ~20-30 min |
| Config/settings change | ~15-20 min |

Prefix estimates with `~` to indicate approximation. These are agent working time, not human time.

---

## Test Count Estimation Guidelines

| Scope | Typical Tests |
|-------|--------------|
| New service with 5 methods | ~15-20 |
| New ORM model | ~5-10 |
| New UI page | ~10-15 |
| Pipeline modification | ~8-12 |
| Config change | ~3-5 |

These are approximate. Use `~{N}` format for pending phases. Replace with exact count when phase is complete.

---

## Rules

1. **Every phase MUST reference at least one SPEC.md section** — no orphan phases
2. **Duration estimates in minutes**, prefixed with `~`
3. **Test counts are estimates** for pending phases, exact for completed
4. **Use consistent status markers**: Pending, In Progress, Complete, Blocked
5. **File table must list ALL files** that will be created or modified
6. **Test gate must be a runnable command** — `pytest tests/unit/test_{name}.py -v`
7. **Goal must describe the problem**, not just the solution — "Currently X is missing/broken, this phase adds/fixes Y"
8. **Deliverables are outcomes**, not tasks — "Cost tracking table with ORM model" not "Write ORM model"

---

## After Planning

Tell the user:
1. The phase has been added to PLAN.md and PHASE_DETAILS.md
2. Show the test gate command they'll need to run when done
3. Remind them to launch the `implement` agent to build the phase
