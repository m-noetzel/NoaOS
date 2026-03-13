# System Auditor Memory

## Environment

- All commands inside Docker: `docker exec noa-dev ...`
- Exception: Playwright E2E tests run on host
- App entrypoint: `from noa.api.app import app`
- Get registered routes: `docker exec noa-dev python -c "from noa.api.app import app; print([r.path for r in app.routes])"`
- **CRITICAL**: noa-dev container has stale site-packages. Always use `PYTHONPATH=/workspace/src` when running code, or reinstall with `pip install -e ".[api,orchestrator,dev]"`. Tests use workspace path via conftest but uvicorn/direct imports may load stale code from site-packages.
- Integration tests need `TEST_DATABASE_URL="postgresql+asyncpg://noa:kindness@postgres:5432/noa_test"` in noa-dev (no Docker socket for testcontainers).

## Historically Fragile Endpoints

- `DELETE /api/v1/threads/{id}` -- **FIXED** as of production readiness audit (2026-03-12): works even with runs. FK cascade issue resolved.
- `POST /api/v1/approvals/{id}/decide` -- was IDOR (no user_id filter), stub for multiple waves, hardcoded risk_tier. Fixed in iOS11 but remains a regression risk.
- `GET /api/v1/runs` -- was stub returning empty list for many waves (MV3 fixed)
- `/api/v1/voice/upload` -- chat mode was stub (iOS2 partially fixed)
- `GET /api/v1/auth/google/*` -- Wave 20 addition (GO1). Routes register in code but need container restart to appear in running server (no --reload).
- `GET /health/backup` -- Wave 20 addition (DE4). Same stale-container issue.

## Common Integration Failure Patterns

### 1. AuthUser refactor orphans
When `require_auth` return type changed from `dict` to `AuthUser` dataclass, endpoints using `payload["sub"]` crashed. Always check ALL callers after shared dependency type changes.

### 2. Push notification pipeline
APNsService._http_client initialization, device token lookup, and actual send() calls have been incomplete across multiple waves. Verify the ENTIRE chain from trigger to external API call.

### 3. ruff gate violations
System-final audit found 6 violations (BLE001, F401, E501). Wave 20 audit found 1 import ordering error. Wave 21: CLEAN (0 errors). Always run `ruff check src/` as part of audit.

### 4. Stale container (no --reload)
The noa-api container runs uvicorn with `--factory` but no `--reload`. Code changes require container restart. This causes routes added in recent waves to return 404. Always restart before testing new routes.

### 5. Env var name mismatches
Token encryption uses `JWT_SECRET_KEY`, docker-compose passes `JWT_SECRET`, config.py uses `SECRET_KEY`. Always verify env var names across all consumers.

### 6. FK cascade gaps in DB models
usage_stats.run_id FK to runs lacks ondelete clause. Thread deletion cascades to runs but fails on usage_stats. Always check FK cascade chains when testing delete operations.

## Security Checks That Catch Real Issues

1. CORS: `allow_origins` must not be `*`, especially with `allow_credentials=True`
2. Auth: every endpoint with user-specific data must filter by `user_id`
3. Domain isolation: `grep -rn "from noa.private_worker" src/noa/external_worker/` and vice versa
4. Secrets: no `or ""` / `or "dev"` fallbacks on security-sensitive config
5. Token storage: httpOnly cookies only, not localStorage
6. Rate limiting: per-user, not just per-action
7. Token encryption key derivation: verify env var name matches what compose/production sets
8. OAuth redirect URI: must match between Google console, backend env, and compose config
9. /docs exposure: should be gated by environment (currently unconditional)

## Dead Code Hotspots

- `GovernanceWrapper` in tools -- unused after per-user rate limiting in ToolGateway
- `_RateLimit` dataclass in gateway.py -- left after inline reimplementation
- `mcp_adapter.py` still has NotImplementedError (superseded by TM6 mcp_remote.py but retained for tests)
- `tools.py:64` fallback tool executor -- NotImplementedError if gateway not wired

## Audit Report Format

- Write to `Plan/REVIEWS/audit_{date}.md` or `audit_wave{N}.md`
- Update `Plan/FINDINGS.md` for any new Critical/High findings
- Score rubric in qa-review agent definition (start at 5, adjust per conditions)

## Previous Audit Scores

- System-final (2026-03-10): 4/10 -> FAIL (architectural)
- System-final recheck (2026-03-10): 5/10 -> FAIL (ruff gate), then 7/10 -> PASS_WITH_NOTES
- Wave 19 (2026-03-11): 7.5/10
- Wave 20 (2026-03-12): 7.5/10 (CI pipeline would fail on push; stale dev container; Google OAuth env var gaps)
- Wave 21 (2026-03-12): 7.5/10 (ruff+mypy clean; DELETE threads FK bug; backup container crash-loop)
- Production readiness (2026-03-12): 6.5/10 (code quality excellent; deployment NOT ready: no LLM keys, ProviderRouter doesn't load user keys, in-memory credential store, no TLS, no backups)

## Production Readiness Blockers (2026-03-12)

1. **CRIT**: Chat pipeline always errors -- ProviderRouter initialized at startup with no keys, never rebuilt per-request with user settings
2. **CRIT**: Tool credential store is in-memory dict (`_credential_store` in tools.py:34) -- lost on restart
3. **CRIT**: No LLM API keys in environment (OPENAI_API_KEY, ANTHROPIC_API_KEY both unset)
4. **HIGH**: forgot-password returns reset_token directly in response body
5. **HIGH**: /docs accessible (ENVIRONMENT env var not set)
6. **MED**: Integration tests broken (DB password mismatch with TEST_DATABASE_URL)
7. **MED**: Backup has never run
8. **MED**: Caddy not deployed (no TLS)

## CI Pipeline Status (Wave 21)

- ruff: CLEAN (0 errors) -- first time ever
- mypy: CLEAN (0 errors, 166 files) -- QE2 achievement
- `ci.yml` has `continue-on-error: false` on both ruff and mypy steps -- CI would pass now
- `web-ci.yml` E2E step has `continue-on-error: true` (soft gate)
- pytest-cov configured: 84% baseline, 70% threshold
- mutmut configured for auth/router/gateway modules
