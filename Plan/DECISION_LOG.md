# Decision Log

All significant decisions made during execution — by agents and orchestrator.

| Date | Phase | Decision | Alternatives Considered | Rationale | Decided By |
|------|-------|----------|------------------------|-----------|------------|
| 2026-03-04 | Pre-Wave 1 | Governance upgrade: refined Red Check, added QA_CHECKLIST.md, ARCH_INVARIANTS.md, RCA requirement, static merge gates | Ship as-is (8.8/10 score) | Human review identified 5 gaps that compound across 28 phases — fixed before Wave 1 starts | Human + Orchestrator |
| 2026-03-04 | F4 | In-memory rate limiting for login attempts (dict of timestamps per email) | Redis-backed rate limiting, DB-backed tracking | Phase 1 runs on single machine; in-memory is simplest correct approach. Can swap to Redis in Phase 2 when scaling. | Code Agent |
| 2026-03-04 | F4 | SHA-256 hash for refresh token storage instead of bcrypt | bcrypt for tokens, plaintext | Refresh tokens are high-entropy random strings; SHA-256 is sufficient and fast. bcrypt is for low-entropy passwords. | Code Agent |
| 2026-03-04 | F4 | Added mypy override for jose/passlib + installed types-passlib | Inline type: ignore comments | Project-level override is cleaner and matches existing pattern for langgraph/langchain_core | Code Agent |
| 2026-03-04 | F4 | Chat stub endpoint in app.py for auth middleware testing | Separate router file | Minimal stub needed only for test_protected_endpoint_rejects_unauthenticated; will be replaced by real chat endpoint in later phase | Code Agent |
