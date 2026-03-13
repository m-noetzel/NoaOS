# Project Health Brief -- 2026-03-12 (DE3)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: 4 of 7 phases remain), +0 (last QA PASS_WITH_NOTES, not PASS), +0 (10 open findings including 2 high -- no critical), -1 (application security warn: BE-M5 MemoryStore.store user_id gap, workers_degraded write-only), +0 (infrastructure security N/A mid-wave), +1 (E2E exists: 18 Playwright + integration tests), +1 (DE3 clean delivery, all containers hardened). Result: 6, clamped to 6/10. Holding steady at DE1/DE2 level.

## What Happened (since last brief)
1. All 5 application containers now have full security hardening: cap_drop ALL, no-new-privileges, resource limits, and log rotation -- Caddy was the last service without hardening (flagged by DE2 QA).
2. Startup degraded-mode probe added to noa-api lifespan: workers are probed via HTTP at startup and `app.state.workers_degraded` is set if either is unreachable.
3. Both worker Dockerfiles now have `HEALTHCHECK` instructions with 60s start periods, matching the compose-level healthcheck definitions.

## Greatest Risk
**The deployment stack has never been tested end-to-end in a real environment.** Three consecutive phases (DE1 CI workflows, DE2 TLS proxy, DE3 container hardening) have added deployment infrastructure validated exclusively by static file parsing. Resource limits, restart policies, and health check start periods are asserted in YAML but have never been exercised by Docker Compose on a real host. The first `docker compose up` in production is the actual integration test -- and ACME cert issuance, inter-container networking, resource limit enforcement, and health check timing could all behave differently than the YAML suggests.

## Decisions Needed
- **Schedule a real deployment test?** DE1-DE3 are all "config validated, never executed." A test run on a real host (even Tailscale-internal) would catch deployment-time failures before they matter.
- **Should workers_degraded flag be consumed?** Currently write-only. Should it gate worker-dependent endpoints or appear in /health/ready? Could be scoped into DE4 or a follow-up.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT sanitized, httpOnly cookies, rate limiting, no secret fallbacks |
| Secrets | ok | No hardcoded secrets. Env var injection via Keychain. |
| Domain isolation | ok | No cross-domain imports. Workers on separate Docker networks. |
| Input validation | ok | Pydantic validation on all endpoints. CORS rejects wildcards. |
| Error handling | warn | BE-M5 (MemoryStore.store user_id gap), workers_degraded write-only |

## Security Posture -- Infrastructure
N/A -- mid-wave. Reusing Wave 19 boundary baseline plus DE2/DE3 observations: all containers now hardened (cap_drop ALL, no-new-privileges, resource limits, log rotation). Backup container runs as root (pre-existing). Backup service missing log rotation config.

## Risks You Are Taking
1. **Deployment configs never tested on real infrastructure.** Three phases of deployment work (CI, TLS, hardening) validated by parsing config files. The first real `docker compose up` on a host is the true integration test. Impact: high if deployment fails during a time-sensitive event. Likelihood: moderate.
2. **MemoryStore.store() lacks user_id (BE-M5).** Facts stored via orchestrator are invisible to the user-scoped API. Data-loss-class bug persisted across 10+ phases. Impact: high for memory features. Likelihood: certain once memory features are used.
3. **workers_degraded flag is decorative.** Set at startup but never read. If a worker goes down, no endpoint or health check reflects this to monitoring. Impact: medium (silent degradation). Likelihood: moderate once workers are running independently.
