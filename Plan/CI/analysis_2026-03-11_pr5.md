# Continuous Improvement Analysis — 2026-03-11 (PR5)

## Summary

PR5 (online indicator, React Router redirect, iOS lifecycle) passed QA on the first cycle with notes. Three issues were flagged: S5 (persistent OPEN, now five consecutive Wave 19 phases), a silent artifact download failure (low severity), and a pre-existing ErrorBoundary stack leak. No new systemic patterns emerge. No new P1 proposals. All four overdue P1 human gates from prior cycles remain open and are re-stated below.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| S5-PR5 | testing | medium | 5/5 Wave 19 | No non-mocked integration test. PR6 committed to close this. |
| NOTE-1 | error-handling | low | 1 (PR5) | Artifact download failure silently logged — user gets no UI feedback |
| NOTE-2 | security | low | pre-existing | ErrorBoundary.tsx:43 renders error.stack to UI (internal detail exposure) |

---

## Patterns

### S5 — Integration Smoke Test Persistently OPEN (now 5/5 Wave 19)

No change from PR4 analysis. Count increments from 4 to 5. CI-016 (P1 human gate, S5 escalation) was raised in PR3 and remains unactioned. PR6 is still the committed resolution point.

No new proposal warranted — CI-016 already covers this. The consecutive count will be verified closed when PR6 QA runs.

### Silent Failure on Artifact Download

A download failure is logged server-side but the client receives no actionable feedback. This is a UX gap, not a data-integrity or security concern. It is a standalone bug, not a systemic pattern — no similar silent-failure pattern appears in prior phases.

This does not meet the bar for a new CI proposal (single occurrence, low severity, already captured in QA notes). The implement agent should surface it to the user via an error toast when PR6 handles E2E flows, or it can be addressed in Wave 22 polish.

### ErrorBoundary Stack Exposure (pre-existing)

First flagged in QA notes. `error.stack` rendered to UI could expose internal file paths to users in production. This is a pre-existing issue (not introduced by PR5). It is not critical (no secrets exposed, Noa is single-user), but it warrants a FINDINGS entry.

**New proposal: CI-021 (P3).** Add a FINDINGS.md entry (FE-L1) tracking the ErrorBoundary stack exposure so it is not lost between waves.

---

## Effectiveness of Past Fixes

| Fix | Applied | Status |
|-----|---------|--------|
| CI-009 (L12 Write-Path User Scoping) | 2026-03-11 | No new violations in PR2–PR5. Effective. |
| CI-016 P1 gate (S5 escalation) | NOT YET | Still overdue. PR6 is committed resolution. |
| CI-013 P1 gate (M5b Findings Currency) | NOT YET | Overdue since PR2. |
| CI-017 P1 gate (M8b Cross-Language Optionality) | NOT YET | Overdue since PR3. |
| CI-020 P1 gate (FINDINGS cleanup before PR5) | NOT YET CONFIRMED | Human gate from PR4 — status unknown. |

---

## Proposals

### CI-021 — Track ErrorBoundary Stack Exposure in FINDINGS.md (P3)

**Evidence**: QA PR5 notes item 3 — `ErrorBoundary.tsx:43` renders `error.stack` to UI. Pre-existing, not introduced by PR5. Single-user context limits severity, but the issue should be tracked rather than dropped from QA notes.

**Proposed change**: Add a new FE-L1 entry to FINDINGS.md:

```
FE-L1 | Low | Open | ErrorBoundary.tsx:43 renders error.stack to UI. In production this
exposes internal file paths to the user. Noa is single-user so impact is low, but
stack traces should be stripped before display. Fix: replace error.stack render with
a generic message; log stack to console only. | Discovered PR5 QA.
```

**Target**: `Plan/FINDINGS.md`
**Priority**: P3 — no human gate required. Can be applied by implement agent during PR6 or Wave 22 polish.
**Impact**: Prevents a low-severity finding from being forgotten between waves.

---

## Outstanding P1 Human Gates (overdue — restated)

These were raised in prior cycles and have not been actioned. They must be resolved before Wave 20 begins.

| ID | Title | Overdue Since |
|----|-------|---------------|
| CI-013 | M5b Findings Currency Gate → QA_CHECKLIST.md | PR2 |
| CI-016 | S5 Integration Test Baseline → CLAUDE.md | PR3 |
| CI-017 | M8b Cross-Language Field Optionality Gate → QA_CHECKLIST.md | PR3 |
| CI-020 | FINDINGS.md immediate cleanup (BE-H1, BE-M3, BE-M4 → Resolved) | PR4 |

---

## Metrics

- Problems scanned: 3
- New patterns identified: 0 (all tracked)
- Recurring patterns (previously seen): 2 (S5, pre-existing ErrorBoundary)
- New single-occurrence issues: 1 (silent artifact download failure — below proposal bar)
- Past fixes verified effective: 1/1 checked (CI-009)
- Proposals generated: 1 (P3: CI-021)
- P1 human gates triggered: 0
