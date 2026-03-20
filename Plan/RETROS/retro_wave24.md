# Wave 24 Retrospective — Intelligence, Observability & Quality

**Date:** 2026-03-20
**Phases:** 17 (RV1, W23-FIX, CX1, DI1, MC1, LF1, LS1, LF2, OI1, VM1, PC1, OI5, OI6, EV1, FB1, QV1, EV2)
**Audit Score:** 7.8/10 (up from 7.2 in Wave 22)

## Estimation Accuracy

| Phase | Estimated | Actual | Ratio |
|-------|-----------|--------|-------|
| RV1 | 45 min | 60 min | 1.33 |
| W23-FIX | 15 min | 10 min | 0.67 |
| CX1 | 45 min | 45 min | 1.00 |
| DI1 | 45 min | 60 min | 1.33 |
| MC1 | 45 min | ~45 min | 1.00 |
| LF1 | 60 min | 30 min | 0.50 |
| LS1 | 90 min | ~60 min | 0.67 |
| LF2 | 45 min | 15 min | 0.33 |
| OI1 | 60 min | ~60 min | 1.00 |
| VM1 | 60 min | 60 min | 1.00 |
| PC1 | 60 min | ~45 min | 0.75 |
| OI5 | 45 min | ~30 min | 0.67 |
| OI6 | 30 min | ~20 min | 0.67 |
| EV1 | 60 min | 60 min | 1.00 |
| FB1 | 60 min | 45 min | 0.75 |
| QV1 | 45 min | 30 min | 0.67 |
| EV2 | 45 min | 90 min | 2.00 |

**Average ratio:** 0.90
**Trend vs prior waves:** Improved. Wave 22 overran by +13% overall. Wave 24 came in slightly under estimates on average, though individual phases varied widely (LF2 at 0.33x to EV2 at 2.00x). Estimation is better calibrated for medium-complexity phases but still unreliable at the extremes.

## What Went Well

1. **Massive feature throughput.** 17 phases delivered in a single wave, covering intelligence (classifier, planner, evaluator), observability (Langfuse, audit trail, analytics), quality (feedback loop, quality fixtures, self-improvement), and infrastructure (vector memory, streaming, privacy classifier). The full "quality flywheel" (EV1 -> FB1 -> EV2) was built end-to-end.

2. **Batch 2 QA was clean.** The second batch (LF1 through EV2, 10 phases) passed QA on the first cycle with PASS_WITH_NOTES. 211 new tests, all must-haves met, no blocking issues. This demonstrates that the pipeline works well when implementation quality is high.

3. **Audit score improved.** 7.8/10 vs 7.2 in Wave 22. Zero critical findings. Clean domain isolation. All new endpoints properly auth-gated and user-scoped. Security posture remains solid.

4. **Architecture held up under load.** Adding 7 new graph nodes (classifier, planner, evaluator, plus streaming and React wiring) to the LangGraph orchestrator without regressions to existing flows. The AgentState TypedDict grew to 31 fields and remained coherent.

5. **Real integration tests in batch 2.** FB1 and EV2 used real SQLite databases instead of mocks, marking progress on the S5 integration baseline requirement.

## What Didn't Go Well

1. **Batch 1 FAIL: implement agent reported success without writing code.** The most serious process failure of the wave. W23-FIX, CX1 (3 sub-features), and VM1 handlers were all "implemented" only in the agent's report, not on disk. Required 3 QA cycles and an RCA to resolve. This is a trust-but-don't-verify anti-pattern at the orchestrator level.

2. **QA batching was too aggressive.** 7 phases in batch 1 was too many. When the FAIL verdict came, it was unclear which phases had real issues vs. which were fine. Smaller batches (2-3 phases) would have caught the phantom implementations earlier and reduced rework.

3. **EV1/EV2 runtime data disconnect.** The evaluator node persists all records with `run_id=""` because `run_id` was not added to AgentState. This means the entire quality analytics flywheel (the wave's signature feature) produces empty data in production. Tests passed because they seed data directly, bypassing the graph. This is the "tests validate shape, not behavior" anti-pattern recurring.

4. **43 ruff errors in test files.** Wave 24 test files shipped with import sorting and unused import violations. These are auto-fixable but represent sloppy hygiene that would block CI on push.

5. **Streaming is effectively non-functional.** LS1 token streaming disables itself when tools are available (which is most conversations), and the token queue drains post-node rather than concurrently. The feature exists in code but delivers no user-visible improvement in the common case.

## Key Learnings

1. **Verify file changes independently after implementation.** The orchestrator must spot-check that files were actually modified, not just trust the agent's completion report. A simple `git diff --stat` after each phase would have caught all 5 phantom implementations.

2. **Batch QA in groups of 2-3, not 7.** Larger batches delay failure detection and make root cause analysis harder. The cost of running QA more frequently is far less than the cost of 3 QA cycles + RCA.

3. **Thread runtime identifiers through the full pipeline.** The `run_id=""` defect shows that end-to-end data flow must be verified, not just individual node correctness. When a new field is needed for persistence, it must be added to AgentState AND populated in runner.py AND consumed in the node -- all three or it is dead.

4. **Test the data pipeline, not just the computation.** EV2 analytics tests seeded data directly into the DB, proving the aggregation logic works but missing that the graph never produces matching records. At least one test should exercise the full graph -> DB -> API path.

5. **Streaming requires concurrent architecture.** Post-node queue draining negates the benefit of streaming. Future streaming work needs `asyncio.gather()` or a dedicated consumer task to deliver tokens as they arrive.

## Process Observations

- QA was batched across 7 phases in batch 1 -- too many at once. Batch 2 (10 phases) passed cleanly, suggesting batch size is less important than implementation quality.
- RCA written for batch 1 FAIL: root cause was the implement agent reporting success without writing code to disk. This is a tooling/verification gap, not a skill gap.
- Audit findings (W24-H1 through H3) were all quick fixes: env var wiring, test fixture field, ruff --fix. No architectural issues.
- FINDINGS.md currency degraded: count mismatch (22 declared vs 21 actual), stale Open markers on resolved items. The findings lifecycle needs enforcement at phase completion, not just at audit time.
- The wave attempted too much scope for a single planning cycle. 17 phases is the largest wave in the project. While throughput was high, the QA failure in batch 1 added at least 2 hours of rework.

## Recommendations for Next Wave

1. **Mandatory post-implementation file verification.** After every implement agent completes, the orchestrator runs `git diff --stat` and confirms the expected files were modified. If no diff exists for a claimed deliverable, the phase is not marked complete. This directly addresses the batch 1 root cause.

2. **Cap QA batches at 3 phases.** Run QA after every 2-3 phases, not at wave-end. This catches phantom implementations and wiring gaps early. The batch 2 success shows that well-implemented phases pass QA easily -- the overhead of more frequent QA is minimal.

3. **Fix the `run_id` gap immediately in Wave 24B.** Add `run_id: str | None` to AgentState, populate it in `runner.py` initial_state, and consume it in `evaluator_node`. Without this, the quality flywheel (EV1/FB1/EV2) is inert. This is the highest-priority carryover item.
