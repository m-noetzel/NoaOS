# QA Review: Wave 24 Batch 1 (W23-FIX, CX1, DI1, MC1, LS1, OI1, VM1)

**Date:** 2026-03-20
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)

---

## Checklist Score

**Must-haves:** 10/13 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | FAIL | W23-FIX: fix implemented in FINDINGS.md description text but NOT in compose files. VM1: phase plan deliverable "Wire rag_ingest, rag_query, summarize, search RPC handlers" not implemented — stubs. FINDINGS.md not updated for TECH-H1 → LS1. |
| M2 | Negative Tests | PASS | All phases have negative/error path tests. DI1 classifier fallback on malformed JSON, CX1 doom loop at threshold, VM1 Ollama error paths, LS1 provider errors. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. User isolation enforced in VectorMemoryStore. No domain isolation violations. |
| M4 | Determinism | PASS | No wall-clock time in test assertions. No network calls in unit tests. |
| M5 | Implementation Completeness | FAIL | (1) W23-FIX: docker-compose.yml and docker-compose.dev-full.yml do NOT have external-data volume — bug not fixed. (2) VM1: rag_ingest, rag_query, summarize, search handlers remain stubs in private_worker/handlers.py. VectorMemoryStore never instantiated in app startup. (3) FINDINGS.md marks TECH-H1 as Open but LS1 was supposed to resolve it. |
| M6 | No Silent Error Swallowing | PASS | All new `except Exception: # noqa: BLE001` blocks log before swallowing. No bare excepts. |
| M7 | Wiring Completeness | FAIL | VectorMemoryStore (VM1) is implemented and tested but NEVER wired into app.py startup, any memory tool handler, or private worker handler. It is dead code from the running application's perspective. |
| M8 | Domain Isolation | PASS | No cross-domain imports. Private/external worker boundary clean. |
| M2b | Write-Path Test Fidelity | PASS | VM1 tests use mock sessions with per-call differentiation. CX1 idempotency tests mock write and read separately. |
| M3b | Write-Path User Scoping | PASS | VectorMemoryStore.store_fact() and recall_similar() both require user_id. MemoryFact model has user_id column. |
| M4b | Mock Interface Accuracy | PASS | AsyncMock used correctly throughout new tests. |
| M5b | Findings Currency | FAIL | FINDINGS.md line 209 marks DEV-H1 (W23-FIX) as "Resolved" with "Fixed:" text — but the actual fix is absent from the compose files. TECH-H1 remains Open but LS1 resolves it — finding should be updated. |
| M5c | Related-Issue Scope | PASS | No incomplete pattern fixes detected. |
| M2c | Source-Inspection Gate | PASS | No source-inspection-only tests without behavioral companions. |
| M8b | Cross-Language Field Optionality | PASS | NodeModelsConfig all fields are `str | None = None`. No new required fields in iOS-facing endpoints. |

**Should-haves:**

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| S1 | Error Handling & Boundaries | OPEN | LS1: `_stream_callback` is a module-level global. Concurrent requests share the same callback reference. Request A's tokens can be delivered to Request B's SSE queue. Single-user system mitigates this, but worth noting. |
| S2 | Code Consistency | PASS | Consistent naming, layering, typed state via AgentState TypedDict. |
| S3 | Migration & Rollback | PASS | Migrations 020, 021, 022 all have downgrade(). Migration 022 handles pgvector-not-available via TEXT fallback. |
| S4 | Documentation | PASS | All public functions annotated. Non-obvious logic commented. |
| S5 | Integration Smoke Test | OPEN | All 7 phases have only mocked unit tests. No non-mocked integration test exercises any of these features end-to-end. VM1 VectorMemoryStore uses mock AsyncSession throughout. LS1 streaming uses mock httpx responses. Per CI-016, at least one DB-touching integration test is required for each phase with DB-touching endpoints. CX1 (IdempotencyKey table), VM1 (memory_facts table), MC1 (user_settings.node_models column) all touch the DB without a real-DB test. |

---

## Spec Compliance

### W23-FIX
- **SPEC.md §13.2** (private data persistence): External worker MemoryStore must write to persistent volume. The phase plan says to add `external-data:/data` to docker-compose.yml. The fix is described in FINDINGS.md DEV-H1 as complete but the compose files do not contain it. The bug is **not fixed**.
  - `docker-compose.yml` external-worker service: only has `coding-workspace:/workspace` — no `/data` volume.
  - `docker-compose.dev-full.yml` external-worker-dev service: no `/data` volume at all.
  - `docker-compose.dev-full.yml` volumes section: no `dev-external-data` entry.

### CX1
- Checkpointer upsert: PASS — `INSERT ... ON CONFLICT DO UPDATE` in PostgresCheckpointer.save().
- Idempotency persistence: PASS — DB-backed with in-memory fallback, sweep method, ON CONFLICT DO NOTHING.
- Doom loop detection: PASS — `_check_doom_loop()` in tools.py, threshold 3 in last 6 results, works for both tool call formats.

### DI1
- Task classifier node: PASS — `classifier_node` in `nodes/classifier.py`, 4 task types, JSON parse with fallback.
- AgentState extended with `task_type: str | None`: PASS.
- Graph wired: router → classifier → planner → agent: PASS.
- Classifier uses empty tools list: PASS (`tools=[]`).
- Falls back to "execution" on error: PASS.

### MC1
- `node_models` JSON column in user_settings: PASS — migration 021, column present.
- PATCH /settings extended with node_models: PASS — `NodeModelsConfig` Pydantic model, `UpdateSettingsRequest.node_models`.
- Runner seeds model_config from user settings: PASS — `node_models=user_settings.get("node_models", {})` in chat.py.
- Router merges user config with privacy-based defaults: PASS — `{**router_config, **existing_config}` with agent enforced.
- IntelligenceSettings frontend component: PASS — component exists, integrates with PATCH /settings.

### LS1
- `complete_stream()` in all 4 providers: PASS — Anthropic, OpenAI, Google AI, Ollama all have the method.
- ProviderRouter has `complete_stream()`: PASS.
- Agent node uses streaming when callback set + no tools: PASS.
- Runner creates asyncio.Queue for token_stream events: PASS.
- TECH-H1 functionally resolved: PASS (but FINDINGS.md not updated).

### OI1
- `plan`, `archetype`, `thoughts`, `use_react` in AgentState: PASS.
- `nodes/planner.py` with archetype selection: PASS.
- Planner LLM call skipped for simple_utility: PASS.
- Agent node injects plan + ReAct instruction into system message: PASS.
- ReAct mode parses "Thought: ..." lines: PASS.
- simple_utility + execution tasks skip ReAct: PASS (only research/decision_intelligence set use_react=True).

### VM1
- MemoryFact model with Vector(768) column: PASS — with pgvector fallback to Text.
- VectorMemoryStore with cosine similarity: PASS — implemented.
- OllamaClient.embed() for nomic-embed-text: PASS.
- Migration 022 with pgvector extension + HNSW index: PASS.
- Trust tiers (pending/approved): PASS — vector search only against approved.
- **Wire rag_ingest, rag_query, summarize, search RPC handlers in private worker: FAIL** — handlers return stubs (`{"status": "queried", "results": []}`) with no VectorMemoryStore usage.
- **VectorMemoryStore never instantiated in app startup: FAIL** — no reference in app.py.

---

## Test Coverage

| Phase | Tests | Spec Coverage | Negative Tests | Notes |
|-------|-------|--------------|----------------|-------|
| W23-FIX | 0 | N/A — infra change | N/A | No tests needed for compose fix |
| CX1 | 22 (12 doom + 10 idempotency) | PASS | PASS — threshold, error cases, boundary | |
| DI1 | 30 | PASS | PASS — fallback on error, invalid JSON, model=none | |
| MC1 | 13 | PASS | PASS — null handling, all-none strips | |
| LS1 | 15 | PASS | PASS — provider errors, non-streaming fallback | |
| OI1 | 25 | PASS | PASS — planner failure, empty messages, no system msg | |
| VM1 | 20 | PASS | PASS — Ollama unavailable, duplicate, DB error, pending exclusion | |

**Total: 125 new tests, all passing.**

**Missing non-mocked integration tests (S5):** All 7 phases rely entirely on mocked unit tests. CX1 IdempotencyKey table, MC1 node_models column, and VM1 memory_facts table are not tested against a real database. S5 per CI-016 requires at least one non-mocked integration test for DB-touching endpoints.

---

## Anti-Pattern Scan Results

**M6: Bare except blocks**
```
src/noa/orchestrator/runner.py:107:   except Exception:  # noqa: BLE001 — logs warning
src/noa/orchestrator/runner.py:373:   except Exception:  # noqa: BLE001 — logs warning
src/noa/orchestrator/runner.py:413:   except Exception:  # noqa: BLE001 — logs warning
src/noa/orchestrator/runner.py:519:   except Exception:  # noqa: BLE001 — logs warning
src/noa/orchestrator/nodes/classifier.py:72:  except Exception:  # noqa: BLE001 — logs warning, returns fallback
src/noa/orchestrator/nodes/planner.py:155:  except Exception:  # noqa: BLE001 — logs warning, returns no plan
```
All bare Exception catches are noqa-annotated and log before swallowing. M6 PASS.

**M7: Router registration**
```
grep include_router src/noa/api/app.py: settings_router included at line 523
```
New MC1 settings extension reuses existing settings_router — no new router needed. M7 PASS for phases that added endpoints.

**M7: VectorMemoryStore NOT wired**
VectorMemoryStore is not referenced in:
- `src/noa/api/app.py` (startup)
- `src/noa/private_worker/handlers.py` (_handle_rag_query, _handle_rag_ingest use stubs)
- `src/noa/api/v1/memory.py`

This is a blocking M7 violation. VM1 deliverable is dead code.

**M8: Domain isolation**
```
grep "from noa.private_worker" src/noa/external_worker/: No matches
grep "from noa.external_worker" src/noa/private_worker/: No matches
```
M8 PASS.

---

## Smoke Test Results

```
CX1 checkpointer: OK
CX1 IdempotencyKey model: OK
CX1 doom loop detection: OK
DI1 classifier node: OK
DI1 AgentState extensions: OK
MC1 ModelConfig extensions: OK
MC1 UserSettings.node_models column: OK
OI1 planner node: OK
OI1 _parse_react_thoughts: OK
LS1 complete_stream in all providers: OK
LS1 ProviderRouter.complete_stream: OK
LS1/VM1 OllamaClient.embed: OK
VM1 VectorMemoryStore: OK
VM1 MemoryFact columns: OK
Graph topology (classifier+planner): OK

FAILED: 2 error(s):
  - W23-FIX FAIL: 'external-data' volume NOT present in docker-compose.yml
  - W23-FIX FAIL: 'dev-external-data' volume NOT in docker-compose.dev-full.yml
```

---

## Security

**VM1 user isolation:** VectorMemoryStore.store_fact() and recall_similar() both require user_id (keyword-only, no default). SQL queries include `WHERE user_id = :user_id`. PASS.

**CX1 IdempotencyKey:** The idempotency_keys table has no user_id column. Idempotency keys are opaque strings provided by the caller — if two users happen to use the same key string (unlikely but possible in theory), they'd get each other's cached responses. In practice keys are caller-generated UUIDs, making collisions negligible. Not a blocking security issue but worth noting.

**LS1 module-level stream callback:** `_stream_callback` is a process-global variable in `noa.orchestrator.nodes.agent`. If two requests execute concurrently (FastAPI async supports this), they share the same callback. Token queue for Request A could receive tokens from Request B's LLM call. The runner sets the callback before graph execution and clears it after, but without asyncio locks, concurrent graphs on the same process-wide event loop can race. This is a latent concurrency defect for multi-user production use. For a single-user deployment (current target) it is acceptable, but should be a FINDINGS entry.

**No hardcoded secrets discovered in new code.** PASS.

---

## Code Quality

**Mypy errors introduced by this batch:**
- `src/noa/tools/gateway.py:208`: `Returning Any from function declared to return "int"` — `result.rowcount` is typed as `Any` in SQLAlchemy's async result. The existing `# type: ignore[union-attr]` comment is now unused (different error). This is a new mypy error from CX1.
- `src/noa/api/v1/chat.py:143`: Pre-existing comparison overlap (PrivacyMode.PRIVATE Literal vs str | None) — not introduced by this batch.

**Ruff:** Clean on all new files.

**OI1 planner archetype fallback:** `ARCHETYPES.get(task_type, "execution")` for non-`simple_utility` tasks — this handles future task types gracefully.

**VM1 migration 022:** Uses `TEXT` fallback for embedding column, then ALTERs to `vector(768)` on PostgreSQL only. The `USING NULL` in ALTER ensures the type change doesn't fail on existing rows. Correct pattern.

**CX1 `_last_sweep` class-level state:** `ToolGateway._last_sweep` is a class variable (shared across all instances). This is fine for single-process deployment but would cause sweep under-frequency if multiple ToolGateway instances existed. Currently only one is created at startup.

---

## Deep Dive

### 1. W23-FIX: Fix Was Committed to FINDINGS.md But Not to Code

The most concerning issue in this batch: FINDINGS.md DEV-H1 was updated to say the fix is complete ("Fixed: Added `external-data:/data` to `external-worker`...") but the actual compose files were never modified. The PLAN.md still shows W23-FIX as "Planned" status, contradicting FINDINGS.md's "Resolved" marker.

Impact: Every container restart loses all external-domain memory facts. The Memory tool for external-domain conversations has zero persistence.

**Files to fix:**
- `/workspace/docker-compose.yml`: Add `external-data:/data` to `external-worker.volumes`, add `external-data:` to top-level `volumes:`
- `/workspace/docker-compose.dev-full.yml`: Add `dev-external-data:/data` to `external-worker-dev.volumes`, add `dev-external-data:` to `volumes:`

### 2. VM1: VectorMemoryStore Is Dead Code

VM1 implemented the VectorMemoryStore class, created the memory_facts table, added OllamaClient.embed(), and wrote 20 tests. But the class is never instantiated in the running application:

- `src/noa/api/app.py`: No VectorMemoryStore instantiation at startup.
- `src/noa/private_worker/handlers.py`: `_handle_rag_query` and `_handle_rag_ingest` return hardcoded stubs `{"status": "queried", "results": []}`.
- `src/noa/api/v1/memory.py`: Uses the old file-based MemoryStore, not VectorMemoryStore.

The phase plan explicitly states: "Wire `rag_ingest`, `rag_query`, `summarize`, `search` RPC handlers in private worker." This deliverable was not completed.

The memory_facts table will be created by migration 022, but no application code ever writes to it or reads from it. This is a "no dead-end stores" violation — inverted: a table with no writer.

### 3. FINDINGS.md Currency

Two findings currency issues:

1. **TECH-H1** (High, Open): States "No LLM token streaming" — LS1 implements streaming for all 4 providers. TECH-H1 should be marked Resolved by LS1.

2. **DEV-H1** (High, marked Resolved by W23-FIX): The resolution text describes a fix that was never applied to the source files.

### 4. LS1 Streaming: Token Queue Drained After Graph Completes, Not During

The token streaming design in `runner.py` drains the token queue after each node completes (`while not token_queue.empty(): token_queue.get_nowait()`). This means tokens are only delivered to the SSE client AFTER the agent node finishes its LLM call — defeating the purpose of streaming (showing tokens as they arrive). The `token_callback` puts tokens into the queue while `_graph.astream()` is processing the agent node, and then the runner drains them when the node is done.

This is a design issue: true streaming should yield tokens concurrently with the LLM generation, not after it completes. The current implementation buffers all tokens then delivers them in a burst — functionally identical to non-streaming with extra complexity.

To fix: The runner needs to drain the queue concurrently while astream() is processing the node, using asyncio.gather() or a separate consumer task.

### 5. LS1 Module-Level Callback Concurrency

As noted in the Security section, `_stream_callback` is process-global. For the current single-user deployment this is acceptable, but should be tracked.

---

## Blocking Issues

1. **W23-FIX not implemented** — `docker-compose.yml` external-worker service has no `external-data:/data` volume mount and no `external-data` named volume in the top-level `volumes:` section. `docker-compose.dev-full.yml` external-worker-dev has no `/data` volume. The data-loss bug W23-H1/DEV-H1 is **not fixed** despite FINDINGS.md marking it resolved. File: `/workspace/docker-compose.yml` lines 214-228, `/workspace/docker-compose.dev-full.yml` lines 175-199.

2. **VM1 VectorMemoryStore is dead code (M7 wiring failure)** — VectorMemoryStore is never instantiated in app startup and never called by any tool handler or memory endpoint. The private_worker handlers `_handle_rag_query` and `_handle_rag_ingest` remain stubs. The phase plan deliverable "Wire rag_ingest, rag_query, summarize, search RPC handlers" was not completed. File: `/workspace/src/noa/private_worker/handlers.py` lines 99-106.

3. **FINDINGS.md false resolution (M5b)** — DEV-H1 is marked "Resolved" with Fix description that was never applied to source files. TECH-H1 remains Open but should be resolved by LS1. These contradictions corrupt the project audit trail.

---

## Notes (for next cycle)

1. **LS1 streaming is post-node, not concurrent.** Tokens are queued during LLM execution but drained only after the agent node completes. This gives a burst of tokens rather than incremental delivery. True streaming requires concurrent queue draining alongside astream().

2. **CX1 gateway.py mypy error.** `src/noa/tools/gateway.py:208` — `result.rowcount` typed as `Any` causes `no-any-return` mypy error. Fix: `int(result.rowcount)` or cast explicitly.

3. **LS1 concurrency concern.** `_stream_callback` is module-level global. If concurrent requests ever run on the same event loop, tokens from one request's LLM call will be delivered to another request's SSE queue. Acceptable for single-user deployment; should be tracked as a finding for future multi-user hardening.

4. **S5 integration tests missing for all 7 phases.** No phase in this batch has a non-mocked integration test using a real DB. Per CI-016, this should be the norm for DB-touching phases. Consider a CX1/VM1 integration test pass.

---

## Decision Review

The critical question is ordering: W23-FIX was listed as Planned in PLAN.md but the implementor appears to have committed only the FINDINGS.md update without the actual compose file change. This is the "committed to docs but not to code" anti-pattern.

VM1 has a similar gap: the VectorMemoryStore class was built and tested, but the wiring step (private worker RPC handlers) was left as stubs. The private_worker's `_handle_remember` and `_handle_recall` already use the file-based MemoryStore — VM1 needed to replace or augment these with VectorMemoryStore calls, which was not done.

Both issues require a fix cycle before this batch can be marked Complete.

---

# QA Review: Wave 24 Batch 1 — Cycle 2

**Date:** 2026-03-20
**Verdict:** FAIL
**Reviewer:** qa-review agent (cycle 2)

## Cycle 2 Summary

Cycle 2 addressed a subset of the blocking issues from Cycle 1. Changes (all uncommitted, working tree only):

- `src/noa/private_worker/handlers.py`: `_handle_remember` and `_handle_recall` now generate real Ollama embeddings via a new `_get_embedding()` helper that calls `OllamaClient.embed()`. `_ollama_client` module-level instance added. This is a partial VM1 wiring improvement.
- `docker-compose.yml` and `docker-compose.dev-full.yml`: postgres image updated to `pgvector/pgvector:pg16`. (This was already in migration 022 but the service definition was lagging.)
- All 125 W24 Batch 1 unit tests still pass.
- `src/noa/orchestrator/runner.py`, `src/noa/orchestrator/nodes/agent.py`, `src/noa/api/v1/chat.py`, and other files: changes appear to be the original Wave 24 Batch 1 implementation (not Cycle 2 fixes) — these are uncommitted from the primary implementation commit.

## Cycle 2 Blocking Issues

### STILL BLOCKING: W23-FIX (external-data volume) — NOT FIXED

The `external-worker` service in `docker-compose.yml` still has no `/data` volume:

```yaml
# docker-compose.yml lines 214-215 (current)
volumes:
  - coding-workspace:/workspace  # Only writable volume
```

No `external-data:/data` mount. No `external-data:` in top-level `volumes:`. Identical situation in `docker-compose.dev-full.yml`. Smoke test confirms:

```
BLOCKING: docker-compose.yml has no external-data volume for external-worker
BLOCKING: docker-compose.dev-full.yml has no external-data volume for external-worker-dev
```

Only change to compose files: postgres image `postgres:16-alpine` → `pgvector/pgvector:pg16`. The data-loss bug (W23-H1/DEV-H1) remains unfixed.

### STILL BLOCKING: VM1 RPC Handlers Are Incomplete Stubs

Cycle 2 upgraded `_handle_remember` and `_handle_recall` to use real embeddings. However, the phase plan (PHASE_DETAILS.md VM1 deliverable #4) explicitly requires:

> - `rag_ingest`: accept `{"text": str, "metadata": dict}`, chunk text, embed each chunk, store in memory_facts with `category="rag"`
> - `rag_query`: embed query, vector search, return top-k chunks with similarity scores
> - `summarize`: send text to Ollama `/api/generate`, return summary string
> - `search`: keyword + vector hybrid search

All four remain hardcoded stubs (`handlers.py` lines 99-116):

```python
async def _handle_rag_query(payload):
    return {"status": "queried", "results": []}   # STUB

async def _handle_rag_ingest(payload):
    return {"status": "ingested"}                  # STUB

async def _handle_summarize(payload):
    return {"status": "summarized", "summary": ""}  # STUB

async def _handle_search(payload):
    return {"status": "searched", "results": []}    # STUB
```

Acceptance criterion 2 (`rag_query` returns non-empty results when facts ingested) and criterion 3 (all 4 previously-stubbed RPC handlers return real data) are not met.

### STILL BLOCKING: VM1 Missing Required Deliverables

Per PHASE_DETAILS.md VM1 Files table:

| Required File | Status |
|---------------|--------|
| `src/noa/private_worker/embeddings.py` | MISSING — `OllamaEmbedder` class never created |
| `tests/integration/test_vm1_pgvector.py` | MISSING — required integration test |

The `_get_embedding()` function in handlers.py duplicates what `OllamaEmbedder` was meant to encapsulate. Inline embedding code in the handler dispatcher is not the same as the planned dedicated embedding module.

### STILL NON-BLOCKING: CX1 gateway.py Mypy Error — NOT FIXED

`src/noa/tools/gateway.py:208` still has two mypy errors:
```
gateway.py:208: error: Returning Any from function declared to return "int"  [no-any-return]
gateway.py:206: error: Unused "type: ignore" comment  [unused-ignore]
```

Fix remains: `return int(result.rowcount)` and remove the stale `# type: ignore[union-attr]`.

## Cycle 2 Checklist Delta

| ID | Criterion | Cycle 1 | Cycle 2 | Notes |
|----|-----------|---------|---------|-------|
| M1 | Spec Traceability | FAIL | FAIL | VM1 rag handlers, embeddings.py, integration test still missing |
| M5 | Implementation Completeness | FAIL | FAIL | W23-FIX compose unchanged; VM1 4 stubs unchanged |
| M7 | Wiring Completeness | FAIL | FAIL | rag_query/rag_ingest/summarize/search all still stubs |

All other criteria remain unchanged from Cycle 1.

## Cycle 2 Test Results

```
125 passed in 0.39s
```

All existing W24 Batch 1 tests continue to pass. No regressions.

## Cycle 2 Smoke Test

```
handlers.py imports: OK
OllamaClient.embed signature: OK
VectorMemoryStore class import: OK
agent.py streaming functions import: OK
Graph topology OK: ['router', 'classifier', 'planner', 'agent', 'tools', 'responder']

ERRORS (6):
  - BLOCKING: _handle_rag_query is still a stub returning hardcoded empty results
  - BLOCKING: _handle_rag_ingest is still a stub
  - BLOCKING: docker-compose.yml has no external-data volume for external-worker
  - BLOCKING: docker-compose.dev-full.yml has no external-data volume for external-worker-dev
  - MISSING: src/noa/private_worker/embeddings.py (required VM1 deliverable)
  - MISSING: tests/integration/test_vm1_pgvector.py (required VM1 deliverable)
```

## Cycle 2 Blocking Issues (Consolidated)

1. **W23-FIX not applied** — `/workspace/docker-compose.yml` lines 214-215: `external-worker` volumes block has only `coding-workspace:/workspace`. Add `external-data:/data`. Add `external-data:` to top-level `volumes:` section. Same fix needed in `/workspace/docker-compose.dev-full.yml` for `external-worker-dev`.

2. **VM1: 4 RPC handlers still stubs** — `/workspace/src/noa/private_worker/handlers.py` lines 99-116: `_handle_rag_query`, `_handle_rag_ingest`, `_handle_summarize`, `_handle_search` all return hardcoded responses with no VectorMemoryStore usage. Phase plan acceptance criterion 2 and 3 fail.

3. **VM1: embeddings.py missing** — `src/noa/private_worker/embeddings.py` required by phase plan File table. The inline `_get_embedding()` in handlers.py does not satisfy this deliverable.

4. **VM1: integration test missing** — `tests/integration/test_vm1_pgvector.py` required by phase plan. No non-mocked DB test for any VM1 behavior.

5. **CX1: gateway.py mypy not fixed** — `src/noa/tools/gateway.py:208`: `no-any-return` + `unused-ignore`. Fix: `return int(result.rowcount)`.

## Cycle 2 Positive Progress

- `_handle_remember` and `_handle_recall` now use real Ollama embeddings (via `_get_embedding()`). This addresses VM1 acceptance criterion 4 (graceful degradation — embedding failure falls back to empty vector, not 500 error).
- postgres image updated to `pgvector/pgvector:pg16` in both compose files — required for migration 022 HNSW index to work.
- The upgrade to `_handle_remember`/`_handle_recall` means that `remember`/`recall` RPC calls now produce real vector-searchable embeddings. The two most-used memory handlers are fully functional.

## Cycle 2 Verdict: FAIL

This batch requires a Cycle 3 to address the 5 remaining blocking issues before it can be marked Complete. Per pipeline rules, a third FAIL triggers the RCA requirement (Plan/RCA/rca_W24_batch1.md).
