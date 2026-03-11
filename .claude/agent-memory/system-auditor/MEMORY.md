# System Auditor Memory

## Environment

- All commands inside Docker: `docker exec noa-dev ...`
- Exception: Playwright E2E tests run on host
- App entrypoint: `from noa.api.app import app`
- Get registered routes: `docker exec noa-dev python -c "from noa.api.app import app; print([r.path for r in app.routes])"`

## Historically Fragile Endpoints

- `POST /api/v1/approvals/{id}/decide` — was IDOR (no user_id filter), stub for multiple waves, hardcoded risk_tier. Fixed in iOS11 but remains a regression risk.
- `GET /api/v1/runs` — was stub returning empty list for many waves (MV3 fixed)
- `DELETE /api/v1/threads/{id}` — was stub (MV1 fixed)
- `/api/v1/voice/upload` — chat mode was stub (iOS2 partially fixed)

## Common Integration Failure Patterns

### 1. AuthUser refactor orphans
When `require_auth` return type changed from `dict` to `AuthUser` dataclass, endpoints using `payload["sub"]` crashed. Always check ALL callers after shared dependency type changes.

### 2. Push notification pipeline
APNsService._http_client initialization, device token lookup, and actual send() calls have been incomplete across multiple waves. Verify the ENTIRE chain from trigger to external API call.

### 3. ruff gate violations
System-final audit found 6 violations (BLE001, F401, E501). These fail merge gates. Always run `ruff check src/` as part of audit.

## Security Checks That Catch Real Issues

1. CORS: `allow_origins` must not be `*`, especially with `allow_credentials=True`
2. Auth: every endpoint with user-specific data must filter by `user_id`
3. Domain isolation: `grep -rn "from noa.private_worker" src/noa/external_worker/` and vice versa
4. Secrets: no `or ""` / `or "dev"` fallbacks on security-sensitive config
5. Token storage: httpOnly cookies only, not localStorage
6. Rate limiting: per-user, not just per-action

## Dead Code Hotspots

- `GovernanceWrapper` in tools — unused after per-user rate limiting in ToolGateway
- `_RateLimit` dataclass in gateway.py — left after inline reimplementation
- Check for `NotImplementedError` raises (stub pattern) — MV5 AST detector covers this

## Audit Report Format

- Write to `Plan/REVIEWS/audit_{date}.md`
- Update `Plan/FINDINGS.md` for any new Critical/High findings
- Score rubric in qa-review agent definition (start at 5, adjust per conditions)

## Previous Audit Scores

- System-final (2026-03-10): 4/10 → FAIL (architectural)
- System-final recheck (2026-03-10): 5/10 → FAIL (ruff gate), then 7/10 → PASS_WITH_NOTES
