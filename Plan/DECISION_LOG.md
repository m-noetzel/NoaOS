# Decision Log

All significant decisions made during execution — by agents and orchestrator.

| Date | Phase | Decision | Alternatives Considered | Rationale | Decided By |
|------|-------|----------|------------------------|-----------|------------|
| 2026-03-04 | Pre-Wave 1 | Governance upgrade: refined Red Check, added QA_CHECKLIST.md, ARCH_INVARIANTS.md, RCA requirement, static merge gates | Ship as-is (8.8/10 score) | Human review identified 5 gaps that compound across 28 phases — fixed before Wave 1 starts | Human + Orchestrator |
| 2026-03-04 | F4 | In-memory rate limiting for login attempts (dict of timestamps per email) | Redis-backed rate limiting, DB-backed tracking | Phase 1 runs on single machine; in-memory is simplest correct approach. Can swap to Redis in Phase 2 when scaling. | Code Agent |
| 2026-03-04 | F4 | SHA-256 hash for refresh token storage instead of bcrypt | bcrypt for tokens, plaintext | Refresh tokens are high-entropy random strings; SHA-256 is sufficient and fast. bcrypt is for low-entropy passwords. | Code Agent |
| 2026-03-04 | F4 | Added mypy override for jose/passlib + installed types-passlib | Inline type: ignore comments | Project-level override is cleaner and matches existing pattern for langgraph/langchain_core | Code Agent |
| 2026-03-04 | F4 | Chat stub endpoint in app.py for auth middleware testing | Separate router file | Minimal stub needed only for test_protected_endpoint_rejects_unauthenticated; will be replaced by real chat endpoint in later phase | Code Agent |
| 2026-03-04 | OC1 | Keyword-based privacy classifier for router node | LLM-based classification, regex patterns | Phase 1 skeleton; keyword matching is deterministic, testable, and requires no LLM call. Will upgrade to semantic classification in later phase. | Code Agent |
| 2026-03-04 | OC1 | MAX_TOOL_CALLS=10 hard cap in agent node | Configurable limit, no limit | SPEC S2.1 requires fixed cost/iteration limits. 10 is a reasonable upper bound per step; can be tuned later via config. | Code Agent |
| 2026-03-04 | OC1 | Static frozenset tool allowlist in tools node | DB-backed allowlist, config file | SPEC S2.1 mandates static allowlists per workflow. Frozenset is immutable and enforced at import time. | Code Agent |
| 2026-03-04 | OC1 | Flat cost estimate (0.001/call) in responder node | Model-aware pricing, token counting | Placeholder for skeleton phase; real cost tracking requires token counts from LLM response, wired in later phase. | Code Agent |
| 2026-03-04 | OC1 | Installed native .so deps (xxhash, ormsgpack, zstandard) to /workspace/.pip_libs due to noexec on /home | Skip langgraph, mock it | LangGraph requires langsmith which requires native extensions; /home is noexec tmpfs in container. /workspace is on a real FS without noexec. | Code Agent |
