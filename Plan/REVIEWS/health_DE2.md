# Project Health Brief -- 2026-03-12 (DE2)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: 5 of 7 phases remain), +0 (last QA PASS_WITH_NOTES, not PASS), +0 (10 open findings including 2 high -- no critical), -1 (application security warn: BE-M5 MemoryStore.store user_id gap, FE-L1 stack trace in ErrorBoundary -- carried from PR7), +0 (infrastructure security N/A mid-wave), +1 (E2E exists: 18 Playwright + integration tests), +1 (DE2 clean delivery, 22 tests, no blockers). Result: 6, clamped to 6/10. Holding steady at DE1 level.

## What Happened (since last brief)
1. DE2 delivered Caddy reverse proxy with automatic TLS (Let's Encrypt for public, internal CA for dev), HSTS, HTTP-to-HTTPS redirect, and security headers -- all traffic now terminates at Caddy before reaching noa-api.
2. noa-api port 8000 is no longer host-exposed; only reachable via Caddy on ports 80/443 or within the Docker internal network.
3. CORS updated to automatically include `https://{NOA_DOMAIN}` when set, with wildcard rejection. TLS_SETUP.md covers 3 deployment scenarios with troubleshooting.

## Greatest Risk
**The CI pipeline and TLS setup have never been tested in a real deployment environment.** Both DE1 (GitHub Actions workflows) and DE2 (Caddy TLS) are validated by parsing config files locally. The first real `docker compose up` with a DNS-resolvable `NOA_DOMAIN` and the first GitHub Actions run are the actual integration tests. ACME challenges, DNS resolution, cert storage persistence, and container health dependencies could all fail in ways that static YAML/Caddyfile parsing cannot detect. Until someone runs the full stack against a real domain, these are untested deployment artifacts.

## Decisions Needed
- **When to do a real deployment test?** DE1 + DE2 are both "config complete but never executed." A test deployment (even to a Tailscale-internal host) would validate the full TLS chain end-to-end.
- **Should caddy container hardening be added to DE3 scope?** Currently DE3 targets worker containers only. Caddy lacks `cap_drop`, `security_opt`, and resource limits.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT sanitized, httpOnly cookies, rate limiting, no secret fallbacks |
| Secrets | ok | No hardcoded secrets. Caddyfile uses env var placeholders only. |
| Domain isolation | ok | No cross-domain imports. Caddy bridges internal/external networks as infrastructure. |
| Input validation | ok | Pydantic validation on all endpoints. CORS rejects wildcards. |
| Error handling | warn | BE-M5 (MemoryStore.store user_id gap), FE-L1 (stack trace in ErrorBoundary) -- carried from PR7 |

## Security Posture -- Infrastructure
N/A -- mid-wave. Reusing Wave 19 boundary baseline. New observations: Caddy service added without container hardening (no cap_drop, no security_opt, no resource limits). Caddyfile mounted read-only. TLS cert data in named volume. noa-api no longer host-exposed.

## Risks You Are Taking
1. **Deployment configs never tested in real environment.** Both CI workflows (DE1) and TLS proxy (DE2) are validated via static file parsing only. The first real execution is the true test. High impact if it fails during a time-sensitive deployment. Likelihood: moderate (Caddy is well-documented, but compose dependency chains and ACME challenges add failure surface).
2. **Caddy container is unhardened.** No `cap_drop: ALL`, no `security_opt: no-new-privileges`, no resource limits. A compromised Caddy container has full Linux capabilities. Impact: medium (Caddy is a minimal Go binary with small attack surface). Likelihood: low.
3. **MemoryStore.store() still lacks user_id (BE-M5).** Facts stored via orchestrator are invisible to the user-scoped API. This is a data-loss-class bug that has persisted across 8+ phases. Impact: high for any user relying on memory features. Likelihood: certain once memory features are used.
