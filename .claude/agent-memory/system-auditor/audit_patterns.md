---
name: audit_patterns
description: Recurring audit patterns, fragile endpoints, and cross-phase integration hotspots in Noa project
type: project
---

## Dead-End Store Pattern (Recurring)

The project has a recurring pattern where settings/config fields are stored to DB and served by API but never consumed downstream. This violates the CLAUDE.md "no dead-end stores" rule. Found in:
- Wave 22 FR6: `approvals_enabled`, `max_tool_calls`, `max_retries`, `timeout_seconds` -- stored in settings but orchestrator never reads them
- Earlier: `GovernanceWrapper` (W19-M2), `NotificationService` (W19-M4) retained with tests but not wired

**Detection command:** grep for field names in the consumer directory (e.g., `src/noa/orchestrator/` for settings fields).

## Domain Isolation Gaps

FR1 (Wave 22) added domain isolation via `Conversation.domain` column. Threads and messages correctly filter by `privacy_mode`. However:
- `runs.py` does NOT filter by domain
- `cost.py` does NOT filter by domain
- `artifacts.py` was not checked

**Pattern:** When domain isolation is added, all data endpoints that show user data need the domain filter, not just the primary entity.

## Container Availability

The noa-api container is NOT always running. The dev container (`noa-dev`) is separate from the API container. The API stack requires `docker compose -f docker-compose.yml -f docker-compose.dev-api.yml up` to start. Previous audits (Wave 21) had the container running; this audit (Wave 22) did not.

## Migration Chain

As of Wave 22: 16 migrations (001-016). Chain verified: `down_revision` values are all correct. Key Wave 22 migrations:
- 014: `conversation_domain_column` (FR1)
- 015: `cascade_thread_delete` (FR3, W21-H1 fix)
- 016: `user_settings_governance_limits` (FR6)

## Open Findings Baseline

Wave 22 boundary: 4 open findings, all Low severity (FR3-L1, FR6-L1, L11, L12). Plus 2 new High findings from this audit (W22-H1, W22-H2 -- dead-end stores).

## Previous Audit Scores

- Wave 20: not scored in standard format
- Wave 21: 7.5/10 (2H, 2M open, 2 regressions)
- Wave 22: 7.2/10 (limited by no container; 0 regressions, 2 new High)
