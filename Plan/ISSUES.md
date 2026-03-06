# Issues Tracker

Problems encountered during execution and their resolutions.

**Severity levels:**
- **LOW** — Noted, no action required
- **MEDIUM** — Addressed during normal workflow
- **HIGH** — Blocks progress, must be resolved before continuing
- **CRITICAL** — Human required immediately, orchestrator stops and escalates

| ID | Phase | Severity | Description | Status | Resolution |
|----|-------|----------|-------------|--------|------------|
| I1 | F4 | LOW | Tests use mock session object instead of real SQLAlchemy session; broad exception assertions | Resolved | Broad `pytest.raises(Exception)` replaced with `TokenError`, `AuthError`, `AccountLockedError`; mock session kept for unit tests (acceptable pattern) |
| I2 | OC3 | LOW | Audit log query/export endpoint not implemented (only write path exists) | Resolved | Created `src/noa/api/v1/audit.py` with `GET /entries?trace_id=` and `POST /verify` endpoints; wired into app.py |
| I3 | DW1 | LOW | `app.py` wiring for private worker not done; 24h windowing for health stats not implemented | Resolved | HealthChecker started/stopped in app lifespan; 24h sliding-window stats via `stats_24h()` exposed in `/health/metrics` |
| I4 | DW4 | LOW | `router.py` now wired to PrivacyClassifier (Wave 4 retro R1); LLM-based classification deferred | Resolved | Router delegates to PrivacyClassifier as of DW4; LLM classification is a future enhancement |
| I5 | TI6 | LOW | `tool_node` wired to ToolRegistry (pre-Wave 5 cleanup); rate limiter is fixed-window not sliding-window despite docstring | Resolved | Replaced fixed-window counter with true sliding-window implementation using timestamp deque with eviction |
| I6 | TI6 | LOW | `extract_idempotency_key` is case-sensitive for header lookup; may not match FastAPI/Starlette header normalization | Resolved | Now checks canonical, lowercase, and full case-insensitive fallback per RFC 7230; tests added for lowercase and mixed-case headers |
