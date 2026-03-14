# QA Review: System Prompt Transparency Refactor

**Date:** 2026-03-14
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)
**Phase ID:** sp-transparency (targeted fix, not a formal phase)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Tests cite SPEC.md §2.1, §2.2, §7.1; UX-H3 tag used consistently |
| M2 | Negative Tests | PASS | test_put_system_prompt_rejects_too_long_content, test_get_system_prompt_returns_empty_when_file_missing, test_responder_skips_empty_assistant_messages, test_agent_does_not_set_response_when_tool_calls_present |
| M3 | Security Boundaries | PASS | All endpoints authenticated; path is hardcoded (no traversal); length limit on PUT /system-prompt; see Notes for PATCH gap |
| M4 | Determinism | PASS | No wall-clock assertions in new tests; test_fr4_chat_ux.py file-existence tests use real file (deterministic) |
| M5 | Implementation Completeness | PASS | All 7 changed files modified; prompts/system_prompt.txt exists; old references (_build_system_prompt, load_default_system_prompt, _DEFAULT_SYSTEM_PROMPT_FILE, is_default) fully removed from src/ |
| M6 | No Silent Error Swallowing | PASS | read_system_prompt catches OSError and returns "" — appropriate silent fallback for missing file; all runner.py except blocks pre-existing with logging |
| M7 | Wiring Completeness | PASS | settings_router registered in app.py (line 489); GET/PUT /system-prompt endpoints reachable |
| M8 | Domain Isolation | PASS | No cross-domain imports in changed files |
| S1 | Error Handling & Boundaries | PASS | OSError caught in read_system_prompt; 10,000-char limit on PUT; None handled with `or ""` in update path |
| S2 | Code Consistency | PASS | Follows existing naming conventions; L9 exception handling compliance; L10 wiring complete |
| S3 | Migration & Rollback | OPEN | system_prompt DB column still exists in ORM model (models.py:63) and migration 013; service now ignores it — schema drift created without cleanup migration |
| S4 | Documentation | PASS | All public functions have type annotations and docstrings; inline comments explain transparency principle |
| S5 | Integration Smoke Test | OPEN | All 53 tests pass; however TestSystemPromptEndpoints mocks file functions; no non-mocked integration test that actually writes to a tmp file and reads back via the endpoint |

## Spec Compliance

- SPEC.md §2.1 (bounded autonomy, tool allowlists): Runner now correctly separates user prompt from tool availability metadata. Tool context appended; personality NOT hardcoded in runner. PASS.
- SPEC.md §2.2 (agent node): Bug fix `if not tool_calls:` (was `if not tool_calls and content:`) ensures response is always set when agent finishes. PASS.
- SPEC.md §7.1 (responder): Bug fix skips empty-content assistant messages when synthesizing response. PASS.
- UX-H3 (system prompt transparency): File-backed single source of truth implemented. GET /settings, PUT /system-prompt, PATCH /settings, and runner all read from same file. PASS.

## Test Coverage

### New tests (test_orchestrator.py additions)
- `test_agent_sets_response_when_empty_content_no_tools` — regression for the `if not tool_calls` fix. PASS.
- `test_agent_does_not_set_response_when_tool_calls_present` — happy path counterpart. PASS.
- `test_responder_skips_empty_assistant_messages` — regression for empty-content skip. PASS.
- `test_responder_uses_tool_context_when_all_messages_empty` — tool context fallback. PASS.
- `test_responder_empty_response_from_agent_is_accepted` — picks up message history. PASS.
- `TestToolContext` class: 4 tests covering chaining instruction, always-respond instruction, empty-tools case, no personality leak. PASS.

### New tests (test_fr4_chat_ux.py additions)
- `TestSystemPromptFile`: file existence, non-empty content, read_system_prompt() helper. PASS.
- `TestSystemPromptEndpoints`: GET reads file, GET returns empty when missing, PUT writes file, PUT rejects >10k chars, PUT empty content. PASS.

### Coverage gap (non-blocking)
- No test exercises: PATCH /settings with system_prompt field writing to file (goes through `update_settings()`, not the dedicated endpoint).
- No non-mocked integration test that writes a real tmp file and reads it back.

## Anti-Pattern Scan Results

```
# Old method names in src/
grep _build_system_prompt src/ -> No matches
grep load_default_system_prompt src/ -> No matches
grep _DEFAULT_SYSTEM_PROMPT_FILE src/ -> No matches
grep is_default src/ (settings context) -> No matches

# bare except in changed files
grep "except:" src/noa/settings/service.py -> No matches
grep "except:" src/noa/orchestrator/runner.py -> No matches
grep "except Exception:" src/noa/settings/service.py -> No matches

# Domain isolation
grep "from noa.private_worker" src/noa/settings/ -> No matches
grep "from noa.external_worker" src/noa/settings/ -> No matches

# Router wiring
grep "include_router.*settings" src/noa/api/app.py -> line 489: PASS

# ruff check on changed files -> All checks passed!
```

## Smoke Test Results

```
=== Import check ===
OK: settings.service
OK: api.v1.settings
OK: orchestrator.runner
OK: orchestrator.nodes.agent
OK: orchestrator.nodes.responder

=== Functional checks ===
read_system_prompt() length: 313 chars
OK: _build_tool_context with tools
OK: _build_tool_context empty when no tools
OK: no personality in tool context
OK: agent_node sets response='' when empty content + no tools
OK: responder_node skips empty messages
OK: write_system_prompt strip+newline logic correct

pytest: 53 passed, 1 warning in 0.62s

ruff check: All checks passed!
```

## Security

**SAFE:** Path traversal is not possible — `_SYSTEM_PROMPT_FILE` is hardcoded; user content goes INTO the file, not as the path.

**SAFE:** All four endpoints (GET /settings, PATCH /settings, GET /system-prompt, PUT /system-prompt) require authentication via `require_auth`.

**SAFE:** PUT /system-prompt enforces 10,000-character length limit (settings.py:260-264).

**WARN (non-blocking):** PATCH /settings has no length limit on `system_prompt` field. `UpdateSettingsRequest.system_prompt: str | None = None` — no `Field(max_length=...)`. An authenticated user could write a very large file via PATCH. This is a personal single-user agent so the blast radius is self-inflicted, but it's a gap vs. the PUT endpoint.

**NOTE:** `system_prompt.txt` is a global file (not per-user). Correct for single-user deployment; would become a privilege escalation vector in multi-user. Acceptable given current architecture.

**SAFE:** OSError handling in `read_system_prompt` returns "" silently — safe fallback for missing file rather than crashing.

## Code Quality

- Code is clean, well-commented, and follows project conventions.
- `_SYSTEM_PROMPT_FILE` path computation using `Path(__file__).parent.parent.parent.parent` is correct for both dev container (`/workspace/src/...`) and production container (`/app/src/...` with `prompts/` copied alongside).
- `docker/noa-api/Dockerfile:13` correctly includes `COPY prompts/ ./prompts/` — deployment will work.
- `Dockerfile.dev` does NOT copy `prompts/` but uses volume mounts — correct for dev.

**mypy issue (pre-existing, non-blocking):** `agent.py:122` has `arg-type` error for `max_tokens` (object vs int). This is pre-existing from `state.get("max_tokens") or 4096` returning `object`, not newly introduced.

## Deep Dive

**Finding 1 — Schema Drift (S3, non-blocking):**
`UserSettings.system_prompt` column still exists in:
- `src/noa/settings/models.py:63` — ORM model
- `alembic/versions/013_user_settings_chat_defaults.py:20` — migration

The service correctly ignores it (always reads from file), but the column is now dead data. The comment in `service.py` says "there is no DB column for system_prompt" — this is factually incorrect. Any existing user data in this column will be silently superseded by the file. A cleanup migration dropping the column would properly complete the transition, but is not strictly required for correctness.

**Finding 2 — PATCH /settings length bypass (non-blocking):**
The dedicated PUT /system-prompt endpoint enforces a 10,000-char limit (`settings.py:260`). However, the same file can be written through PATCH /settings → `update_settings()` → `write_system_prompt()` with no length check. An authenticated user can bypass the limit by sending `{"system_prompt": "x" * 100_000_000}` via PATCH /settings.

**Finding 3 — Concurrent write non-atomicity (informational):**
`write_system_prompt` uses `Path.write_text()`, which is not atomic. Concurrent requests could produce a partially written file. Risk is negligible for a single-user personal agent.

**Finding 4 — No test for PATCH→file path:**
The PATCH /settings route also writes system_prompt to the file (via `update_settings()`), but no test exercises this code path end-to-end. All system prompt endpoint tests use the dedicated PUT /system-prompt route.

## Blocking Issues
None.

## Notes (PASS_WITH_NOTES)

1. **Schema drift cleanup (low priority):** Add migration 017 to drop `user_settings.system_prompt` column and remove it from `UserSettings` ORM model. The service comment is misleading as written — the column exists in DB but is unused. Not blocking, but creates maintenance confusion.

2. **PATCH /settings system_prompt length limit:** Apply the same 10,000-char constraint to `UpdateSettingsRequest.system_prompt` as the dedicated PUT endpoint enforces. `system_prompt: str | None = Field(default=None, max_length=10_000)` would close the gap.

3. **Add PATCH→file integration test:** A test that sends `PATCH /settings` with `system_prompt` and verifies `read_system_prompt()` returns the new value would complete behavioral coverage for that code path.

## Decision Review

The implementation is correct and clean. The single-source-of-truth design works: file → GET /settings → UI → ChatRequest → runner. The three-place duplication (DB, file, hardcoded) is eliminated. The two bug fixes (agent empty-content response, responder empty-message skip) are correctly implemented and tested.

The most interesting non-obvious issue is the PATCH /settings bypass of the length limit — the two write paths (dedicated endpoint vs. settings PATCH) have inconsistent validation. Since PATCH /settings is the path the UI actually uses for saving chat defaults, this gap is in the hot code path, not a theoretical endpoint.
