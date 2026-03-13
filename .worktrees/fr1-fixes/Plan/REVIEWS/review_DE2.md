# QA Review: Phase DE2

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 9/9 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Module docstring cites SPEC.md §29.4, §7.1, §20.1. All 22 tests have docstrings. All 10 planned test areas are covered (22 tests exceeds the ~10 target). |
| M2 | Negative Tests | PASS | `test_cors_never_allows_wildcard` (wildcard rejection), `test_cors_does_not_add_localhost_domain_as_https` (localhost guard), `test_no_hardcoded_domain_in_directives` (hardcoded domain guard). |
| M3 | Security Boundaries | PASS | No hardcoded secrets. CORS rejects wildcard. HSTS enforced. X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers in Caddyfile. noa-api port not host-exposed. Caddyfile mounted read-only. |
| M4 | Determinism | PASS | Tests read static files (Caddyfile, compose YAML, docs). No time, network, or randomness dependencies. |
| M5 | Implementation Completeness | PASS | All 5 deliverables present: Caddyfile, compose update, app.py CORS, TLS_SETUP.md, test file. No TODO/FIXME/HACK. |
| M5b | Findings Currency | PASS | DE2 does not resolve any existing finding. No update needed. |
| M6 | No Silent Error Swallowing | PASS | No exception handling in new code (Caddyfile is declarative; app.py CORS change is inline list manipulation). |
| M7 | Wiring Completeness | PASS | Caddy service in compose depends_on noa-api with service_healthy condition. CORS middleware already wired; DE2 only adds origins to the existing list. |
| M8 | Domain Isolation | PASS | No cross-domain imports. Caddy is infrastructure-only (no Python code). |
| M8b | Cross-Language Optionality | PASS | N/A — no Pydantic models changed. |
| S1 | Error Handling & Boundaries | PASS | Handles localhost edge case, wildcard filtering, empty domain. |
| S2 | Code Consistency | PASS | Naming matches existing conventions. Caddyfile follows Caddy idioms. |
| S3 | Migration & Rollback | PASS | No DB changes. Compose changes are additive (caddy service added, noa-api ports→expose). Removing caddy and restoring ports would revert. |
| S4 | Documentation | PASS | TLS_SETUP.md covers 3 scenarios (public, Tailscale, localhost), troubleshooting, CORS config. |
| S5 | Integration Smoke Test | OPEN | See Note 1 below. CORS tests replicate app.py logic inline instead of testing the real `create_app()` middleware. |

## Test Plan Coverage
No formal test plan existed for DE2 (no `test-plan_DE2.md`). The phase plan specified ~10 tests; 22 were delivered, covering all listed behaviors. Coverage is thorough for static validation.

## Spec Compliance
- **§29.4 (HTTPS over LAN/VPN):** Caddy terminates TLS with HSTS, HTTP→HTTPS 308 redirect. Let's Encrypt for public, internal CA for localhost. PASS.
- **§7.1 (network topology):** noa-api exposed only on internal Docker network (expose, not ports). Caddy bridges to host on 80/443. PASS.
- **§20.1 (Docker network isolation):** Caddy placed on both noa-internal and noa-external. This is necessary so Caddy can (a) reach noa-api on noa-internal and (b) reach ACME servers on noa-external. Acceptable -- Caddy is a trusted proxy component, not a user-facing application. PASS.

## Test Coverage

| Test | Spec Requirement | Category |
|------|-----------------|----------|
| test_reverse_proxy_to_noa_api | §29.4 reverse proxy | Behavioral |
| test_hsts_header_present | §29.4 HSTS | Behavioral |
| test_noa_domain_env_var_placeholder | §29.4 configurability | Behavioral |
| test_http_to_https_redirect | §29.4 HTTP redirect | Behavioral |
| test_no_hardcoded_domain_in_directives | §29.4 no hardcoded secrets | Security |
| test_tls_directive_present | §29.4 TLS | Behavioral |
| test_caddy_service_exists | §7.1 compose | Integration |
| test_caddy_uses_alpine_image | §7.1 image spec | Behavioral |
| test_caddy_binds_port_80/443 | §7.1 port mapping | Behavioral |
| test_caddy_data_volume_mounted/declared | §29.4 cert persistence | Behavioral |
| test_noa_api_does_not_expose_port_to_host | §7.1 internal only | Security |
| test_noa_api_uses_expose_not_ports | §7.1 internal only | Security |
| test_caddy_noa_domain_env_var | §29.4 env config | Behavioral |
| test_cors_accepts_noa_domain_https_origin | §29.4 CORS | Security |
| test_cors_does_not_add_localhost_domain_as_https | §29.4 CORS edge | Negative |
| test_cors_never_allows_wildcard | M2 CORS | Security |
| test_tls_setup_doc_* (4 tests) | §29.4 documentation | Documentation |

**Gap:** No test verifies the caddy service has `restart: unless-stopped` or logging config. Minor.

## Anti-Pattern Scan Results

**M6 — bare except / except Exception:**
- No bare `except:` or `except Exception:` in `tests/unit/test_de2_tls.py`. Clean.
- No new exception handling in the app.py CORS section (lines 333-355 are list operations).

**M7 — wiring:**
- Caddy service in compose: depends_on noa-api with service_healthy. Properly wired.
- CORS origins in app.py: inline in `create_app()`, immediately passed to `CORSMiddleware`. Wired.

**M8 — domain isolation:**
- `grep "from noa.private_worker" src/noa/external_worker/`: No matches.
- `grep "from noa.external_worker" src/noa/private_worker/`: No matches.
- Clean.

## Smoke Test Results

```
$ docker exec noa-dev python -m pytest tests/unit/test_de2_tls.py -x -v
22 passed in 0.08s

$ docker exec noa-dev python -c "<inline CORS + Caddyfile + compose validation>"
CORS origins OK: ['http://localhost:5173', 'https://noa.example.com']
Caddyfile OK
compose OK
DE2 smoke PASSED

$ docker exec noa-dev ruff check tests/unit/test_de2_tls.py
All checks passed!
```

## Security

1. **CORS wildcard rejection:** Verified -- wildcard `*` is stripped from allowed_origins list (app.py line 342-344). Test covers this.
2. **HSTS:** max-age=31536000 with includeSubDomains and preload. Strong.
3. **Security headers in Caddyfile:** X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy: strict-origin-when-cross-origin. Good.
4. **noa-api not host-exposed:** Changed from `ports:` to `expose:`. Verified in compose YAML and tested.
5. **Caddyfile mounted read-only:** `:ro` flag on volume mount. Good.
6. **No secrets in Caddyfile:** Only `{$NOA_DOMAIN}` and `{$NOA_ACME_EMAIL}` env var references. Good.
7. **Caddy on noa-external:** Necessary for ACME. Acceptable -- Caddy is infrastructure, not application code.

**No container hardening on caddy service:** Unlike noa-api (which has `read_only: true`, `cap_drop: ALL`, `security_opt: no-new-privileges`), the caddy service has none of these. This is not blocking for DE2 (which focuses on TLS/proxy), but should be addressed in DE3 (Worker Container Hardening) or a follow-up.

## Code Quality

- Caddyfile is well-structured with clear comments and section separators.
- TLS_SETUP.md is comprehensive (159 lines, 3 scenarios, troubleshooting).
- Test file is organized into logical classes (Caddyfile, DockerCompose, CORS, Documentation).
- app.py CORS change is minimal and clean (4 lines: read env, check, append, filter).

## Beyond the Test Plan

1. **CORS tests replicate logic instead of testing real code (Note 1):** `TestCORSConfig` (lines 203-257) duplicates the CORS origin-building logic from `app.py` instead of importing `create_app()` and inspecting the actual middleware configuration. If the app.py logic changes (e.g., someone adds a different filtering rule), the test would still pass with the old replicated logic. A proper integration test would call `create_app()` with `NOA_DOMAIN` set and inspect `app.middleware_stack` or make a request and check the `Access-Control-Allow-Origin` header. This is S5 (Integration Smoke Test) -- not blocking but notable.

2. **Caddy container lacks hardening:** No `read_only`, `cap_drop`, `security_opt`, or `deploy.resources.limits`. Caddy needs write access to caddy-data and caddy-config volumes for cert storage, so `read_only: true` would require tmpfs or volume exceptions. Resource limits should be added. Not blocking for DE2.

3. **NOA_DOMAIN defaults to `localhost`** in compose (line 25): `NOA_DOMAIN=${NOA_DOMAIN:-localhost}`. This is a safe default for dev, but means forgetting to set it in production gives you a working-but-wrong TLS setup (Caddy internal CA for "localhost" instead of a real cert). The docs cover this clearly, so not blocking.

4. **`caddy-config` volume not tested:** Tests verify `caddy-data` volume is mounted and declared, but not `caddy-config`. Minor gap.

## Notes (PASS_WITH_NOTES)

1. **S5 — CORS tests are logic-replication, not integration tests.** `TestCORSConfig` duplicates the CORS building logic from `app.py` rather than testing the actual `create_app()` CORS middleware. If the real logic diverges from the test's replica, the test provides false confidence. Consider a follow-up test that instantiates the app with `NOA_DOMAIN` set and verifies the middleware actually includes the expected origin. (File: `tests/unit/test_de2_tls.py`, lines 203-257.)

2. **Caddy container lacks hardening.** No `cap_drop`, `security_opt`, or resource limits on the caddy service. This is reasonable scope for DE2 (TLS focus), but should be addressed -- either in DE3 or a dedicated follow-up. (File: `docker-compose.yml`, lines 12-35.)

3. **Missing test for `caddy-config` volume.** Tests verify `caddy-data` but not `caddy-config`. Minor completeness gap. (File: `tests/unit/test_de2_tls.py`.)
