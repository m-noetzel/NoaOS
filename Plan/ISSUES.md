# Issues Tracker

Problems encountered during execution and their resolutions.

**Severity levels:**
- **LOW** — Noted, no action required
- **MEDIUM** — Addressed during normal workflow
- **HIGH** — Blocks progress, must be resolved before continuing
- **CRITICAL** — Human required immediately, orchestrator stops and escalates

| ID | Phase | Severity | Description | Status | Resolution |
|----|-------|----------|-------------|--------|------------|
| I1 | F4 | LOW | Tests use mock session object instead of real SQLAlchemy session; broad exception assertions | Open | Acceptable for unit tests; tighten assertions when integration tests added |
| I2 | OC3 | LOW | Audit log query/export endpoint not implemented (only write path exists) | Open | Deferred to Wave 5/6 when UI needs it |
| I3 | DW1 | LOW | `app.py` wiring for private worker not done; 24h windowing for health stats not implemented | Open | Wiring deferred; windowing acceptable for MVP |
| I4 | DW4 | LOW | `router.py` now wired to PrivacyClassifier (Wave 4 retro R1); LLM-based classification deferred | Resolved | Router delegates to PrivacyClassifier as of DW4; LLM classification is a future enhancement |
| I5 | TI6 | LOW | `tool_node` wired to ToolRegistry (pre-Wave 5 cleanup); rate limiter is fixed-window not sliding-window despite docstring | Partial | tool_node wired; rate limiter accuracy deferred to pre-AB1 fix (retro R5) |
| I6 | TI6 | LOW | `extract_idempotency_key` is case-sensitive for header lookup; may not match FastAPI/Starlette header normalization | Open | Validate during integration testing (retro R6) |
