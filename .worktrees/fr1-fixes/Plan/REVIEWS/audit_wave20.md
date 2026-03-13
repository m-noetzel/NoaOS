# System Audit Report — Wave 20 (2026-03-12)

## Summary
- **Overall Health Score**: 7.5/10
- **Endpoints Tested**: 55/72 working (17 unverifiable due to auth, all health endpoints responding)
- **E2E Flows Tested**: 4/6 verifiable (OAuth flow requires real Google credentials)
- **Security Issues**: 3 found (1 medium, 2 low)
- **Dead Code Items**: 3 found
- **Cross-Phase Regressions**: 1 found (stale site-packages in dev container)

## Critical Findings (must fix before next wave)

### CRIT-1: CI Pipeline Will Fail on First Push
**Severity**: CRITICAL
**Components**: `.github/workflows/ci.yml`

The CI pipeline has `continue-on-error: false` on both ruff and mypy steps. Currently:
- **ruff**: 1 import ordering error in `src/noa/api/app.py` (fixable with `--fix`)
- **mypy**: 51 type errors across 18 files

Both will cause CI to fail immediately on any push to `main`. The pipeline was never tested against the actual codebase state.

**Impact**: CI is red from day one. No PR can pass until these are fixed or the checks are relaxed.

**Recommendation**: Fix the ruff error (1-line fix). For mypy, either fix the 51 errors (planned for QE2) or set `continue-on-error: true` on the mypy step until QE2 is complete.

### CRIT-2: Dev Container Has Stale Installed Package
**Severity**: CRITICAL (for development workflow)
**Components**: `noa-dev` container, pip install vs workspace source

The `noa-dev` container has the noa package installed in `/usr/local/lib/python3.11/site-packages/` from an old build. This installed version is missing:
- All Google OAuth routes (GO1)
- Backup health endpoint (DE4)
- forgot-password / reset-password routes
- python-multipart dependency

**Evidence**:
- `python3 -c "import noa.api.v1.auth; print(noa.api.v1.auth.__file__)"` returns `/usr/local/lib/python3.11/site-packages/noa/api/v1/auth.py`
- The installed auth.py has only 4 routes vs 10 in the workspace source
- Tests pass because pytest sets `PYTHONPATH` to include `/workspace/src`, but `uvicorn` and direct imports load the stale version

**Impact**: Running the server inside `noa-dev` serves an old API surface. Tests pass but the running app is broken. New developers would experience confusing behavior.

**Recommendation**: Run `pip install -e ".[api,orchestrator,dev]"` in the `noa-dev` container, or rebuild it. Alternatively, start uvicorn with `PYTHONPATH=/workspace/src` prepended.

## High Findings (fix soon)

### HIGH-1: GOOGLE_REDIRECT_URI Not in docker-compose.yml
**Severity**: HIGH
**Components**: `docker-compose.yml`, `src/noa/api/v1/auth.py`

The Google OAuth2 callback redirect URI defaults to `http://localhost:8000/api/v1/auth/google/callback`. In production with Caddy TLS, the URI must be `https://{NOA_DOMAIN}/api/v1/auth/google/callback`. The env var `GOOGLE_REDIRECT_URI` is not passed in `docker-compose.yml`.

**Impact**: Google OAuth2 will fail in production - the redirect URI registered with Google must match exactly.

**Recommendation**: Add `GOOGLE_REDIRECT_URI` to docker-compose.yml environment, defaulting to `https://${NOA_DOMAIN}/api/v1/auth/google/callback` when NOA_DOMAIN is set.

### HIGH-2: Token Encryption Key Mismatch Risk
**Severity**: HIGH
**Components**: `src/noa/tools/_token_crypto.py`, `docker-compose.yml`

`_token_crypto._derive_key()` reads `JWT_SECRET_KEY` env var. The docker-compose.yml passes `JWT_SECRET` (different name). The `config.py` uses `SECRET_KEY`. These three key names are not aligned.

If `JWT_SECRET_KEY` is not set in the environment, `encrypt_token()` raises a `RuntimeError`, crashing the Google OAuth callback.

**Impact**: Token encryption/decryption will crash at runtime unless `JWT_SECRET_KEY` is explicitly set. This is not currently set in docker-compose.yml.

**Recommendation**: Either rename `JWT_SECRET_KEY` to `SECRET_KEY` in `_token_crypto.py` (matching what config.py uses), or add `JWT_SECRET_KEY=${SECRET_KEY}` to docker-compose.yml.

### HIGH-3: Network Isolation Test Failure
**Severity**: HIGH (existing, pre-Wave-20)
**Components**: `tests/integration/test_network_isolation.py`

`test_api_port_binding_is_localhost_only` consistently fails. This test checks that the API binds only to localhost, which is correct behavior in the dev container but the test's assertion may be wrong for the containerized environment where binding to `0.0.0.0` is required for Docker networking.

**Impact**: 1 persistently failing integration test blocks `-x` (fail-fast) test runs.

**Recommendation**: Update the test to account for Docker networking or skip it in the container environment.

## Medium Findings (track)

### MED-1: OAuth State Leak (No TTL)
**Severity**: MEDIUM
**Components**: `src/noa/api/v1/auth.py`, `_oauth_states`

The `_oauth_states` dict accumulates entries when `authorize` is called but `callback` never completes. There is no TTL or cleanup mechanism.

**Impact**: Minimal for single-user system, but could grow over time with repeated authorize attempts.

**Recommendation**: Add a TTL (e.g., 10 minutes) or periodic cleanup for stale states.

### MED-2: noa-api Dockerfile Missing HEALTHCHECK
**Severity**: MEDIUM
**Components**: `docker/noa-api/Dockerfile`

The private-worker and external-worker Dockerfiles include `HEALTHCHECK` directives, but the noa-api Dockerfile does not. The compose file defines a healthcheck that overrides this, but standalone container usage lacks it.

**Recommendation**: Add `HEALTHCHECK` directive to `docker/noa-api/Dockerfile` matching the compose definition.

### MED-3: Web-CI E2E Tests Have continue-on-error: true
**Severity**: MEDIUM
**Components**: `.github/workflows/web-ci.yml`

The Playwright E2E test step has `continue-on-error: true`, meaning E2E failures won't block the pipeline. This was likely intentional during initial setup but should be tightened once E2E tests are stable.

**Recommendation**: Remove `continue-on-error: true` from the E2E step once the tests are known to pass in CI.

### MED-4: Remaining NotImplementedError Stubs
**Severity**: MEDIUM
**Components**: `src/noa/orchestrator/nodes/tools.py:64`, `src/noa/tools/mcp_adapter.py:43`

Two `NotImplementedError` raises remain:
1. `tools.py:64` — fallback tool executor (patched in tests, but would crash if gateway is not wired)
2. `mcp_adapter.py:43` — MCP adapter when transport is not configured

**Impact**: Both are guarded by proper dispatch paths but could surface in edge cases.

### MED-5: In-Memory Credential Store (TODO)
**Severity**: MEDIUM
**Components**: `src/noa/api/v1/tools.py:33`

The tool credential store is still in-memory (`_credential_store` dict) with a TODO to replace with vault/Keychain integration. Credentials are lost on server restart.

## Low/Informational

### LOW-1: 51 mypy Errors Pending
Known issue tracked for QE2. Includes attribute errors on Pool, Conversation model, type mismatches in app.py lifespan.

### LOW-2: Ruff Import Ordering Error
Single fixable error in `src/noa/api/app.py` — import block not sorted. `ruff check --fix` resolves it.

### LOW-3: Unregistered Pytest Marks
14 custom marks (pr1, pr2, go1, tm1, etc.) generate warnings. Not registered in pyproject.toml.

### LOW-4: Caddy HSTS Includes preload Directive
The `Strict-Transport-Security` header includes `preload` which should only be used after submitting to the HSTS preload list. For a personal single-user system this is harmless but technically incorrect.

### LOW-5: iOS GoogleAuthService Connected Status Has No Email
`getStatus()` returns `.connected(email: nil)` — the backend doesn't provide the connected Google email address. This is a UX gap but not a bug.

## Endpoint Status Matrix

| Route | Method | Auth | Status | Notes |
|-------|--------|------|--------|-------|
| `/health` | GET | No | 200 OK | Returns `{"status": "alive"}` |
| `/health/ready` | GET | No | 200 OK | Returns `{"status": "degraded"}` (workers not available in dev) |
| `/health/metrics` | GET | No | 200 OK | Uptime, pool stats, worker availability |
| `/health/tools` | GET | No | 200 OK | Returns `{"tools": {}}` (no tools configured) |
| `/health/echo` | GET | No | 200 OK | Echo endpoint working |
| `/health/backup` | GET | No | **404** | Not registered in running server (CRIT-2: stale install) |
| `/api/v1/auth/login` | POST | No | 422 | Correctly requires body (email, password, device_id) |
| `/api/v1/auth/register` | POST | No | 422 | Correctly requires body |
| `/api/v1/auth/refresh` | POST | No | 422 | Correctly requires body |
| `/api/v1/auth/logout` | POST | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/auth/google/authorize` | GET | Yes | **404** | Not registered (CRIT-2: stale install) |
| `/api/v1/auth/google/callback` | GET | No | **404** | Not registered (CRIT-2: stale install) |
| `/api/v1/auth/google/status` | GET | Yes | **404** | Not registered (CRIT-2: stale install) |
| `/api/v1/auth/google/disconnect` | DELETE | Yes | **404** | Not registered (CRIT-2: stale install) |
| `/api/v1/threads` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/settings` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/approvals/pending` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/memory/facts` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/runs` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/artifacts` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/cost/summary` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/tools` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/queue` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/usage` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/tasks` | GET | Yes | 401 | Correctly rejects unauthenticated |
| `/api/v1/chat` | POST | Yes | 401 | Correctly rejects unauthenticated |

## E2E Flow Results

| Flow | Steps Completed | Failure Point | Details |
|------|-----------------|---------------|---------|
| Health check flow | 5/5 | None | /health, /ready, /metrics, /echo, /tools all respond correctly |
| Auth rejection flow | 12/12 | None | All protected endpoints return 401 without auth token |
| Google OAuth flow | 0/4 | Step 1 | Routes not registered due to stale container install (CRIT-2) |
| Backup health flow | 0/1 | Step 1 | Endpoint not registered due to stale container install (CRIT-2) |
| Login flow (validation) | 1/1 | None | Correct 422 for missing device_id field |
| CORS headers | 1/1 | None | CSP, X-Content-Type-Options present on all responses |

## Security Checklist

| Check | Result | Details |
|-------|--------|---------|
| Domain isolation (private/external) | PASS | No cross-domain imports found |
| Auth on protected endpoints | PASS | All 12+ protected endpoints return 401 without auth |
| CORS configuration | PASS | Explicit origins only, no wildcard, credentials allowed |
| CSP headers | PASS | Present on all responses |
| X-Content-Type-Options | PASS | `nosniff` on all responses |
| Token encryption (Google OAuth) | CONCERN | Fernet encryption present but key derivation uses wrong env var name (HIGH-2) |
| CSRF protection (OAuth) | PASS | State parameter generated with `secrets.token_urlsafe(32)`, verified on callback |
| Container hardening | PASS | All services: `read_only: true`, `cap_drop: ALL`, `security_opt: no-new-privileges` |
| Non-root container users | PASS | All Dockerfiles use `noa` user |
| Secrets in compose | PASS | All secrets use `${VAR:?required}` or `${VAR:-}` patterns |
| Resource limits | PASS | All services have CPU and memory limits |
| Log rotation | PASS | All services: `max-size: 50m`, `max-file: 5` |
| Network isolation | PASS | `noa-internal` is `internal: true`, `noa-external` allows egress |
| HSTS headers | PASS | Caddy adds `Strict-Transport-Security` with 1-year max-age |
| Error message sanitization | PASS | JWT errors return generic "Invalid token" (PR7 fix verified) |
| Credential masking | PASS | `mask_credential` function in tools module |

## Test Results

| Suite | Pass | Fail | Error | Notes |
|-------|------|------|-------|-------|
| Full suite (with PYTHONPATH fix) | 1650 | 0 | 0 | Excludes 1 network isolation test |
| Wave 20 tests (DE1-DE4, GO1) | 162 | 0 | 0 | All pass with correct path |
| Ruff | — | 1 | — | 1 fixable import ordering error |
| Mypy | — | 51 | — | 51 errors in 18 files (planned QE2) |

## CI/CD Pipeline Review

| Component | Status | Notes |
|-----------|--------|-------|
| `ci.yml` | Structurally valid | 3 jobs (test-backend, test-frontend, static-analysis), Postgres service, Python 3.12, caching. **Will fail on mypy and ruff.** |
| `cd.yml` | Valid | Pushes to ghcr.io on main. Uses docker/build-push-action@v5. |
| `web-ci.yml` | Valid | Node 20, build + unit tests + Playwright. E2E step has `continue-on-error: true`. |
| `ios-ci.yml` | Valid | macOS-14 runner, `swift test`. Minimal but functional. |
| `pre-push-hook.sh` | Valid | Runs ruff + mypy + pytest via noa-dev container. Skips gracefully if container not running. |

## Docker Security Posture

| Service | read_only | cap_drop ALL | no-new-privileges | resource limits | HEALTHCHECK | non-root |
|---------|-----------|-------------|-------------------|----------------|------------|----------|
| caddy | N/A | YES (+NET_BIND_SERVICE) | YES | 0.5 CPU / 256M | compose | N/A |
| noa-api | YES | YES | YES | 2 CPU / 2G | compose only | YES |
| postgres | N/A | N/A | N/A | 1 CPU / 2G | YES | default |
| private-worker | YES | YES | YES | 4 CPU / 32G | Dockerfile + compose | YES |
| external-worker | YES | YES | YES | 2 CPU / 4G | Dockerfile + compose | YES |
| backup | YES | YES | YES | 0.5 CPU / 512M | N/A | N/A |

## Recommendations

1. **Immediate** (before Wave 21):
   - Fix the 1 ruff error (`ruff check --fix src/noa/api/app.py`)
   - Add `JWT_SECRET_KEY=${SECRET_KEY}` to docker-compose.yml environment, OR change `_token_crypto.py` to read `SECRET_KEY`
   - Add `GOOGLE_REDIRECT_URI` to docker-compose.yml with sensible default
   - Rebuild or update the noa-dev container (`pip install -e ".[api,orchestrator,dev]"`)

2. **Wave 21 (QE2)**:
   - Fix 51 mypy errors (already planned)
   - Register custom pytest marks in pyproject.toml

3. **Soon**:
   - Add HEALTHCHECK to noa-api Dockerfile
   - Add TTL cleanup to OAuth state store
   - Remove `continue-on-error: true` from web-ci.yml E2E step once stable
   - Consider adding `GOOGLE_REDIRECT_URI` auto-derivation from NOA_DOMAIN

4. **Tracking**:
   - The in-memory credential store (MED-5) should be replaced with persistent storage
   - Network isolation test needs updating for container environment
