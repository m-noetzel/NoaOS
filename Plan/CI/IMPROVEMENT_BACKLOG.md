# Improvement Backlog

Maintained by the `continuous-improvement` agent. Proposals require human approval before application.

| ID | Title | Priority | Status | Target | Proposed | Applied | Verified |
|----|-------|----------|--------|--------|----------|---------|----------|
| CI-001 | Implementation-First Bias Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-002 | Canonical Output Locations Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-003 | Docker Environment Awareness Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-004 | Project Path Reference | P2 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-005 | `/wave` Skill for MASTER_PLAN.md | P2 | PROPOSED | .claude/skills/ | 2026-03-07 | — | — |
| CI-006 | Docker Rebuild Reminder in write-code | P2 | PROPOSED | .claude/skills/write-code/ | 2026-03-07 | — | — |
| CI-007 | Auto-Test PostToolUse Hook | P3 | PROPOSED | ~/.claude/settings.json | 2026-03-07 | — | — |

---

## Proposal Details

Full analysis and proposed text for each item: [`Plan/CI/analysis_2026-03-07_insights.md`](analysis_2026-03-07_insights.md)

### Summary

- **CI-001 through CI-003** (P1): Three new CLAUDE.md sections addressing the top friction categories from the Insights Report — implementation-first bias, canonical output locations, and Docker environment awareness. These can be applied in a single CLAUDE.md edit.
- **CI-004** (P2): Add a key directories table to CLAUDE.md Project Overview to prevent wrong-path suggestions.
- **CI-005** (P2): New `/wave` skill to standardize wave-level MASTER_PLAN.md operations (mirrors `/phase-planning` for phases).
- **CI-006** (P2): Add Docker rebuild reminder to write-code skill's verification step.
- **CI-007** (P3): PostToolUse hook to auto-run pytest after git commit. Convenience enhancement with latency tradeoff — requires human evaluation.
