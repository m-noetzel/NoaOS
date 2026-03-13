# QA Review: Phase PR4

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Test docstring cites SPEC.md S11.1, S13.2, S22.1. All 4 deliverables (BE-H1, BE-M2, BE-M3, BE-M4) have corresponding test classes. |
| M2 | Negative Tests | PASS | 5 path traversal rejection tests (dotdot, relative escape, absolute escape, encoded dotdot, endpoint-level guard). Empty updates no-op test. Provider import failure tolerance test. |
| M3 | Security Boundaries | PASS | Path traversal guard rejects ".." and paths outside _ARTIFACTS_BASE. Runner error events send generic message to client (no str(exc) leak). Artifact download requires auth + user_id join. No hardcoded secrets. |
| M4 | Determinism | PASS | No wall-clock time in assertions. No network calls. No unseeded randomness. UUIDs generated per-test. |
| M5 | Implementation Completeness | PASS | All 4 deliverables implemented: BE-H1 (_reload_llm_pipeline_if_needed with full_settings), BE-M3 (_validate_artifact_path), BE-M2 (public persist()), BE-M4 (structured log_ctx in runner.py and chat.py). Default model change to "openai/gpt-4.1-mini" applied consistently in router.py, agent.py, test_mr8. |
| M6 | No Silent Error Swallowing | PASS | All `except Exception:` blocks have `noqa: BLE001` and log at warning or debug level. Line 106 (agent router reload) logs at DEBUG -- acceptable since it's best-effort. Line 113 (provider router reload) logs at WARNING with exc_info. |
| M7 | Wiring Completeness | PASS | _reload_llm_pipeline_if_needed called from both PUT and PATCH settings endpoints (lines 150, 171). _validate_artifact_path called in download_artifact endpoint (line 124). persist() used in memory.py update_fact (line 91). No new routers or services to wire. |
| M8 | Domain Isolation | PASS | No cross-domain imports. `from noa.private_worker` not found in `noa.external_worker` or vice versa. |
| S1 | Error Handling & Boundaries | PASS | Boundary tests: empty updates dict, absolute path outside base, relative dotdot escape. HTTPException detail is generic "Invalid artifact path" (no info leak). |
| S2 | Code Consistency | PASS | Follows existing patterns: `success_envelope`, `trace_id_ctx.get("")`, `logger = logging.getLogger(__name__)`. _DynSettings follows the same class-attribute pattern as ProviderRouter.from_settings expects. |
| S3 | Migration & Rollback | PASS | N/A -- no DB schema changes in this phase. |
| S4 | Documentation | PASS | _reload_llm_pipeline_if_needed has a comprehensive docstring explaining the full_settings rationale. _validate_artifact_path documents the traversal check. |
| S5 | Integration Smoke Test | OPEN | MemoryStore tests (test_persist_writes_to_disk, test_update_status_persists) use real MemoryStore with tmp_path -- these are real integration tests. Path traversal tests call real _validate_artifact_path. However, the credential reload tests are fully mocked -- no test calls the real PUT/PATCH endpoint through ASGI TestClient. |

## Test Plan Coverage
No formal test plan existed for PR4. The 24 tests cover all 4 deliverables thoroughly.

## Spec Compliance

| Requirement | Status | Detail |
|-------------|--------|--------|
| BE-H1: Credential persistence + router reload | Implemented | _reload_llm_pipeline_if_needed rebuilds ProviderRouter from full_settings dict. Called from both PUT and PATCH. Agent router also updated. Partial-update preservation verified by test. |
| BE-M3: Path traversal guard | Implemented | _validate_artifact_path checks for ".." and Path.relative_to(_ARTIFACTS_BASE). 5 test vectors cover dotdot, relative, absolute, encoded, and endpoint-level. |
| BE-M2: MemoryStore public persist() | Verified | persist() is public (line 199). _persist() remains internal. memory.py uses store.persist() not store._persist(). Codebase-wide scan confirms no external ._persist() calls. |
| BE-M4: Structured log context | Implemented | runner.py: log_ctx dict with run_id/user_id/trace_id passed as `extra=` to all logger calls. chat.py: log_ctx with trace_id/user_id at request entry. Both pass user_id/trace_id to runner.run(). |

## Test Coverage

| Test Class | Count | Spec Ref | Category |
|-----------|-------|----------|----------|
| TestArtifactPathTraversalGuard | 6 | BE-M3 | 5 negative + 1 positive |
| TestCredentialPersistenceAndRouterReload | 8 | BE-H1 | 5 behavioral + 1 integration + 1 error tolerance + 1 partial-update |
| TestMemoryStorePublicInterface | 6 | BE-M2 | 3 behavioral + 2 integration + 1 codebase scan |
| TestStructuredLogContext | 4 | BE-M4 | 3 behavioral + 1 signature |
| **Total** | **24** | | |

## Anti-Pattern Scan Results

**M6 - Bare except / blind exception:**
- `src/noa/api/v1/settings.py:106` -- `except Exception: # noqa: BLE001` -- logs at DEBUG (agent router reload, best-effort). Acceptable.
- `src/noa/api/v1/settings.py:113` -- `except Exception: # noqa: BLE001` -- logs at WARNING with exc_info (provider router reload). Acceptable.
- `src/noa/orchestrator/runner.py:90,207,239,271` -- All log at WARNING. Pre-existing patterns for best-effort status updates and event persistence. Acceptable.

**M7 - Wiring:**
- _reload_llm_pipeline_if_needed wired at lines 150 (PUT) and 171 (PATCH).
- _validate_artifact_path wired at line 124 in download_artifact.
- persist() wired in memory.py line 91.

**M8 - Domain isolation:**
- `grep 'from noa.private_worker' src/noa/external_worker/` -- no matches.
- `grep 'from noa.external_worker' src/noa/private_worker/` -- no matches.

## Smoke Test Results

```
1. _validate_artifact_path imported OK, base=/data/artifacts
2. _reload_llm_pipeline_if_needed imported OK, fields=frozenset({'ollama_base_url', 'anthropic_api_key', 'openai_api_key'})
3. MemoryStore persist() is public OK
4. OrchestratorRunner.run() has user_id,trace_id params OK
5. Path traversal guard works: HTTPException 400
6. memory.py uses public persist() API OK
7. Runner error event is generic (no exc leak) OK

All smoke tests PASSED
```

All 24 tests pass:
```
======================== 24 passed, 1 warning in 0.28s =========================
```

## Security

1. **Path traversal guard (BE-M3):** Solid implementation. Two-layer defense: (a) fast pre-check for ".." substring, (b) Path.resolve().relative_to(_ARTIFACTS_BASE) for canonicalized containment check. Logs traversal attempts at WARNING level without revealing internal paths to the client.

2. **Error event sanitization (runner.py):** Fixed -- error events now send "An error occurred processing your request." instead of `str(exc)`. Server-side log retains the full error.

3. **Pre-existing concern (chat.py:157-162):** The outer exception handler in chat.py `event_stream()` still sends `str(exc)` to the client via SSE. This is pre-existing (CP3-era) and not in PR4 scope, but should be addressed in a future phase. Not blocking.

4. **Credential handling:** _DynSettings reads from full_settings dict with env-var fallback. No secrets logged. No hardcoded API keys.

## Code Quality

1. **_DynSettings pattern:** Clean -- uses class attributes evaluated at class definition time from the `full_settings` closure. This avoids the partial-update credential loss that was the original bug.

2. **Test quality:** Good variety -- behavioral, negative, integration (real MemoryStore), codebase scan (no external ._persist calls), and error tolerance tests.

3. **Ruff violation:** `tests/unit/test_pr4_security_robustness.py:290` -- E501 (line too long, 91 > 88 chars in docstring). Minor.

## Beyond the Test Plan

1. **chat.py str(exc) leak to client:** Pre-existing. Runner.py was fixed to send generic messages, but the outer SSE handler in chat.py still leaks raw exception text. Should be logged as a new finding.

2. **_DynSettings google_ai_api_key only from env:** `google_ai_api_key` at line 88 is only read from `os.environ.get("GOOGLE_AI_API_KEY")`, not from `full_settings`. This is consistent because `UpdateSettingsRequest` has no `google_ai_api_key` field, but if one is added in the future, this would need updating. Not blocking.

3. **_ARTIFACTS_BASE resolved at module load:** If `ARTIFACTS_DIR` env var changes after import, the base won't update. This is fine for a container environment (env set at startup).

4. **No symlink check in _validate_artifact_path:** The `Path.resolve()` call follows symlinks. If an attacker could create a symlink inside _ARTIFACTS_BASE pointing outside, the check would pass. In practice this requires write access to the artifacts directory, which is a higher privilege than the attack this guards against. Not blocking.

## Notes (PASS_WITH_NOTES)

1. **FINDINGS.md not updated.** BE-H1, BE-M3, BE-M4 should be marked Resolved by PR4. BE-M2 was already marked Resolved by PR1 (PR4 only verified it). This is the fourth consecutive review flagging stale FINDINGS.md.

2. **Ruff E501 in test file.** `tests/unit/test_pr4_security_robustness.py:290` -- docstring 3 chars over limit. Trivial fix.

3. **chat.py str(exc) SSE leak.** Pre-existing (CP3-era). Runner.py was fixed to send generic error messages, but `chat.py:157-162` still sends `str(exc)`. Recommend adding this as a new finding for PR5 or PR6 scope.

4. **No ASGI TestClient integration test.** All credential reload tests use mocks. A single test calling PUT /settings through TestClient and verifying the ProviderRouter was rebuilt would increase confidence. Not blocking since the unit tests are thorough.

## Decision Review

PR4 delivers solid security improvements. The path traversal guard is well-implemented with dual-layer defense. The credential reload fix correctly uses full_settings to prevent partial updates from dropping credentials. The structured logging context provides the observability foundation needed for production debugging. The MemoryStore public interface is clean and verified by codebase scan.

The main gap is process hygiene -- FINDINGS.md remains stale across four consecutive reviews. This is a project-level issue, not a code quality issue.
