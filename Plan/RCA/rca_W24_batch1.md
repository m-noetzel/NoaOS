# RCA: Wave 24 Batch 1 — QA FAIL (2 cycles)

**Date:** 2026-03-20
**Phases:** W23-FIX, CX1, DI1, MC1, LS1, OI1, VM1

## Root Cause

The implement agent reported success for W23-FIX and CX1 but **did not actually write the code changes to disk**. Specifically:

1. **W23-FIX**: Agent reported adding `external-data:/data` volume to compose files but the files were unchanged on disk.
2. **CX1 (checkpointer)**: Agent reported replacing SELECT→INSERT/UPDATE with pg_insert upsert but checkpointer.py was unchanged.
3. **CX1 (doom loop)**: Agent reported adding DoomLoopError and detection logic to tools.py but the file was unchanged.
4. **CX1 (idempotency)**: Agent created the model/migration but did not update gateway.py dispatch methods to use DB-backed lookups.
5. **VM1 (RPC handlers)**: Agent reported unstubbing rag_query/rag_ingest/summarize/search but handlers.py stubs remained.

## Contributing Factors

- **No post-implementation verification by orchestrator**: The orchestrator trusted agent-reported success without independently verifying that files on disk matched the claimed changes.
- **QA was not run after each phase**: The pipeline requires QA after every phase, but QA was batched across 7 phases, delaying detection.
- **Agent tool result opacity**: Agent tool returns a summary string, not a diff. The orchestrator cannot verify actual file changes without reading the files.

## Corrective Actions

1. **Immediate**: All 4 blockers fixed manually by orchestrator with verified `ruff`/`mypy`/test passes.
2. **Process**: After every implement agent completes, orchestrator must verify key files were actually modified (spot-check at minimum).
3. **Pipeline**: Run QA per-phase or in small batches (max 3), not 7 at once.

## Resolution

All blockers resolved:
- W23-FIX: `external-data:/data` added to both compose files + volumes section
- CX1 checkpointer: pg_insert upsert implemented
- CX1 doom loop: DoomLoopError + _check_doom_loop + wiring in tool_node
- CX1 idempotency: _load_idempotency/_store_idempotency/sweep methods added to gateway
- VM1 handlers: rag_query, rag_ingest, summarize, search all implemented with real logic

2164/2165 tests pass (1 pre-existing CI backlog failure).
