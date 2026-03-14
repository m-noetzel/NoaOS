# Continuous Improvement Analysis -- 2026-03-14 (Wave 22)

## Summary

Wave 22 (FR1--FR6) delivered strong finding closure (27 findings resolved, all High/Medium closed) and genuine domain isolation (FR1). However, the wave introduced a recurring anti-pattern: dead-end stores (W22-H1, W22-H2) -- the 2nd occurrence across the last 3 waves (Wave 20 had `workers_degraded` write-only). CI-031 (M7 `app.state` write-only detection) was effective for `app.state` assignments but the Wave 22 dead-end stores are DB-persisted settings fields, not `app.state`, so CI-031's scope did not cover them. This is a gate gap requiring a broader dead-end store check. All 6 QA verdicts were PASS_WITH_NOTES; the bar appears correctly calibrated (notes are genuine should-have gaps, not deferred must-haves). FR1 required a second QA cycle due to a cascade delete test gap (pre-QA verification shortfall). FR6 had scope creep (+50% overrun).

---

## Problems Found

| # | Category | Severity | Occurrences | Description |
|---|----------|----------|-------------|-------------|
| P1 | architecture | high | 2 waves (W20 DE3, W22 FR6) | Dead-end stores: data persisted to DB or app.state but never consumed by the intended consumer. W20: `workers_degraded` flag. W22: 4 governance settings fields (`max_tool_calls`, `max_retries`, `timeout_seconds`, `approvals_enabled`). |
| P2 | testing | medium | 1 phase (FR1) | Pre-QA verification missed cascade delete test gap, triggering a 2nd QA cycle. CI-033 (pre-QA deliverable check) was not applied rigorously. |
| P3 | process | medium | 1 phase (FR6) | Scope creep: Notion auto-grant + iOS health check added mid-implementation, causing +50% time overrun. No scope-freeze gate for polish phases. |
| P4 | testing | medium | 2 phases (FR5, FR6) | Type contract mismatches caught by QA, not during implementation. FR5: `CostRecord.run_id` typed `string` in TS but backend returns `null`. FR6: no Pydantic bounds on integer settings fields. |
| P5 | process | low | 4 phases (FR1-FR4) | Missing signal log rows for FR1-FR4 -- qa-review did not append rows for these phases, reducing CI visibility. |
| P6 | infrastructure | low | 2 waves (W21, W22) | System-auditor container-blind: containers not running during audit window, capping 5 rubric dimensions at 0.5. Score drops are audit infrastructure gaps, not code quality regressions. |
| P7 | architecture | medium | 1 phase (FR6) | Scope overrides (`_scope_overrides`) are in-memory only -- lost on restart. Tracked as FR6-L1. |
| P8 | architecture | medium | 1 phase (FR5+FR1 gap) | Domain isolation incomplete: runs and cost endpoints do not filter by domain (W22-M1). FR1's domain isolation applied to threads but not to runs/cost cross-phase. |

---

## Patterns Identified

### Pattern 1: Dead-End Stores (P1 -- meets evidence threshold)

**Occurrences:** 2 waves within last 3 (Wave 20 DE3, Wave 22 FR6)
**Category:** architecture
**Current mitigation:** CI-031 (M7 `app.state` write-only detection) -- APPLIED in Wave 20.
**Gate effectiveness:** CI-031 is narrowly scoped to `app.state.{var}` assignments. The Wave 22 dead-end stores are ORM model fields persisted via `SettingsRepository`, not `app.state` writes. CI-031 did not fail to catch this -- it was never designed to cover DB-persisted settings fields. This is a **missing gate**, not a gate failure.
**Root cause:** The implement agent adds UI controls + DB persistence for settings without confirming the consumer (orchestrator/policy engine) is within the same phase's scope. The "no dead-end stores" CLAUDE.md rule exists but is advisory -- no pre-QA or QA checklist item covers DB-level dead-end stores.

### Pattern 2: Type Contract Mismatches Caught at QA (P4 -- watch list)

**Occurrences:** 2 phases in Wave 22 (FR5, FR6). Similar pattern seen in Wave 19 (PR3 field optionality).
**Current mitigation:** M8b (cross-language field optionality) covers iOS/Swift nil-omission. No gate covers TypeScript type lie (`string` vs `string | null`) or Pydantic validation bounds.
**Note:** The retro recommends adding `tsc --noEmit` to the verify gate. This is a reasonable proposal but only 2 occurrences in the current wave -- placing on watch list for now and including as part of a broader proposal if it recurs.

### Pattern 3: Scope Creep in Polish Phases (P3 -- watch list)

**Occurrences:** 1 phase in Wave 22 (FR6), with historical echoes in QC7/QC8 (Wave 14B). Only 1 occurrence within the last 3 waves.
**Note:** The retro recommends a scope-freeze gate for polish phases. Single occurrence in the evidence window; placing on watch list.

---

## Emerging Patterns (watch list)

| Description | Occurrences | Category | Notes |
|-------------|-------------|----------|-------|
| Type contract mismatches (TS type lie, missing Pydantic bounds) caught at QA not implementation | 2 phases (FR5, FR6) in W22 | testing | Retro recommends `tsc --noEmit` in verify gate. Monitor in Wave 23. |
| Scope creep in polish/UX phases | 1 phase (FR6) in W22 | process | Retro recommends scope-freeze gate. Single occurrence -- monitor. |
| Missing QA signal log rows | 4 phases (FR1-FR4) in W22 | process | QA reviews for FR1-FR4 either not persisted or signal rows not appended. Reduces CI visibility. |
| System-auditor container-blind at wave boundary | 2 consecutive waves (W21, W22) | infrastructure | Score penalized but code quality unaffected. Retro action item #7 addresses this. |
| Cross-phase domain isolation gaps | 1 instance (FR1 x FR5) in W22 | architecture | Domain filter applied to threads but not runs/cost. Tracked as W22-M1. |

---

## Effectiveness of Past Fixes

| Fix | Wave Applied | Status | Evidence |
|-----|-------------|--------|----------|
| CI-031 (M7 app.state write-only) | Wave 20 | **PARTIALLY EFFECTIVE** | Effective for `app.state` writes (zero violations in W21 and W22). But scope is too narrow -- does not cover DB-persisted dead-end stores (W22-H1, W22-H2). Needs broadening (see CI-042). |
| CI-033 (Pre-QA Deliverable Check) | Wave 20 | **PARTIALLY EFFECTIVE** | No completeness FAIL verdicts in W21 or W22 (good). But FR1 still needed a 2nd QA cycle for a test gap -- CI-033 checks file existence, not test coverage gaps. The gate works for its designed scope. |
| CI-013 (M5b Findings Currency) | Wave 19 | **EFFECTIVE** | All 27 findings resolved in W22 were correctly synced to FINDINGS.md. Zero drift. Pattern fully reversed from the W19 drift crisis. |
| CI-015 (Findings Sync Pipeline Step) | Wave 19 | **EFFECTIVE** | No stale findings at wave close. |
| CI-030 (Ruff on tests/) | Wave 20 | **EFFECTIVE** | Zero ruff violations in any W22 test file. |
| CI-009 (L12 Write-Path User Scoping) | Wave 19 | **EFFECTIVE** | No write-path scoping violations in W22. All new endpoints filter by `user_id`. |
| CI-017 (M8b Cross-Language Field Optionality) | Wave 19 | **EFFECTIVE** | FR6 correctly marks all new settings fields as `Optional` with `= None`. No iOS 422 failures. |
| CI-023 (Pre-Phase Test Plan) | Wave 19 | **NOT EFFECTIVE** | Still no evidence of test plans in implement agent output. 0/6 phases in W22 had a test plan. CI-038 (M1b enforcement gate) remains DEFERRED. |

---

## Proposals

### CI-042: Broaden Dead-End Store Detection to DB-Persisted Fields (P1)

**Evidence:**
- Wave 20 DE3: `app.state.workers_degraded` set but never read (review_DE3.md line 123)
- Wave 22 FR6: `max_tool_calls`, `max_retries`, `timeout_seconds`, `approvals_enabled` persisted to DB via ORM but never consumed by orchestrator or policy engine (audit_wave22_2026-03-14.md lines 130-153)
- 2 occurrences across 2 of the last 3 waves, different phases (DE3, FR6)

**Not a duplicate of:** CI-031 (app.state write-only detection). CI-031 is narrowly scoped to `app.state.{var}` assignments and was effective for that scope. CI-042 broadens coverage to all storage mechanisms (ORM fields, in-memory dicts, config writes) -- the class of problem is the same ("no dead-end stores") but the detection surface is different.

**Estimated impact:** high -- avoids misleading UI controls that present as functional but have no effect. W22-H1/H2 are High severity because users believe they have governance limits configured when the agent runs unconstrained.

**Implementation burden:** low -- adds one sentence to an existing M7 checklist row. No new tooling required.

**Confidence:** high -- clear causal chain (field added without consumer), 2 occurrences across 2 waves, existing CLAUDE.md rule confirms this is a known anti-pattern.

**Proposed change:** Add to QA_CHECKLIST.md M7 (Wiring Completeness), after the CI-031 bullet:

```markdown
- [ ] **CI-042**: When this phase adds a new DB column, ORM field, settings field, or in-memory store entry: verify at least one consumer reads and acts on the value within the running system. A stored field with no reader is a dead-end store. If the consumer is in a future phase, the field must NOT be exposed in the UI as a functional control -- add a `# TODO: wire in phase <ID>` comment and a FINDINGS entry.
```

**Target:** Plan/QA_CHECKLIST.md (M7 section)
**Priority:** P1 (human gate required -- this is a recurring High-severity anti-pattern with UI honesty implications)

### CI-043: Add `tsc --noEmit` to Verify Gate (P2)

**Evidence:**
- Wave 22 FR5: `CostRecord.run_id` typed `string` in `types.ts` but backend returns `string | null` (review_fr5.md line 140)
- Wave 22 FR6: `max_tool_calls`/`max_retries`/`timeout_seconds` accept negative values -- no Pydantic `Field(ge=1)` (review_fr6.md line 27)
- The retro (retro_wave22.md line 49) explicitly recommends `tsc --noEmit` as a verify gate addition

**Not a duplicate of:** CI-017 (M8b cross-language field optionality) covers Swift nil-omission at the Pydantic level. CI-043 covers TypeScript type correctness at the frontend compilation level -- different tool, different failure class.

**Estimated impact:** medium -- catches frontend type lies (`string` vs `string | null`) before QA. The Pydantic bounds issue (negative values) is a separate concern not caught by `tsc`.

**Implementation burden:** low -- one command addition to the verify gate checklist in CLAUDE.md.

**Confidence:** medium -- 2 occurrences support the TS type check proposal. The Pydantic bounds issue is separate (no automated gate proposal for that -- it's a design review concern).

**Proposed change:** Add to CLAUDE.md "Implementation rules" section:

```markdown
- **Frontend type check**: Run `cd web && npx tsc --noEmit` before submitting for QA to catch type mismatches between frontend types and backend response shapes.
```

**Target:** CLAUDE.md (Implementation rules section)
**Priority:** P2 (advisory -- prevents rework but not a recurring blocking pattern yet)

### CI-044: Signal Log Completeness Enforcement (P3)

**Evidence:**
- Wave 22 FR1-FR4: 4 phases completed without signal log rows in `Plan/CI/signals.md`. Only FR5 and FR6 have rows.
- This reduces CI agent visibility and makes pattern analysis incomplete.

**Not a duplicate of:** No existing proposal covers signal log completeness. CI-015 (findings sync) is a similar "mandatory pipeline step" pattern but for a different artifact.

**Estimated impact:** low -- CI agent can still read reviews directly, but signal log is designed as the fast-scan prioritization tool.

**Implementation burden:** low -- add one sentence to the QA review agent's output contract.

**Confidence:** medium -- clear gap (4 missing rows), but impact is low since reviews are the primary evidence source.

**Proposed change:** Add to CLAUDE.md QA Review gate description:

```markdown
- **Signal log row (mandatory)**: After every QA verdict, the qa-review agent must append one row to `Plan/CI/signals.md` with phase, date, verdict, and key issues. Missing rows are a pipeline violation.
```

**Target:** CLAUDE.md (Gates section, QA Review)
**Priority:** P3 (nice to have -- does not block quality but improves CI visibility)

---

## QA Leniency Assessment

All 6 Wave 22 verdicts were PASS_WITH_NOTES. The question: is QA too lenient?

**Assessment: The bar is correctly calibrated.**

Evidence:
- Notes consistently flag real should-have gaps (S1 bounds, ruff E501, scope persistence) -- not deferred must-haves
- All 13/13 must-haves passed in FR6; 11/11 in FR5
- The 2nd-cycle FR1 verdict shows QA does enforce must-haves (cascade test gap blocked PASS on cycle 1)
- PASS_WITH_NOTES is the expected verdict for phases that are functionally correct but have cosmetic/improvement items
- The W22 dead-end stores (H1/H2) were caught by the system-auditor at wave boundary, not by QA -- but this is by design (QA reviews individual phases; system-auditor reviews cross-phase integration)

The streak of PASS_WITH_NOTES (now 25+ consecutive across W19-W22) does suggest that achieving a clean PASS is rare, which may indicate either (a) the should-have bar is set slightly above what typical implementation achieves, or (b) there is always minor polish remaining. Neither is actionable as a process change -- the current calibration correctly separates blocking from advisory.

---

## FR1 Second QA Cycle Analysis

FR1 required a 2nd QA cycle because a cascade delete test gap was found during QA review. The retro (line 37) states CI-033 (pre-QA deliverable check) was "not applied rigorously enough."

**Root cause:** CI-033 checks that planned **files** exist on disk. It does not check that planned **test scenarios** cover all new code paths. The cascade delete path (migration 014 + FK handling) was a new code path introduced by FR1 but not covered by a test. CI-033 is working as designed -- this is a test plan gap, not a deliverable completeness gap.

**Mitigation:** CI-023 (pre-phase test plan) would catch this if it were being applied -- the implement agent would list "cascade delete test" as a scenario. But CI-023 has 0% compliance (still NOT EFFECTIVE after 2 waves). CI-038 (M1b enforcement gate) remains DEFERRED. No new proposal needed -- the existing deferred proposals cover this gap.

---

## Metrics

- Wave: 22
- Phases analyzed: 6 (FR1-FR6)
- Signal rows read: 2 (FR5, FR6 only -- FR1-FR4 missing from signal log)
- New patterns identified: 1 (dead-end stores broadened beyond app.state)
- Recurring patterns (previously seen): 1 (dead-end stores, 2nd occurrence)
- Proposals below evidence threshold (watch list): 4
- Past fixes verified effective: 6/8 (CI-031 partially effective, CI-023 not effective)
- Proposals generated: 3 (P1: 1, P2: 1, P3: 1)
