# Continuous Improvement Analysis — 2026-03-12 (Wave 20 Boundary)

## Summary

Wave 20 (DE1–GO3, seven phases) delivered CI/CD infrastructure, TLS, container hardening, backup
verification, and Google OAuth2 across three surfaces with zero architectural FAILs and no second-cycle
QA except on DE1. Three new pattern proposals emerge: expanding the ruff gate to cover `tests/`,
adding an explicit `app.state` write-only detection step to QA M7, and formalizing infrastructure phase
estimation brackets. The dominant prior P1 backlog (CI-013, CI-016, CI-017, CI-022) remains largely
unactioned through Wave 20; their effectiveness is assessed below. One prior P1 (CI-025 iOS contract
audit) appears effective: GO3's M8b check passed clean — first iOS-backend phase without a 422 failure.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| W20-A | testing | medium | 4/7 phases (DE1–DE4) | Config-only tests: infrastructure phases produced YAML/shell-text assertions rather than runtime behavior tests. S5 OPEN in all four. |
| W20-B | testing | medium | 7/7 phases | No pre-phase test plan written for any Wave 20 phase (same as every prior wave). |
| W20-C | process | medium | 1/7 phases (GO1) | 23 ruff violations in test file — source files pass, test files excluded from ruff gate. Same gap in PR2, PR4 Wave 19. |
| W20-D | architecture | medium | 1/7 phases (DE3) | `app.state.workers_degraded` set at startup; no endpoint or background task reads it. Dead-end store in violation of CLAUDE.md "no dead-end stores" rule. |
| W20-E | architecture | high | 2/7 phases (GO1, GO2) | ViewModel/view error-path tests missing. GO2: authorize-failure path. GO3: loadStatus + disconnect failure cases. Pattern absent from test plans. |
| W20-F | process | high | 2/7 phases (DE4, GO1) | Infrastructure runtime gaps: DE4 `PGPASSWORD` not in compose (backup script would fail first DR test); GO1 JWT_SECRET_KEY env-var name mismatch with compose (token encryption crashes). Both require immediate pre-Wave-21 fixes. |
| W20-G | process | critical | 1/7 phases (DE1) | Cycle 1 FAIL due to missing deliverables (4 of 5 files absent). Not a quality gap — a completeness gap. Pre-QA "are all planned files present?" step absent from pipeline. |
| W20-H | architecture | medium | 1/7 phases (GO1) | `_get_live_google_client()` traverses four levels of private attributes — silent break on any adapter/tool chain refactoring. No accessor on ToolGateway or app_state. |
| W20-I | security | medium | 1/7 phases (GO1) | `_oauth_states` dict no TTL — abandoned authorize flows accumulate entries. Flagged in both GO1 and GO3 QA. Single-user risk negligible now; becomes medium before any multi-user evolution. |

---

## Patterns Identified

### Pattern 1: Ruff Not Covering `tests/` — Repeated Across Waves

**Phases:** GO1 (Wave 20, 23 violations), PR2 (Wave 19, 4 violations), PR4 (Wave 19, noted). Three
occurrences of test-file ruff violations across two consecutive waves.

**Root cause:** The ruff command in both the pre-push hook and the CI workflow targets `src/noa/` only.
Test files in `tests/` are not scanned.

**Why it keeps happening:** The gate covers the place developers *think* to run it, not the place where
violations actually accumulate. Test files receive less review attention; without an automated gate,
cosmetic violations accumulate and only surface at QA.

**Existing coverage:** None. M6 (bare except) covers semantic concerns in source files. No gate checks
style/formatting in `tests/`.

**Retro reference:** `retro_wave20.md` SP1 (lines 133–144) provides the exact fix text. This is a
ready-to-apply, one-change proposal requiring no architectural decision.

---

### Pattern 2: Write-Only `app.state` Variables (Dead-End Store)

**Phases:** DE3 (Wave 20) `workers_degraded`. No prior wave instances in the QA record.

**Root cause:** DE3 wired a degraded-worker flag to startup but the M7 (wiring completeness) QA check
focuses on "is the code reachable from the running system?" — it does not specifically ask "does anything
*read* the flag that was just written?" The QA reviewer caught it as a "beyond the test plan" note
rather than an M7 finding.

**Existing coverage:** CLAUDE.md already states "No dead-end stores: if data is stored somewhere,
something must read it." However, this rule is in the implementation guidelines, not in M7 of the QA
checklist. The QA reviewer has no checklist item forcing them to grep for `app.state.{var} =` and
verify a consumer exists.

**Retro reference:** `retro_wave20.md` SP2 (lines 146–156) provides the proposed M7 addition verbatim.

---

### Pattern 3: Infrastructure Phase Estimation Systematically Over-Estimates

**Phases:** DE2 (3x under: 60→20 min), DE3 (2x+ under: 45→20 min), DE4 (1.5x under: 45→30 min).
One prior occurrence: no clean historical baseline for infrastructure phases before Wave 20.

**Root cause:** Phase estimates are built from scope descriptions without a type-based estimate bracket.
Infrastructure phases (Caddyfile, hardening flags, shell script) have a lower ceiling than feature
phases because their deliverables are bounded config artifacts, not multi-layer feature logic.

**Wave 20 impact:** The wave ran 20% under budget (~310 vs ~390 min). This is positive for delivery
but creates false impressions about future wave pacing. Infrastructure phases should be estimated at
20–30 min as a default bracket.

**Retro reference:** `retro_wave20.md` Estimation Observations (lines 121–125).

---

### Pattern 4: Pre-Phase Test Plans Absent — 19+ Consecutive Phases

**Phases affected:** All 7 Wave 20 phases (0/7 had a pre-phase test plan). Prior count: 12/12 across
Waves 18 and 19. Running total: at least 19 consecutive phases without a pre-phase test plan.

**Status of CI-023 (P2, proposed Wave 19 retro):** Not applied. The pattern is now 19 phases deep. No
QA reviewer has ever seen a pre-phase test plan for any phase in project history.

**Why this matters now more than before:** DE1's cycle 1 failure was a completeness gap — four planned
files were absent. A pre-phase test plan that lists "deliverable: ci.yml must exist and be valid YAML"
would have produced a self-check before QA submission. The absence of upfront coverage decisions also
directly contributed to the coverage gaps flagged in the DE1 QA review (5 planned test items absent).

---

### Pattern 5: FINDINGS.md Currency — Major Improvement Confirmed

**Wave 20:** 0/7 phases had stale FINDINGS entries. Wave 19 had 5/6 phases stale.

**Assessment:** The CI-013 (M5b) gate appears effective in Wave 20. No drift observed. This is a
confirmed pattern reversal. The retroactive addition of M5b to QA_CHECKLIST.md (applied mid/post Wave
19) is working.

**Remaining gap:** CI-015 (CLAUDE.md "Findings Sync" as a blocking pipeline step) status is still
unclear. Wave 20 had no drift, but the structural enforcement in CLAUDE.md may not have been applied —
the pattern resolved due to QA reviewer attention, not a pipeline gate.

---

### Pattern 6: S5 OPEN Across Infrastructure Phases (Structural, Not Failure)

**Wave 20:** 7/7 phases S5 OPEN. Wave 19: 5/6 phases.

**Analysis:** Unlike Wave 19 where S5 OPEN was a coverage failure (DB-touching endpoints with no
real-session tests), Wave 20's S5 OPEN is structurally justified for infrastructure phases:
- DE1–DE4: GitHub Actions / shell scripts cannot be executed locally
- GO3: iOS ASWebAuthenticationSession requires real device / simulator (CI-029 carve-out)
- GO2: Frontend tests are inherently mocked for OAuth flows

**However:** GO2 had an addressable S5 gap — the authorize-failure path was not tested at all, not
just untestable due to environmental constraints. The QA reviewer noted this as an S5 note. This
should be tracked separately from the inherent infrastructure S5 OPEN.

**Gate CI-016 status:** PR6 (Wave 19) satisfied it manually. The CLAUDE.md integration test baseline
rule was not confirmed as applied before Wave 20. No new violations in Wave 20 because the wave had
no DB-touching feature phases — the gate was not triggered.

---

## Effectiveness of Past Fixes

| Fix | Status at Wave 20 | Assessment |
|-----|-------------------|------------|
| CI-009 (L12 Write-Path User Scoping) | APPLIED 2026-03-11 | Effective — zero new write-path scoping violations in Wave 20. Pattern eliminated. |
| CI-013 (M5b Findings Currency Gate) | IN QA_CHECKLIST.md | Effective — zero FINDINGS.md drift in Wave 20. Reversal confirmed. |
| CI-015 (Findings Sync CLAUDE.md step) | Status unclear | Not tested by Wave 20 (no drift to detect). Verify CI-015 is actually in CLAUDE.md. |
| CI-016 (S5 integration baseline) | NOT CONFIRMED | Wave 20 had no DB-touching feature phases, so the rule was not triggered. Still required for Wave 21. |
| CI-017 (M8b Cross-Language Field Optionality) | IN QA_CHECKLIST.md | Effective — GO3 M8b PASS (`GoogleStatusResponse.scopes` correctly typed `[String]?`). First iOS-backend phase without a 422 failure. |
| CI-022 (L14 Full Request Model Audit) | NOT CONFIRMED in ARCH_INVARIANTS.md | Wave 20 had no iOS-backend contract fix phases. Cannot assess. Must be applied before Wave 21 iOS work. |
| CI-025 (iOS-backend contract audit in CLAUDE.md) | APPLIED (confirmed PR7) | Effective — GO3 passed M8b. No iOS 422 failures introduced. Direct causal connection plausible. |
| ruff E722/BLE001 | APPLIED | Effective — M6 passes clean across all Wave 20 phases. |
| CI-023 (pre-phase test plan) | NOT APPLIED | Pattern persists: 0/7 Wave 20 phases had a pre-phase test plan. 19 consecutive phases total. |
| CI-024 (multi-platform 2x multiplier) | NOT APPLIED | Wave 20 had no multi-platform overruns (GO2/GO3 close to estimate). Infrastructure phases were under. |
| CI-028 (M2c Source-Inspection Test Gate) | NOT APPLIED | Wave 20 had no TypeScript-source-scanning tests. Pattern dormant this wave. |
| CI-008 (M4b Mock Interface Accuracy) | NOT APPLIED | No regressions observed in Wave 20. |
| CRIT-2 stale noa-dev container | NOT FIXED | System audit confirmed routes missing from running server. Must fix before Wave 21. |

---

## Proposals

### CI-030 — Expand Ruff Gate to Cover `tests/` (P1)

**Evidence:**
- GO1 (`test_go1_oauth_backend.py`): 23 ruff violations (6 unused imports, 11 import sorting, 3 line length, 1 unused variable). Source files passed ruff clean. (`review_GO1.md` lines 97–98; `retro_wave20.md` lines 72–73)
- PR2 Wave 19: 4 ruff violations in test file
- PR4 Wave 19: ruff violations noted in QA
- Three occurrences across two consecutive waves; all preventable by one gate change

**Current state:**
Pre-push hook: `ruff check src/noa/`
CI workflow static-analysis job: `ruff check src/noa/`

**Proposed change:**
```
ruff check src/noa/ tests/
```
Both in `tools/pre-push-hook.sh` and `.github/workflows/ci.yml` static-analysis job.

**Target:** `tools/pre-push-hook.sh` + `.github/workflows/ci.yml`

**Priority:** P1 — this is not a process suggestion; it is a one-character fix with no false-positive
risk. Three occurrences across two waves establish it as a pattern, not a one-off. The fix is concrete
enough that P2 would be appropriate for a proposal requiring architectural judgment; this does not.

**Impact estimate:** Zero QA note overhead per wave if applied. Current cost: 1 QA note per wave from
test-file ruff violations appearing in reviews.

---

### CI-031 — Add `app.state` Write-Only Detection to QA M7 (P2)

**Evidence:**
- DE3 (`docker/private-worker/Dockerfile`-adjacent wiring): `app.state.workers_degraded = True` set
  at startup. No endpoint reads it; `/health/ready` does not gate on it. Only produces a startup log
  line. (`retro_wave20.md` lines 76–77; `review_DE3.md`; `audit_wave20.md` MED-3)
- CLAUDE.md rule "No dead-end stores: if data is stored somewhere, something must read it" already
  exists as an implementation guideline. It was not applied as a QA gate, so the reviewer noted it
  as "beyond the test plan" rather than an M7 finding.
- W20-C2 (`workers_degraded`) is now a carry-forward item for Wave 21 (R2 in retro).

**Proposed addition to `Plan/QA_CHECKLIST.md`**, as an extension to M7 (Wiring Completeness):

```markdown
Also verify: any flag or counter set on `app.state` (or module-level state) in the phase has at
least one consumer (endpoint, middleware, or background task that reads and acts on the value).
A state assignment with no reader is a dead-end store violation of CLAUDE.md L-rule "no dead-end
stores". Flag as M7 note if a consumer is absent or deferred.
```

**Target:** `Plan/QA_CHECKLIST.md` (M7 row)

**Priority:** P2 — one occurrence in Wave 20 (DE3), first confirmed case. Evidence threshold met
because the existing CLAUDE.md rule explicitly covers this pattern and the QA checklist does not,
creating a gap between the rule and its enforcement. A single occurrence with a clear rule/checklist
gap justifies P2.

**Impact estimate:** Would have caught `workers_degraded` as M7 rather than "beyond the test plan,"
ensuring it became an immediate FINDINGS entry rather than a retrospective recommendation.

---

### CI-032 — Infrastructure Phase Estimate Bracket in Phase Planning (P2)

**Evidence:**
- DE2: 60 min estimated → 20 min actual (3x under)
- DE3: 45 min estimated → 20 min actual (2x+ under)
- DE4: 45 min estimated → 30 min actual (1.5x under)
- All three phases involved single bounded deliverables (Caddyfile, hardening flags, shell script)
- `retro_wave20.md` lines 122–125: "Infrastructure phases (DE2, DE3, DE4) were systematically
  over-estimated. Future infrastructure phases should use ~20-30 min as the default estimate, not
  45-60 min."

Note: CI-024 addresses multi-platform overruns (1.5-2x over). CI-032 addresses the inverse: pure
infrastructure phases are systematically 2-3x under. Both calibration rules are needed.

**Proposed addition to phase-planning skill:**

```markdown
### Infrastructure Phase Estimate Bracket

Pure infrastructure phases (Dockerfile additions, GitHub Actions workflows, Caddyfile, docker-compose
service blocks, shell scripts) have a default estimate of **20–30 minutes per deliverable**. Do not
apply the 45–60 min default for these. Rationale: the deliverable is a single bounded config artifact,
not a multi-layer feature requiring service, API, test, and wiring changes.

Evidence: Wave 20 DE2 (20 vs 60 min), DE3 (20 vs 45 min), DE4 (30 vs 45 min). All infrastructure
phases ran 2-3x under standard estimates.

Exception: Infrastructure phases that include Python test suites exceeding 20 tests should add ~20
min per 10 tests beyond that (DE1: 74 tests, correctly estimated higher at 60 min even before Cycle 1).
```

**Target:** `.claude/skills/phase-planning/SKILL.md`

**Priority:** P2 — no quality impact, but systematic over-estimation creates false planning signals.
With Wave 21 including infrastructure work (QE phases), calibrated estimates prevent scope creep from
appearing as execution efficiency.

---

### CI-033 — Pre-Phase Deliverable Completeness Check Before QA Submission (P2)

**Evidence:**
- DE1 Cycle 1 FAIL: 4 of 5 planned workflow files absent (ci.yml, cd.yml, web-ci.yml, ios-ci.yml —
  only ci.yml present). Caused a full wasted QA cycle. (`review_DE1.md` lines 33–38; `retro_wave20.md`
  lines 57–59)
- The pre-QA verify gate in CLAUDE.md ("All tests pass + ruff + mypy + app loads + feature is wired
  and callable") does not include an explicit "all planned deliverables are present" check.
- The implement agent submitted for QA without verifying the phase plan's deliverable list.

**Root cause:** The verify gate addresses test and static-analysis quality, not completeness against
the phase plan. The implement agent has no structured step that reads back the planned deliverables
and confirms each file exists before submitting for QA.

**Proposed addition to CLAUDE.md** (Verify gate, before "QA Review"):

```markdown
**Deliverable Completeness (new step):** Before submitting for QA review, the implement agent must
read the phase's PHASE_DETAILS.md entry and verify that every planned file deliverable exists on disk.
For each planned file: confirm its existence and basic validity (parseable YAML, importable Python,
compilable Swift). A deliverable listed in the plan but absent from disk is a blocking issue — resolve
before QA submission. This check takes < 2 minutes and prevents completeness failures from consuming
a full QA cycle.
```

**Target:** `CLAUDE.md` (Phase Pipeline → Verify gate)

**Priority:** P2 — one direct occurrence (DE1), but the impact was a full wasted QA cycle and a round
of retrospective attention. The fix is structural (add a 2-minute self-check step) and has no
false-positive risk.

---

## Critical Infrastructure Bugs (Not CI Proposals — Require Immediate Fixes)

These are not process proposals; they are runtime bugs confirmed by the system auditor that need
immediate pre-Wave-21 fixes:

**CRIT-1 / W20-C1**: CI pipeline will fail on first push due to ruff import error in `src/noa/api/app.py`
and 51 mypy errors. Fix: `ruff check --fix src/noa/api/app.py`; for mypy, set `continue-on-error: true`
on the mypy step until QE2.

**HIGH-1 / W20-H1**: `GOOGLE_REDIRECT_URI` not in `docker-compose.yml`. Google OAuth2 will fail in
production. Fix: add `GOOGLE_REDIRECT_URI=https://${NOA_DOMAIN}/api/v1/auth/google/callback` to
noa-api environment block.

**HIGH-2 / W20-H2**: `_token_crypto.py` reads `JWT_SECRET_KEY` but compose passes `JWT_SECRET` and
`config.py` uses `SECRET_KEY`. Token encryption crashes at runtime if `JWT_SECRET_KEY` is absent. Fix:
rename to `SECRET_KEY` in `_token_crypto.py` or add `JWT_SECRET_KEY=${SECRET_KEY}` to compose.

These are already tracked in FINDINGS.md as W20-C1, W20-H1, W20-H2. They are listed here to ensure
Wave 21 begins with a working production deployment path.

---

## Effectiveness Summary

| Confirmed effective | Confirmed ineffective / not yet triggered |
|--------------------|------------------------------------------|
| CI-009 (L12) — no new write-path scoping violations | CI-016 — not triggered (no DB feature phases) |
| CI-013 (M5b) — zero FINDINGS drift in Wave 20 | CI-022 (L14) — not triggered (no iOS contract fix) |
| CI-017 (M8b) — GO3 M8b PASS; no iOS 422 failures | CI-023 — pre-phase test plans still 0/7 |
| CI-025 — GO3 passed contract check; pattern held | CI-015 — findings sync CLAUDE.md step unverified |
| ruff E722/BLE001 — M6 clean across all phases | CI-028 — no new source-inspection tests this wave |

---

## Backlog Triage Note

The backlog contains 29 proposals (CI-001 through CI-029). Wave 21 (QE1) plans to triage all of them:
apply or explicitly reject. The CI agent recommends the following priority guidance for the triage:

**Apply immediately (before Wave 21 coding begins):**
- CI-030 (this wave, P1): Ruff gate on `tests/`
- CI-022 (prior, P1): L14 to ARCH_INVARIANTS.md — needed before any Wave 21 iOS work
- CI-016 (prior, P1): S5 integration baseline to CLAUDE.md — needed for Wave 21 QE DB phases

**High-value P2 proposals (strong evidence, apply in Wave 21 QE1):**
- CI-023: Pre-phase test plan step in implement agent (19 consecutive phases absent)
- CI-013 / CI-015: If M5b is in QA checklist, verify CI-015 CLAUDE.md step is also present

**Deprioritize or reject:**
- CI-001 through CI-007 (from Insights Report, 2026-03-07): Review for continued relevance against
  current CLAUDE.md — several may be superseded by Wave 18-19 process changes
- CI-019, CI-021 (P3 FINDINGS entries): Confirm still open in FINDINGS.md; if tracked, mark resolved

---

## Metrics

- Input documents scanned: `Plan/CI/signals.md` (Wave 20 rows), `Plan/RETROS/retro_wave20.md`,
  `Plan/REVIEWS/audit_wave20.md`, `Plan/REVIEWS/review_DE1.md`, `Plan/REVIEWS/review_GO1.md`,
  `Plan/CI/IMPROVEMENT_BACKLOG.md`, `Plan/CI/analysis_2026-03-11_wave19_retro.md`
- Wave 20 phases analyzed: 7 (DE1, DE2, DE3, DE4, GO1, GO2, GO3)
- Total problems inventoried: 9 (W20-A through W20-I)
- New patterns identified: 2 (ruff gate not covering tests/; infrastructure phases systematically over-estimated)
- Recurring patterns confirmed: 3 (pre-phase test plans absent; S5 OPEN infrastructure; config-only tests)
- Past fixes verified effective: 4 (CI-009, CI-013, CI-017, CI-025)
- Past fixes confirmed not triggered: 2 (CI-016, CI-022)
- Past fixes not applied: 3 (CI-023, CI-015, CI-028)
- Proposals generated: 4 (P1: 1, P2: 3)
- Total P1 proposals outstanding (including prior): CI-016, CI-022, CI-030

---

## Priority Order for Human Review

**Require human gate before Wave 21 begins:**

1. **CI-030** (P1, NEW) — Ruff gate on `tests/`. Three-wave pattern, one-character fix. Apply
   immediately: `ruff check src/noa/ tests/` in pre-push hook and ci.yml.

2. **CI-022** (P1, prior) — L14 Full Request Model Audit to ARCH_INVARIANTS.md. Wave 21 QE phases
   may include iOS work. Not yet applied.

3. **CI-016** (P1, prior) — S5 integration baseline to CLAUDE.md. Wave 21 includes QE DB-touching
   phases (testcontainers, Postgres integration tests). The rule must be structural before those phases
   begin.

**Apply without human gate (P2):**

4. **CI-031** (P2, NEW) — `app.state` write-only detection in QA M7. Non-blocking addition to
   existing M7 check row.

5. **CI-032** (P2, NEW) — Infrastructure phase estimate bracket (~20-30 min default). Pure planning
   calibration.

6. **CI-033** (P2, NEW) — Deliverable completeness check before QA submission. Prevents DE1-class
   completeness failures.

7. **CI-023** (P2, prior) — Pre-phase test plan step in implement agent. 19 consecutive phases with
   no pre-phase plan. Apply before Wave 21 implement sessions.
