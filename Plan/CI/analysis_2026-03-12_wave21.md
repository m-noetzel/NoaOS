# Continuous Improvement Analysis — 2026-03-12 (Wave 21 Boundary)

## Summary

Wave 21 (Pipeline Excellence & Quality Infrastructure, QE1–QE6) achieved its headline goals: mypy
zero across 166 files, real Postgres integration tests (55/56 passing), and a fully-instrumented CI
pipeline. Despite this, the wave shipped two High findings (FK cascade 500 on thread DELETE, backup
container crash-loop from cap_drop interaction), one tooling data-integrity bug (traceability.py
destructive overwrite), and a uniform PASS_WITH_NOTES verdict across all 5 reviewed phases.

Three new patterns are proposed for improvement: cross-phase interaction testing at wave close (P1),
security config gating for debug endpoints (P2), and idempotent tooling generation (P2). One prior
pattern — source-inspection tests as the sole test form — reached critical mass in QE6 (15/16 tests).

The dominant backlog observation is that all 33 CI proposals (CI-001 through CI-033) have been
applied, resolved, or deferred. The backlog is fully triaged. Wave 21 now opens a new generation of
proposals (CI-034 onward).

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| W21-A | testing | high | 1 (audit H1) | DELETE /threads returns 500 due to FK constraint on usage_stats. Integration tests cover create/read but not delete paths with FK dependencies. |
| W21-B | infrastructure | high | 1 (audit H2) | Backup container crash-loops under cap_drop from DE3. Cross-phase interaction (DE3 + DE4) not tested end-to-end before wave close. |
| W21-C | tooling | medium | 1 (audit M3, retro) | traceability.py `--check` regenerates TRACEABILITY.md, destroying manually-added sections (mutation baseline). Tooling generator is not idempotent. |
| W21-D | security | medium | 1 (audit M2) | OpenAPI /docs and /redoc exposed unconditionally. Not caught by QA S3 checklist. Pattern existed before Wave 21; not introduced here, but should have been caught. |
| W21-E | process | medium | 6/6 phases | No pre-phase test plan written for any Wave 21 phase (CI-023 applied but not producing test plans). Consecutive count now 25 phases without a formal pre-phase test plan. |
| W21-F | process | medium | 6/6 phases | All 5 QA-reviewed phases passed with PASS_WITH_NOTES verdict. QA notes accumulate without a mandatory resolution gate before phase completion. |
| W21-G | testing | medium | 15/16 tests in QE6 | Source-inspection tests dominate QE6 (15/16). Pattern resurfaces each wave in config/infrastructure phases. CI-028 (M2c gate) applied but behavioral companion acceptance threshold not calibrated for infra phases. |
| W21-H | process | medium | 2/6 phases (QE5, QE6) | Severe estimation compression: QE5 at 0.38x ratio (17 min vs 45 est), QE6 at 0.12x ratio (7 min vs 60 est). Phases with fuzzy scope compress via silent scope reduction. |
| W21-I | infrastructure | medium | 1 (audit M4) | Integration tests (30 tests) fail in dev container without manual TEST_DATABASE_URL because Docker socket is unavailable inside the dev container. Developer experience gap. |
| W21-J | process | low | 1 (QE6 notes) | mutmut configured but no CI execution step exists. Config-without-execution gap: mutation testing is manual-only, defeating the purpose of tooling setup. |
| W21-K | testing | low | 1 (QE6) | QE6 TOML parsing uses string-split instead of tomllib (stdlib 3.11+). Fragile under format changes. |

---

## Patterns Identified

### Pattern 1: Cross-Phase Interaction Bugs (NEW — 2 instances in Wave 21)

**Phases:** W21-H1 (DELETE /threads 500 — QE4 added integration tests but did not cover delete paths;
thread delete cascade untested) and W21-H2 (backup container crash-loop — DE3 cap_drop + DE4 backup
script setpgid interaction untested).

**Root cause:** Per-phase testing verifies intra-phase correctness. Wave 21 introduced real integration
tests (QE4) that cover happy-path CRUD but do not cover delete/cascade paths or compose-level service
interactions. Neither the QA checklist nor the wave close process has a step that explicitly tests
cross-phase side effects before the system audit.

**Why it keeps happening:** The verify gate in CLAUDE.md checks that "data flows end-to-end" and the
feature "is wired and callable." This is intra-phase framing. No step says: "verify that previously
passing flows still pass after this phase's changes."

**Gap:** No existing gate or checklist item. The system audit is the only cross-phase check, but it
runs after the wave is already done.

**Evidence:** Retro lines 37–39 explicitly name this as a pattern risk. Audit H1 and H2 both
confirmed as cross-phase interaction failures.

**Impact estimate:** If a wave-close smoke test existed, both H1 and H2 would have been caught before
the system audit, saving one full audit cycle and the fixes that now become Wave 22 P1 action items.

---

### Pattern 2: Security Config Gaps Not Caught by QA S3 (NEW — persistent across waves)

**Phases:** W21-M2 (/docs exposure, audit), and W20-H1 (JWT_SECRET_KEY env-var name mismatch, audit).
These are both configuration-level security issues that the system audit catches but the QA checklist
does not.

**Root cause:** QA S3 ("Migration & Rollback") is evaluated per-phase for DB changes. The broader
security config surface (debug endpoints, environment variable name alignment between compose and code,
container capability mismatches) is not in any QA gate.

**Why it keeps happening:** The QA checklist was designed around per-phase code review, not
deployment-configuration correctness. Cross-cutting config invariants are checked only at audit time.

**Gap:** No QA gate checks whether `/docs` would be reachable in a production compose profile, or
whether capability grants are consistent across service definitions.

**Evidence:** Audit M2 (docs exposure), Audit H2 (cap_drop + backup), Retro lines 43–44 ("should be
caught by a security checklist item, not a system audit"), Wave 20 audit H1 (JWT env-var mismatch).

**Impact estimate:** 2 audit findings per wave that a pre-ship config checklist would catch.

---

### Pattern 3: Tooling Generators Without Idempotency Tests (NEW — 1 instance)

**Phases:** QE5 (traceability.py), W21-M3 (audit).

**Root cause:** traceability.py regenerates TRACEABILITY.md on `--check`, overwriting the manually-
added "Mutation Testing Baseline" section that QE6 expects. The generator has no merge/append mode
and no round-trip test. The QE6 test `test_traceability_has_mutation_baseline_section` fails because
TRACEABILITY.md was regenerated without the manual section.

**Why it keeps happening:** Tooling generators are typically tested for first-run correctness (generate
output), not for idempotency (generate → modify externally → regenerate → verify merge). The QA
checklist has no gate for this.

**Gap:** No existing checklist item requires that file-generating tools be idempotent or append-only
for manual sections.

**Evidence:** Retro lines 70–71 (tooling bugs ship undetected), Audit M3 and L2, QE5 review Beyond
the Test Plan item 4 (TRACEABILITY.md tracked vs generated).

---

### Pattern 4: PASS_WITH_NOTES as Steady State (ongoing — 5 consecutive phases this wave)

**Phases:** QE1, QE2, QE3, QE4, QE5, QE6 (all PASS_WITH_NOTES). Also all 7 Wave 20 phases and all 7
Wave 19 PR phases. This is now a multi-wave consecutive pattern.

**Root cause:** QA reviewers correctly identify minor issues and note them. The notes are not
systematically converted to FINDINGS.md entries or fixes before the phase is marked complete. The
pipeline has no step that says "resolve or escalate each QA note."

**Why it keeps happening:** PASS_WITH_NOTES is a valid final verdict. The pipeline permits advancing
with notes. Notes accumulate as deferred tech debt.

**Gap:** CI-013 (M5b) and CI-015 (Findings Sync) address finding currency. But they do not require
QA notes to be either resolved or escalated before phase completion. Notes that don't rise to FINDINGS
level are effectively dropped.

**Evidence:** Retro lines 31–32, 66–68, 89 (A8). All 6 QA reviews contain at least 2–3 unresolved
notes. Wave 21 notes that produced no action: QE4 HealthChecker fragility, QE4 dual 404/503, QE5
datetime.utcnow deprecation, QE6 no mutation CI step, QE6 fragile TOML parsing.

---

### Pattern 5: Pre-Phase Test Plan Still Absent (ongoing — 25 consecutive phases)

**Phases:** All 6 Wave 21 phases, all 7 Wave 20 phases, all 7 Wave 19 PR phases, previous waves.
CI-023 was applied (adding a mandatory pre-phase test plan step to the implement agent). Wave 21 is
the first post-application wave. Zero of 6 QA reviews mention a test plan existing.

**Root cause:** CI-023 added the step to implement.md (the agent skill), but all 6 QA reviews
explicitly note "No test plan was pre-written for [QEx]." This suggests the implement agent is not
using the skill, or the skill requirement is not being enforced.

**Gate effectiveness:** CI-023 applied. Zero compliance detected in Wave 21. The gate is not
effective.

**Impact:** The QA checklist has no item that blocks on test plan absence. The implement agent skill
has it, but there is no QA verification gate for test plan existence.

---

## Effectiveness of Past Fixes

| Proposal | Applied | Wave 21 Result |
|----------|---------|----------------|
| CI-009 (L12 Write-Path User Scoping) | Wave 19 | EFFECTIVE — no write-path scoping violations in any QE phase |
| CI-013 (M5b Findings Currency) | Wave 19 | EFFECTIVE — FINDINGS.md at 0 open going into audit. Pattern fully reversed. |
| CI-015 (Findings Sync Gate) | Wave 19 | EFFECTIVE — no stale findings at wave close |
| CI-016 (S5 Integration Baseline) | Wave 20 | EFFECTIVE — QE4 delivered 55 real Postgres integration tests. S5 OPEN dropped from 5/7 in Wave 20 to 3/6 in Wave 21 (QE1/QE3/QE6 legitimately exempt). |
| CI-017 (M8b Cross-Language Optionality) | Wave 19 | N/A — no iOS-backend contract phases in Wave 21 |
| CI-023 (Pre-Phase Test Plan) | Wave 20 | NOT EFFECTIVE — 0/6 phases produced test plans. Gate exists in skill but not enforced at QA. |
| CI-025 (iOS Contract Audit) | Wave 19 | N/A — no iOS-backend phases in Wave 21 |
| CI-028 (M2c Source-Inspection Gate) | Wave 20 | PARTIALLY EFFECTIVE — QE6 noted 15/16 source-inspection tests. Gate passed because one behavioral companion existed. But 15/16 ratio would have triggered concern under stricter calibration. |
| CI-030 (Ruff Gate on tests/) | Wave 20 | EFFECTIVE — zero ruff violations in any Wave 21 test file (confirmed by audit: "ruff: PASS, 0 errors across src/ and tests/") |
| CI-031 (M7 app.state Write-Only Detection) | Wave 20 | EFFECTIVE — no new dead-end app.state writes detected in Wave 21 QA reviews |
| CI-032 (Infrastructure Phase Estimate) | Wave 20 | PARTIALLY EFFECTIVE — QE4 (infra) estimated 90 min, actual 90 min. But QE5 (0.38x) and QE6 (0.12x) still show severe compression for fuzzy-scope phases |
| CI-033 (Pre-QA Deliverable Check) | Wave 20 | EFFECTIVE — no completeness FAIL verdicts in Wave 21 (DE1 Cycle 1 FAIL was the motivating event; not repeated) |

---

## Proposals

### CI-034: Wave-Close Cross-Phase Smoke Test

**ID:** CI-034
**Title:** Wave-close cross-phase smoke test covering critical delete and interaction paths
**Priority:** P1
**Target:** CLAUDE.md (Wave Boundary section)

**Evidence:**
- W21-H1: DELETE /threads returns 500 (FK cascade on usage_stats) — caught by system audit, not by
  QE4 integration tests. The QE4 thread integration suite includes a delete test
  (`test_delete_thread`) but it does not test the path where runs and usage_stats exist for the
  thread. Retro lines 37–39.
- W21-H2: Backup container crash-loop from cap_drop. DE3 + DE4 interaction. No compose-level
  end-to-end test verified backup container starts after hardening changes. Audit H2.
- Retro A5: "Add cross-phase smoke test at wave boundary covering auth + threads DELETE + backup
  health." Explicitly proposed as a wave action item.

**Root cause:** The wave boundary process (system-auditor → retrospective → ci agent → human gate)
has no automated step that re-runs a fixed set of critical integration scenarios before the audit.
The system auditor runs these manually (as evidenced by the endpoint status matrix), but this
catches bugs after the wave is already closed.

**Impact estimate:** Both W21-H1 and W21-H2 would have been caught in the pre-audit window,
reducing Wave 21's audit score impact and preventing them from becoming Wave 22 P1 action items.

**Proposed change — add to CLAUDE.md Wave Boundary section:**

```
**Wave-Close Smoke Test (before system-auditor):** Run the following fixed scenario set using the
ASGI test client against the live database. All must pass before submitting to system-auditor:

1. Register + login (auth baseline)
2. Create thread → send chat message → list messages (SSE path)
3. DELETE /threads/{id} where the thread has at least one run and usage_stats row (FK cascade)
4. PATCH /settings round-trip (settings path)
5. GET /health/backup (backup container health)
6. GET /health/tools (tool gateway)

Failure in any step = fix before audit. Document results as a table in the wave boundary retro.
```

---

### CI-035: QA S3 Security Config Checklist Items (Production Readiness)

**ID:** CI-035
**Title:** Add deployment-config security checks to QA S3 (debug endpoints, cap_drop audit, env vars)
**Priority:** P2
**Target:** Plan/QA_CHECKLIST.md

**Evidence:**
- W21-M2: /docs and /redoc accessible without auth. No QA gate checks this. Retro lines 43–44
  explicitly state this should be caught by the security checklist.
- W21-H2: backup container cap_drop incompatibility. No QA gate checks compose-level capability
  consistency.
- W20-F: JWT_SECRET_KEY env-var name mismatch between compose and code (Wave 20 audit H1). Same
  class: config-level security gap not in any QA gate.
- Two occurrences across consecutive waves. Both caught only at audit time.

**Proposed change — add to Plan/QA_CHECKLIST.md S3 section:**

```
| S3b | Deployment Config Security | For phases that add new routes or modify docker-compose.yml: (1) verify /docs and /redoc return 404 when ENVIRONMENT != "debug"; (2) verify any new cap_drop entries are compatible with the container's runtime needs (check setpgid, setuid requirements in shell scripts); (3) verify env-var names match between compose service definitions and Python os.environ lookups. |
```

---

### CI-036: Idempotent Generator Test Gate

**ID:** CI-036
**Title:** Require round-trip idempotency test for any phase that ships a file-generating tool
**Priority:** P2
**Target:** Plan/QA_CHECKLIST.md

**Evidence:**
- W21-M3 / QE5: traceability.py `--check` regenerates TRACEABILITY.md, overwriting the manually-
  added Mutation Testing Baseline section. This caused the QE6 test
  `test_traceability_has_mutation_baseline_section` to fail (L2 in audit).
- Retro lines 70–71: "Any tool that writes to a file should be tested with a round-trip: generate
  → modify externally → regenerate → verify idempotent merge behavior."
- This is a single confirmed instance, but the pattern (generators that destructively overwrite)
  is a well-known class of tooling bug. The retro identified it as systemic.

**Proposed change — add to Plan/QA_CHECKLIST.md M2 section:**

```
| M2d | Generator Idempotency | For phases that ship a tool which writes or updates files: verify the tool is idempotent (generate → run again → output unchanged) OR append-safe (generate → manually add a section → run again → manual section preserved). A round-trip test in the test suite is required; manual smoke test is acceptable only for the first run. |
```

---

### CI-037: QA Note Resolution Gate (Enforce PASS_WITH_NOTES Expiry)

**ID:** CI-037
**Title:** Require each QA note to be either resolved in-phase or escalated to FINDINGS.md before phase completion
**Priority:** P2
**Target:** CLAUDE.md (Phase Pipeline section) and Plan/QA_CHECKLIST.md

**Evidence:**
- Wave 21: 5 consecutive PASS_WITH_NOTES phases. Retro lines 31–32 name this as a normalization
  risk.
- Wave 20: All 7 phases PASS_WITH_NOTES.
- Wave 19 PR phases: All 7 PASS_WITH_NOTES.
- Cumulative QA notes not converted to action: QE4 HealthChecker fragility, QE4 dual 404/503,
  QE5 datetime.utcnow deprecation, QE6 no mutation CI step, QE6 fragile TOML parsing. None of
  these appear in FINDINGS.md.
- Retro A8: "Each PASS_WITH_NOTES verdict must produce ≥1 concrete fix in the same phase before
  marking complete."

**Root cause:** Notes are cheaper to write than to fix. The pipeline has no step that forces each
note to be dispositioned. CI-013 (M5b) enforces finding currency, but notes below the FINDINGS
threshold are not tracked anywhere.

**Proposed change — add to CLAUDE.md Phase Pipeline:**

```
**QA Note Disposition (after PASS_WITH_NOTES):** For each note in the QA review:
- Fix it immediately in the same phase (preferred), OR
- Escalate to FINDINGS.md as a Low finding (with phase reference), OR
- Accept with written rationale recorded in the phase's REVIEWS/ file

A phase is not complete until every QA note is dispositioned. The implement agent owns this step.
```

**Proposed QA_CHECKLIST.md addition:**

```
| M5d | QA Note Disposition | If prior cycle produced PASS_WITH_NOTES, confirm each note from that cycle is either fixed, in FINDINGS.md, or has written acceptance rationale. Zero undispositioned notes is the gate. |
```

---

### CI-038: Pre-Phase Test Plan Enforcement at QA Gate

**ID:** CI-038
**Title:** Add QA M1b gate requiring test plan existence before QA review proceeds
**Priority:** P2
**Target:** Plan/QA_CHECKLIST.md

**Evidence:**
- Wave 21: 0/6 phases had a pre-phase test plan. Every QA review notes its absence: "No test
  plan was pre-written for [QEx]."
- CI-023 was applied to implement.md in Wave 20 requiring a pre-phase test plan. Zero compliance
  in Wave 21 (first post-application wave).
- The implement agent skill has the requirement but the QA reviewer cannot enforce it — there is
  no QA checklist item that blocks on test plan absence.
- Pattern: 25 consecutive phases without a formal pre-phase test plan (all of Waves 19, 20, 21).
  CI-023 has not produced any observable change.

**Root cause:** CI-023 is a "soft" requirement in the implement skill. Without a QA gate that
checks for the test plan file and fails if absent, the requirement is advisory.

**Proposed change — add to Plan/QA_CHECKLIST.md:**

```
| M1b | Pre-Phase Test Plan | Verify that a test plan exists in Plan/PHASE_DETAILS.md or as a separate file (e.g., test-plan_{phase-id}.md) covering: spec sections exercised, happy-path scenarios, negative-path scenarios, and integration scenarios. PASS = plan exists. FAIL = no plan found. (CI-023 gate enforcement) |
```

---

### CI-039: Integration Test Delete/Mutation Coverage Gate

**ID:** CI-039
**Title:** Require at least one delete-path integration test per endpoint suite
**Priority:** P2
**Target:** CLAUDE.md (Implementation rules section)

**Evidence:**
- W21-H1: DELETE /threads/{id} returns 500. The QE4 threads integration suite includes a delete
  test but only tests the case where the thread has no associated run data. The FK violation
  occurs when usage_stats rows reference the run. The gap: integration tests cover happy-path
  reads and creates; delete paths with FK dependencies are untested.
- Retro lines 72–73: "For Wave 22, each integration test module should include at least one
  delete/cascade test."
- This is a new finding class that the QE4 integration test infrastructure enables testing but
  does not require.

**Proposed change — add to CLAUDE.md Implementation rules:**

```
**Integration test delete coverage:** Each integration test suite that covers a resource with
a DELETE endpoint must include at least one delete test that verifies the path where the
resource has associated child data (foreign key relationships). A delete test on an empty
resource is not sufficient.
```

---

### CI-040: Dev Container TEST_DATABASE_URL Setup

**ID:** CI-040
**Title:** Add TEST_DATABASE_URL to dev container environment for integration test developer experience
**Priority:** P3
**Target:** docker-compose.dev.yml (configuration change, not a process document)

**Evidence:**
- Audit M4: Integration tests (30 tests in 6 suites) fail in noa-dev container without manual
  TEST_DATABASE_URL because testcontainers cannot access Docker socket from inside the container.
- QE4 produced 30 integration tests that require real Postgres, but the developer flow to run
  them locally requires manual env var setup not documented anywhere.
- Single occurrence; developer experience gap rather than a quality gate gap.

**Proposed change:** Add `TEST_DATABASE_URL: postgresql+asyncpg://noa:noa@db:5432/noa_test` to the
`environment` section of the `noa-dev` service in `docker-compose.dev.yml`. Also add a note to
docs/SETUP.md about running integration tests locally.

Note: This is a configuration file change (not a process document). Human approval is required
before application per CI agent rules.

---

### CI-041: Nightly Mutation CI Job

**ID:** CI-041
**Title:** Add a weekly/nightly mutation test CI job for a single critical module (jwt.py)
**Priority:** P3
**Target:** .github/workflows/ci.yml

**Evidence:**
- QE6 notes item 5: "No CI mutation testing step. The phase plan says 'CI: run mutation tests
  on critical paths only' but no CI job or step runs mutmut."
- QE6 Beyond the Test Plan item 5: "Mutation testing is manual-only. A nightly mutation job
  would complete the loop."
- QE6 PASS_WITH_NOTES note 1: "Consider a weekly mutation job targeting jwt.py."
- Single phase occurrence, but the gap makes the mutation tooling setup from QE6 purely
  documentation/config with no automated execution.

**Proposed change:** Add a weekly mutation test job to ci.yml targeting `src/noa/auth/jwt.py`
only (fast — single file). Schedule: Sunday 03:00 UTC. Use `continue-on-error: true` (detection
only, not blocking). Generates a mutation score that developers can trend over time.

---

## Metrics

- Total problems scanned: 11 (W21-A through W21-K)
- New patterns identified: 3 (cross-phase interaction bugs, security config gaps, tooling generators)
- Recurring patterns (previously seen): 2 (PASS_WITH_NOTES steady state, pre-phase test plan absent)
- New proposals generated: 8 (CI-034 through CI-041)
  - P1: 1 (CI-034)
  - P2: 4 (CI-035, CI-036, CI-037, CI-038, CI-039)
  - P3: 2 (CI-040, CI-041)
- Past fixes verified effective: 7/11 checked (CI-009, CI-013, CI-015, CI-016, CI-030, CI-031, CI-033)
- Past fixes not effective: 1 (CI-023 — pre-phase test plan, 0% compliance in Wave 21)
- Past fixes partially effective: 2 (CI-028 — M2c, CI-032 — infra estimate)
- Past fixes N/A this wave: 2 (CI-017, CI-025 — no iOS-backend phases)

---

## Pre-Wave-22 Priority Order

1. **CI-034 (P1, human gate):** Wave-close cross-phase smoke test — apply to CLAUDE.md before Wave 22 begins. The W21-H1 (thread DELETE 500) fix that Wave 22 will implement should be covered by this test.
2. **CI-035 (P2):** QA S3b security config checklist — apply to QA_CHECKLIST.md.
3. **CI-037 (P2):** QA note disposition gate — apply to CLAUDE.md and QA_CHECKLIST.md.
4. **CI-038 (P2):** Pre-phase test plan QA enforcement gate — apply to QA_CHECKLIST.md. CI-023 is not effective without this.
5. **CI-036 (P2):** Generator idempotency gate — apply to QA_CHECKLIST.md.
6. **CI-039 (P2):** Integration test delete coverage rule — apply to CLAUDE.md.
7. **CI-040 (P3):** Dev container TEST_DATABASE_URL — apply to docker-compose.dev.yml.
8. **CI-041 (P3):** Nightly mutation job — apply to ci.yml.
