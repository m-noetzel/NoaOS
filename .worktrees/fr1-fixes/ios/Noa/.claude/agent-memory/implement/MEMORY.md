# Implement Agent Memory

## Key Patterns

### Lazy imports inside functions — patch at source module
When a function does `from noa.some.module import MyClass` inside its body, patch at
`noa.some.module.MyClass`, not at the caller module. The caller module never holds the name.

### asyncio in sync tests
Use `asyncio.run()` (not `get_event_loop().run_until_complete()`) in sync test methods.
`get_event_loop()` fails when the previous event loop was closed by pytest-asyncio.

### Module-level mutable state in tests
When tests modify module-level variables (e.g., `artifacts_mod._ARTIFACTS_BASE`), always
restore via `try/finally` to avoid polluting subsequent tests in the full suite.

### Path traversal guard pattern
Reject paths with `..` as a fast pre-check, then use `path.resolve().relative_to(base)`
and raise `HTTPException(400)` from the `ValueError`. Use `from exc` to satisfy B904.

### ProviderRouter reload after credential update
`_reload_llm_pipeline_if_needed()` in settings.py rebuilds ProviderRouter when LLM credential
fields (anthropic_api_key, openai_api_key, ollama_base_url) are updated. Uses lazy imports
inside a try/except so failures are best-effort (logged, not raised).

### Pre-existing test failure: test_lifespan_db_skip_emits_warning
`tests/unit/test_qc3_error_handling.py::TestExceptionHandlingQuality::test_lifespan_db_skip_emits_warning`
fails when run in the full suite because `_app` is already set by the time the test runs
(so `create_app()` never fires, the patch never intercepts anything). Passes when run in
isolation. Pre-existing flaky test — not introduced by any wave 19/20 changes.

### ruff per-file-ignores for tests/
`pyproject.toml` has `[tool.ruff.lint.per-file-ignores]` for `tests/**/*.py` suppressing:
E501, N806, S105, S106, F841, BLE001. This is intentional — tests use patterns that
would trip these rules (hardcoded passwords, blind except in error-path assertions, etc).

## Project State

- Wave 20 COMPLETE (DE1-DE3, DE4, GO1, GO2, GO3, Wave20-cleanup)
- Pre-Wave-21 cleanup complete: 12 findings resolved (W20-C1/H1/H2/M1/M2, BE-H4/H5/M1/M5, FE-L1/M5, iOS-L1)
- 29 CI proposals applied (CI-001 to CI-033)
- FINDINGS: 3 open (iOS-L2, W20-MED-3 workers_degraded, W20-MED-4 _get_live_google_client), 109 resolved
- ruff gate expanded to tests/ (CI-030); per-file-ignores added for test-specific patterns
- Pre-existing test failures (not introduced by implement):
  - test_qc3_error_handling.py::test_lifespan_db_skip_emits_warning (flaky — app singleton already set)
  - test_mr8_model_routing.py::test_router_returns_model_config_external (model name mismatch)
