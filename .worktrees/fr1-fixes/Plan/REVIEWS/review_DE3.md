# QA Review: Phase DE3

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Module docstring references DE3. Individual tests descriptive but lack per-test SPEC section citations. Phase plan lists 10 tests; 18 delivered (8 extra for cap_drop/security_opt). |
| M2 | Negative Tests | PASS | test_probe_worker_returns_false_on_503, test_probe_worker_returns_false_on_connection_error |
| M3 | Security Boundaries | PASS | All 5 service containers have cap_drop ALL + no-new-privileges. Workers have read_only + tmpfs. Caddy correctly adds cap_add NET_BIND_SERVICE. No hardcoded secrets. |
| M4 | Determinism | PASS | No time dependencies, no network calls in tests (httpx mocked), no randomness. |
| M5 | Implementation Completeness | PASS | All 4 deliverables from phase plan delivered. Caddy hardening added beyond original scope (per DE2 QA recommendation). |
| M6 | No Silent Error Swallowing | PASS | `_probe_worker` catches `httpx.TransportError` specifically (not bare except), logs with worker name, returns False. Pre-existing `except Exception: # noqa: BLE001` blocks in app.py are all annotated and log warnings. |
| M7 | Wiring Completeness | PASS | `_probe_worker` called in lifespan() at lines 222-223. `app.state.workers_degraded` set at line 224. |
| M8 | Domain Isolation | PASS | No cross-domain imports. Workers on separate networks. |
| S1 | Error Handling & Boundaries | PASS | _probe_worker handles 5xx, transport errors, and success. 5-second timeout configured. |
| S2 | Code Consistency | PASS | Follows existing naming and style conventions. |
| S3 | Migration & Rollback | N/A | No DB schema changes. |
| S4 | Documentation | PASS | Comments reference spec sections (e.g., "Container hardening (section 8.1, DE3)"). |
| S5 | Integration Smoke Test | OPEN | All tests mock httpx. No non-mocked integration test. However, for infrastructure-config-validation tests (YAML parsing, Dockerfile scanning), mocking is unavoidable -- the "integration" is parsing real files, which the compose fixture does. The _probe_worker tests could be more integration-like but would require a running worker. |

## Test Plan Coverage
No test plan existed for DE3. The phase plan specified 10 tests; 18 were delivered, exceeding the plan.

## Spec Compliance
| Spec Requirement | Status |
|-----------------|--------|
| SPEC section 8.1: Private container hardening (cap_drop, no-new-privileges, read_only, tmpfs) | Implemented + tested |
| SPEC section 8.2: External container hardening | Implemented + tested |
| SPEC section 30: Resource limits (CPU, memory) | Implemented + tested |
| SPEC section 31: Failure handling (restart policy, health checks, degraded mode) | Implemented + tested |
| Caddy hardening (DE2 QA recommendation) | Implemented + tested via smoke test |

## Test Coverage

| Test | Spec/Plan Requirement |
|------|----------------------|
| test_private_worker_cpu_limit | Plan: private-worker cpus 4.0 |
| test_private_worker_memory_limit | Plan: private-worker memory 32G |
| test_private_worker_restart_policy | Plan: restart unless-stopped |
| test_private_worker_healthcheck_start_period | Plan: start_period >= 30s |
| test_external_worker_cpu_limit | Plan: external-worker cpus 2.0 |
| test_external_worker_memory_limit | Plan: external-worker memory 4g |
| test_external_worker_restart_policy | Plan: restart unless-stopped |
| test_external_worker_healthcheck_start_period | Plan: start_period >= 30s |
| test_private_worker_dockerfile_has_healthcheck | Plan: Dockerfile HEALTHCHECK |
| test_external_worker_dockerfile_has_healthcheck | Plan: Dockerfile HEALTHCHECK |
| test_probe_worker_returns_false_on_503 | Plan: degraded on 503 |
| test_probe_worker_returns_false_on_connection_error | Plan: startup proceeds when unreachable |
| test_probe_worker_returns_true_on_200 | Implicit: happy path |
| test_workers_degraded_set_when_external_worker_down | Plan: workers_degraded flag |
| test_private_worker_cap_drop_all | Extra: security hardening |
| test_external_worker_cap_drop_all | Extra: security hardening |
| test_private_worker_no_new_privileges | Extra: security hardening |
| test_external_worker_no_new_privileges | Extra: security hardening |

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- `except:` in src/noa/api/app.py: 0 matches
- `except Exception:` in src/noa/api/app.py: 8 matches, all pre-existing with `# noqa: BLE001`, all log warnings
- New code (_probe_worker) catches `httpx.TransportError` specifically -- clean

**M7: Wiring completeness:**
- _probe_worker called in lifespan() lines 222-223
- app.state.workers_degraded set at line 224

**M8: Domain isolation:**
- `from noa.private_worker` in external_worker/: 0 matches
- `from noa.external_worker` in private_worker/: 0 matches

**Docker security:**
- `USER root` / `privileged` / `--net=host` / `docker.sock` in docker/: 0 matches
- All worker Dockerfiles run as `USER noa`

## Smoke Test Results

```
_probe_worker imported OK: <function _probe_worker at 0x108aa6d40>
private-worker: hardening OK
external-worker: hardening OK
caddy: hardening OK
noa-api: hardening OK
backup: hardening OK
private-worker: resource limits OK (cpus=4.0, memory=32G)
external-worker: resource limits OK (cpus=2.0, memory=4g)
caddy: resource limits OK (cpus=0.5, memory=256m)
noa-api: resource limits OK (cpus=2.0, memory=2g)
backup: resource limits OK (cpus=0.5, memory=512m)
postgres: resource limits OK (cpus=1.0, memory=2g)
private-worker: restart policy OK
external-worker: restart policy OK
private-worker: logging limits OK
external-worker: logging limits OK
caddy: logging limits OK
noa-api: logging limits OK
postgres: logging limits OK
WARNING: backup service missing logging config (not DE3 blocker)

All smoke checks passed!
```

## Security
- All 5 application containers have `cap_drop: ALL` + `security_opt: no-new-privileges:true`
- Workers have `read_only: true` + `tmpfs` for ephemeral writes
- Caddy adds back only `NET_BIND_SERVICE` capability (required for ports 80/443)
- Both worker Dockerfiles use `USER noa` (non-root)
- No hardcoded secrets in Dockerfiles
- No `privileged`, `--net=host`, or `docker.sock` mounts

## Code Quality
- Test file passes ruff with zero violations
- app.py has 1 pre-existing I001 (import sorting) -- not introduced by DE3
- `_probe_worker` function is clean: specific exception handling, 5s timeout, clear logging
- The `healthy = resp.status_code < 500` logic treats 4xx as "healthy" which is reasonable (a 404 means the server is running)

## Beyond the Test Plan

1. **workers_degraded is write-only (anti-pattern HD).** `app.state.workers_degraded` is set at startup but never read by any endpoint, middleware, or health check. The health endpoint at `/health` does not include degraded state. This means the flag is purely for the startup log message. Consider exposing this in `/health/ready` or using it to gate worker-dependent endpoints.

2. **Caddy hardening tests are missing from test_de3_hardening.py.** The tests verify cap_drop/security_opt for private-worker and external-worker but not for caddy, noa-api, or backup -- even though all five have hardening in docker-compose.yml. The smoke test caught this.

3. **backup service missing logging configuration.** All other services have `logging: driver: json-file` with max-size/max-file limits. The backup service does not, meaning its logs could grow without bound.

4. **noa-api Dockerfile missing HEALTHCHECK instruction.** The worker Dockerfiles both have `HEALTHCHECK` instructions, but the noa-api Dockerfile does not (it relies on docker-compose.yml's healthcheck definition). This is inconsistent but not blocking since compose-level healthchecks work.

5. **backup Dockerfile runs as root.** No `USER` directive. Pre-existing, not DE3 scope, but a gap when all other containers run as non-root.

## Notes (PASS_WITH_NOTES)

1. **workers_degraded is set but never consumed** (src/noa/api/app.py:224). Consider reading it in `/health/ready` or as a middleware guard. Currently it only produces a startup log line.

2. **Test coverage gap for Caddy hardening.** Tests verify cap_drop/security_opt only for workers, not for caddy/noa-api/backup. These services were hardened but the tests don't assert it.

3. **backup service missing logging driver config** (docker-compose.yml, backup service block around line 210). All other services have `logging: driver: json-file` with rotation limits.

## Decision Review
No architectural decisions were introduced. The phase executed the plan faithfully and addressed the Caddy hardening recommendation from DE2 QA. The workers_degraded flag pattern should be extended with a consumer in a future phase.
