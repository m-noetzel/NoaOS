---
name: audit_patterns
description: Recurring audit patterns, fragile endpoints, dead code hotspots, and test isolation issues discovered across Wave 19-23 audits
type: project
---

## Test Isolation (Persistent Pattern -- Wave 23)

- Module-level state in `src/noa/api/app_state.py` (global variables for router, gateway, runner, etc.) causes test pollution. Tests that call `set_router()`, `set_gateway()` etc. contaminate subsequent test files.
- `reset_all()` exists but is not called automatically between test files. ~29 tests pass in isolation but fail in the full suite.
- **How to apply:** When auditing test failures, always re-run failing tests in isolation before classifying as a real failure. Count "persistent" (fails alone) vs "order-dependent" (passes alone) separately.

## Dead Code Hotspots (Updated Wave 23)

- Wave 23 CQ2 fully resolved the governance stack (governance.py, idempotency.py, rate_limiter.py, mcp_adapter.py).
- `external_worker/tools/__init__.py` has its own `ToolRegistry` class (different from the deleted one) -- do not flag as dead code.
- `policy/approval.py` `ApprovalService` is used for expiry processing, NOT approval creation. The main creation path is `chat.py:_create_approval()`.

## Fragile Endpoints & Tests

- `/api/v1/chat` -- requires `privacy_mode` (str, not optional). Recurring 422s from iOS.
- Runner event sequence tests (`test_cp2_runner.py`, `test_fr4_chat_ux.py`) break whenever orchestrator event flow changes.
- Model default tests (`test_mr8_model_routing.py`) break when config constants change.
- Route count tests (`test_new_endpoints.py`) break when any route is added/removed.

## Security Baselines

- Domain isolation: `grep -rn "from noa.private_worker" src/noa/external_worker/` and vice versa. Clean since QC4.
- Credential masking: `mask_credential()` in `tools/health.py`. Used in `tools.py` response paths.
- No bare `except:` in src/noa/ -- all narrowed to `except Exception` with noqa:BLE001.
- JWT error messages sanitized (PR7). X-Content-Type-Options nosniff (PR7). httpOnly cookies (QC2). CSP headers (QC2).

## Container Availability

- Docker has never been available during audits (Waves 21-23 all static analysis only).
- Score 0.5 (not 0) for dimensions requiring live testing. Max achievable without Docker is ~8.5/10.
- TypeScript verifiable via `npx tsc --noEmit` even when rollup build fails (platform binary issue).

## Audit Environment

- Auth flow: register (email+password only, no device_id) then login (email+password+device_id) to get token.
- If containers available: use `noaos-noa-api-1` (not `noa-dev`). Source bind-mounted but uvicorn runs without --reload.
