# Project Health Brief — 2026-03-14 (MVP-fixes)

**Score: 7/10**
Starting at 5: +0 (Wave 22 still in progress — MVP batch is mid-wave), +1 (last QA verdict PASS_WITH_NOTES, previous was also PASS_WITH_NOTES — acceptable), +1 (zero critical findings open), +1 (application security posture fully green), +0 (infrastructure security has warn — no lockfile, carried from baseline; mid-wave so not re-audited), +1 (E2E + integration tests exist: real-DB integration in scope persistence tests). Subtract: -1 for infrastructure warn (carried from QE6 baseline), -1 for open medium findings (4 new findings from this batch — MVP-M1, MVP-M2, MVP-L1, MVP-L2). Score = 5+1+1+1+1-1-1 = 7. Stable at 7/10.

## What Happened (since last brief)

1. **Six dead-end stores fixed** — W22-H1/H2 wired agent limits and approvals toggle through the full chain (settings → chat → runner → AgentState → agent_node/gateway). These were flagged as high-severity findings; the resolution closes the most critical UX promise gap from Wave 22 planning.
2. **Memory tool now visible on Tools page** — MVP-H2 fixed the privacy_mode default that was hiding private-domain tools. `memory` and `external_memory` added to TOOL_CAPABILITIES. Users can now see and enable memory tools from the UI.
3. **Scope overrides persist across restarts** — FR6-L1 replaced the in-memory `_scope_overrides` dict with DB-backed storage (migration 017, scope_overrides TEXT column on user_settings). User tool scope configurations now survive server restarts.

## Greatest Risk

**QueueDrainWorker is decorative.** MVP-H3 wires the enqueue path (private.chat tasks get stored in the DB queue with a "queued" SSE response to the user), but the drain worker never actually dispatches them. `_drain_one()` marks tasks as "processing" and stops. Private.chat requests queued while the private domain is unavailable will sit in the DB permanently — the user receives a "queued" promise that is never fulfilled. This is intentionally deferred to Phase 2, but it means the feature is currently a UX lie: users believe their request will be executed when the domain comes back online, but it won't be. If the private domain goes down for any reason in production, affected users will see their requests silently disappear. This is the single biggest risk to user trust.

## Decisions Needed

- **Phase 2 dispatch for QueueDrainWorker:** Decide timeline for implementing actual task dispatch in `_drain_one()`. Until this is done, the MVP-H3 feature is half-complete and should not be promoted as "queue and resume" in user documentation.
- **enable_tool endpoint scope:** Should POST /tools/{name}/enable accept function-level keys like `memory__remember`? Currently it succeeds but creates a no-op grant. Either restrict to TOOL_SCHEMAS top-level keys, or document that function-level grants are unsupported via this endpoint.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All new endpoints require auth. approvals_enabled cannot be overridden per-request (not in ChatRequest). |
| Secrets | ok | Queue payload excludes API keys. scope_overrides uses json.loads (no eval). No hardcoded secrets found. |
| Domain isolation | ok | No cross-domain imports. privacy_mode filter pattern anchored with `^...$`. |
| Input validation | ok | W22-M2 adds ge/le constraints on agent limit fields. scope_name validated against registry. |
| Error handling | ok | All new except blocks log with warning/exception. No silent swallowing. No success-on-error. |

## Security Posture — Infrastructure

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | N/A — mid-wave, not re-audited. Baseline: 107 scoped allow rules, deny blocks dangerous patterns. |
| Docker config | ok | N/A — mid-wave. Baseline: no root, no privileged, no secrets in ENV (per QE6 audit). |
| CORS / network exposure | ok | N/A — mid-wave. Baseline: explicit localhost origins, wildcard rejected. |
| Secrets in repo | ok | N/A — mid-wave. Baseline: only .env.example tracked, .env.secrets gitignored. |
| Dependency pinning | warn | No lockfile. Loose `>=` pins with upper bounds. Carried from QE6 baseline. |

## Risks You Are Taking

1. **Queued private tasks never execute (High probability, High impact):** If the private domain goes offline, any chat request in private mode is silently lost after the user receives a "queued" promise. This is not a crash — it's a silent data loss that affects user trust. The risk is real the moment anyone uses private mode with an unreliable private-worker.

2. **agent_node falls back to hardcoded MAX_TOOL_CALLS=10 if max_tool_calls is None in state (Low probability, Low impact):** The `or` operator in `agent_node` means a max_tool_calls value of 0 (theoretically impossible via API validator, but possible via direct DB write) would silently use the default. Validator enforces ge=1 so this is unlikely in practice.

3. **No dependency lockfile (Medium probability, Low impact):** Loose `>=` pins mean a new upstream release could introduce a breaking change on the next `pip install`. No CI pins to specific hashes. Standard risk for Python projects without lock files; low likelihood of production breakage given typical package stability but worth addressing before scaling deployments.
