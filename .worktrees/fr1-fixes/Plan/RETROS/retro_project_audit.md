# Project Audit Retrospective

**Date:** 2026-03-07
**Trigger:** Full codebase audit (FINDINGS.md) revealed 49 issues — 6 critical, 10 high, 14 medium, 5 architectural, 14 frontend — across a codebase that had 14 completed waves, 16 QA reviews (all PASS or PASS_WITH_NOTES), and 569 passing tests.
**Rating:** 4/10 — excellent blueprint, prototype-grade implementation.

---

## The Central Question

How did 14 waves of spec-driven, QA-gated, test-first development produce code where:
- The core tool dispatch crashes at runtime (C1)
- An attacker can forge auth tokens with an empty string (C5)
- The dual-domain isolation — the project's defining architectural principle — is violated in code (C2)
- 10 subsystems are stubs or dead code
- 15+ locations silently swallow all exceptions

All while every QA review said PASS?

---

## Root Cause Analysis

### RC1: Tests Validated Shape, Not Behavior

**The single biggest problem.** All 569 tests pass, but they test against mocks. The tool dispatch test mocks the executor, so C1 (returning `Future` instead of `dict`) was never caught by any test. The worker tests mock HTTP calls, so H1 (workers have no real endpoints) appears "tested." The SSE tests mock the event source, so UI-C1 (wrong BASE_URL) was invisible.

The test-first pipeline verified that code *exists and has the right structure*, not that it *works when connected to real dependencies*. Every phase produced a green test suite that proved nothing about runtime behavior.

**Evidence:** 569 tests pass. The first real chat message would crash on C1.

### RC2: QA Reviewed Deliverables Against the Plan, Not Against Reality

Every QA review asks: "Did the phase deliver what the plan said?" This is the wrong question. The right question is: "Does this code actually work in the running system?"

Examples:
- Wave 6 QA: *"Auth tokens stored in localStorage (standard for SPAs; HttpOnly cookies would be more secure but not required per spec)"* — identified the issue, dismissed it. This is exactly C6.
- Wave 6 QA: *"No XSS vulnerabilities identified"* — missed H10 (regex-based HTML sanitization in Notion tool).
- Every QA review checks "No hardcoded secrets" (good) but never checks "Is the JWT secret actually validated at startup?" (C5).

QA measured plan compliance, not code quality.

### RC3: Zero Integration Testing

14 waves. 569 unit tests. **Zero integration tests.** No test ever:
- Started a FastAPI server and sent an HTTP request
- Connected to a real (or test) Postgres database
- Sent a chat message through the orchestrator pipeline
- Verified that the external worker talks to a real LLM provider
- Checked that SSE streaming works end-to-end

The "verify green" gate in the pipeline runs `pytest` — which runs unit tests with mocks. There is no gate that verifies the system works as a system.

### RC4: Speed Was Celebrated, Thoroughness Was Not

Every retrospective highlighted speed as "What Went Well":
- Wave 3: "2.5x faster than estimated"
- Wave 4: "2.7x faster — strongest ratio yet"
- Wave 5: "4.2x faster — completed in 24% of estimated time"
- Wave 6: "1.8x faster — best estimate accuracy"

Speed was achieved by writing stubs, skipping wiring, and leaving skeleton implementations. The pipeline incentivized fast phase completion (green tests → QA PASS → mark complete), not thorough implementation. When the metric is "how fast did we finish?" the optimization is to produce the minimum code that passes the tests.

**The retros recommended tightening estimates** (R1 in Waves 4, 5, 6) — making the speedup *even faster* — instead of questioning whether the speed indicated insufficient depth.

### RC5: "Missing Wiring" Was a Recurring Pattern That Was Never Truly Fixed

The retros tracked this honestly:
- Wave 3: DW1 missing `app.py`, DW4 missing `router.py` (flagged)
- Wave 4: TI6 missing `tool_node` wiring (flagged again)
- Wave 5: "Resolved" via pre-wave cleanup
- Wave 6: No `App.tsx` router (flagged *again*)

The "resolution" in Wave 5 only wired the easy parts. The fundamental problem — workers have no functional endpoints (H1), tool dispatch doesn't actually work (C1) — was never addressed because the unit tests didn't require it. The wiring was deferred forever because nothing in the pipeline forced it to be done.

### RC6: Each Agent Optimized Locally, Not Globally

In multi-agent parallel execution, each agent has one goal: make its phase's tests pass. Agent DW2 builds an external worker skeleton with a `/health` endpoint and tests — PASS. Agent OC1 builds an orchestrator that calls tools — PASS. But nobody checks whether the orchestrator can actually reach the worker.

The agents have no cross-cutting awareness. They don't read each other's code. They don't test against each other's endpoints. The orchestrator trusts each agent's PASS verdict and merges. The result: 14 independently-passing modules that don't work together.

**This is not a problem with parallelism itself.** It's a problem with the verification boundary — each agent verifies only its own phase, and nothing verifies the whole.

### RC7: Bare `except` Blocks as a Symptom

The 15+ `except Exception: pass` blocks (H5) are likely a symptom, not a root cause. When code doesn't work or throws unexpected errors, wrapping it in `except: pass` makes the test green. This is the natural result of a pipeline that rewards green tests without reviewing the code that produces them.

### RC8: No Human Code Review

The CLAUDE.md pipeline has human gates at:
1. Wave planning approval
2. Architectural FAIL from QA
3. CRITICAL issues
4. Skill patches
5. Wave completion

None of these gates involve reading code. The human approved wave plans and wave completions but never reviewed actual implementations. The pipeline assumed QA + tests = sufficient review. They weren't.

---

## Is Multi-Agent Parallelism the Problem?

**No — but its failure mode is specific and was unmitigated.**

Parallel execution worked well mechanically:
- No merge conflicts across 6-way parallel in Wave 6
- No interface mismatches between parallel agents
- Correct dependency ordering (sequential where needed, parallel where independent)

The problem is that parallelism amplifies the "local optimization" failure (RC6). One sequential agent building everything would have been forced to wire things together — you can't build the tool dispatch without connecting it to the tool registry. Six parallel agents can each build their piece in isolation, and the pieces never get connected.

**The fix is not to abandon parallelism.** The fix is to add a cross-cutting integration verification step after parallel phases merge.

---

## Is Container Isolation the Problem?

**Partially — it makes integration testing structurally impossible.**

Claude in the dev container can run `pytest` but cannot:
- `docker-compose up` (Docker-in-Docker is not available)
- Start a real Postgres and run migrations
- Boot FastAPI and send HTTP requests
- Test SSE streaming end-to-end

This means the only available verification is unit tests with mocks — which is exactly the verification that failed to catch the real bugs. The container environment makes RC3 (zero integration testing) structural rather than accidental.

**However**, even within these constraints, the agents could have:
- Written tests that actually called the async functions (catching C1's `Future` return)
- Tested JWT validation with an empty secret (catching C5)
- Checked that `from noa.private_worker import ...` in `external_worker/` violates the architecture (catching C2)
- Used `ruff` rules or custom checks to flag bare `except` blocks (catching H5)

Container isolation explains the absence of end-to-end tests. It does not explain the absence of rigorous unit tests.

---

## Process Gaps and Recommendations

### P1: Add Integration Test Gate (Addresses RC1, RC3)

After each wave's phases merge, run an integration test phase that:
- Imports and calls actual functions (not mocked)
- Verifies cross-module interactions (orchestrator → tool dispatch → registry)
- Tests error paths with real exceptions (not `except: pass`)

Even without Docker/Postgres, this catches C1, C2, C5, and many others. Add this as a mandatory step between "verify green" and "QA review" in the phase pipeline.

### P2: QA Must Test Running Code, Not Plan Compliance (Addresses RC2)

Change the QA checklist from:
- "Did the phase deliver what was planned?" ❌

To:
- "Can I call the main function and get a correct result?" ✅
- "What happens when I pass bad input?" ✅
- "Does this code import anything it shouldn't?" ✅
- "Are there any `except Exception: pass` blocks?" ✅

The QA agent should be adversarial, not confirmatory.

### P3: Add Explicit Security Checklist to QA (Addresses RC2)

Every QA review must check:
- [ ] JWT/auth: secrets validated at startup, no fallbacks
- [ ] Input validation: all external inputs validated
- [ ] Token storage: httpOnly cookies, not localStorage
- [ ] CORS/CSRF: configured correctly
- [ ] Exception handling: no bare `except` blocks
- [ ] Domain isolation: no cross-domain imports
- [ ] Default-deny: permissions, tool access, capabilities

### P4: Wiring Is Not Optional (Addresses RC5)

**New rule:** A phase is not complete until its code is callable from the existing system. "Tested in isolation" is insufficient. If the phase builds an endpoint, the endpoint must be registered in the app. If the phase builds a service, the service must be instantiated in startup. No "wire it later."

### P5: Cross-Cutting Verification After Parallel Merge (Addresses RC6)

After N parallel agents merge into main, run a verification step that:
- Imports all modified modules together (catches import errors)
- Calls the highest-level function that connects the parallel pieces
- Verifies the combined behavior matches the wave's goal

This is the integration gate specifically designed for the parallel execution model.

### P6: Ban Bare `except` via Linting (Addresses RC7)

Add ruff rule `E722` (bare except) and `BLE001` (blind exception) to `pyproject.toml` as errors, not warnings. This makes it structurally impossible to swallow exceptions without being specific about what's caught.

### P7: Human Code Review Gate for Security-Sensitive Code (Addresses RC8)

Auth, JWT handling, token storage, CORS, domain isolation, tool permissions — these areas need human eyes. Add a human gate for any phase that touches auth, security, or domain boundaries.

### P8: Track Quality Metrics, Not Just Speed (Addresses RC4)

Stop celebrating speed. Replace "completed in X% of estimated time" with:
- Integration test coverage (% of cross-module paths tested)
- Exception handling quality (specific vs. bare)
- Stub/skeleton count (how many TODOs/NotImplementedError remain)
- Wiring completeness (registered endpoints / total endpoints)

### P9: Retrospectives Must Question PASS Verdicts (Addresses RC2, RC4)

When QA says PASS and phases complete 4x faster than estimated, the retro should ask: "Is this suspiciously fast? Are we building stubs?" Instead, every retro celebrated the speed. Add a mandatory retro question: "What would break if we ran this in production right now?"

---

## Verdict

The development process was well-structured in theory — spec-driven, test-first, QA-gated, with retros and human gates. But the verification layer was hollow. Tests tested mocks, QA checked plans, and speed was the primary metric. The result: a project that looks complete on paper (14 waves, 569 tests, 16 PASS reviews) but crashes on the first real request.

The multi-agent parallel approach is fine. The container constraints are limiting but not fatal. The core failure is that **nothing in the pipeline verified the system works as a system**. Fix that one gap (P1 + P2 + P5) and the quality floor rises dramatically.

---

## Action Items for Wave 14B (Quality & Cleanup)

1. Before starting QC1, add `E722` and `BLE001` to ruff config (P6)
2. Each QC phase must include at least one non-mocked integration test (P1)
3. QA for QC phases must verify by calling real code, not checking deliverable lists (P2)
4. After QC1-QC3 merge, run cross-cutting verification (P5)
5. Human reviews security-related changes in QC2 before merge (P7)
