---
name: audit_patterns
description: Recurring audit patterns, fragile endpoints, and common integration issues discovered across system audits
type: project
---

## Audit Environment

- The `noa-dev` container has NO database (connects to localhost:5432 which doesn't exist). Use `noaos-noa-api-1` for all live endpoint testing.
- Source code is bind-mounted (`src` -> `/app/src`) but uvicorn runs WITHOUT `--reload`, so code changes require container restart.
- Auth flow: register (email+password only, no device_id) then login (email+password+device_id) to get token.

## Fragile Endpoints

- `/api/v1/chat` — requires `privacy_mode` (str, not optional). This has been a recurring source of 422s from iOS clients.
- `/api/v1/audit/entries` — requires `trace_id` query parameter, which is non-obvious.
- `/api/v1/devices/push-token` — schema validation issues with the request body.
- PATCH /settings — added in PR2 but only works after container restart.

## Common Integration Failures

- **Container staleness**: Wave code changes on disk not reflected in running uvicorn. Always verify after container restart.
- **httpx cookie persistence**: When testing auth bypass, use a fresh `httpx.Client()` — cookies from prior login requests persist and give false positives.
- **success_envelope type mismatch**: Many endpoints pass `list` to `success_envelope(data=...)` but the signature expects `dict[str, Any]`. Works at runtime but causes 17+ mypy errors.

## Dead Code Hotspots

- `src/noa/tools/mcp_adapter.py` — old stub, superseded by TM6's `mcp_remote.py`
- `src/noa/tools/governance.py` — GovernanceWrapper never imported
- `src/noa/coding/` — entire module never wired
- `src/noa/queue/notifications.py` — empty notify() stub

## Security Checks That Found Real Issues

- JWT error messages leak internal details (library fingerprinting)
- Missing X-Content-Type-Options header
- Credential masking works correctly (pass)
- Domain isolation is clean (pass)
- httpOnly cookies properly configured (pass)
- CSP headers present (pass)
