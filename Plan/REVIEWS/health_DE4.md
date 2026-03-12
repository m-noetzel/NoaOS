# Project Health Brief -- 2026-03-12 (DE4)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: 3 of 7 phases remain), +0 (last QA PASS_WITH_NOTES, not PASS), +0 (0 critical findings open, but 2 high -- no +1 for zero critical since high still open), -0 (application security: no new warn, pre-existing BE-M5 still open), +0 (infrastructure security N/A mid-wave), +1 (E2E exists: 18 Playwright + integration tests), +0 (no new wave-level milestone). Result: 6, clamped to 6/10. Holding steady from DE3.

## What Happened (since last brief)
1. Backup verification automation complete: verify_backup.sh performs full decrypt-restore-schema-check cycle, writes verify_status.json, with weekly cron (Sundays 03:00 UTC).
2. `GET /health/backup` endpoint added -- exposes backup integrity status (ok/stale/failed/never_run) with backup_age_hours for monitoring.
3. noa-api container now mounts the backups volume read-only, completing the data flow from backup sidecar to API health endpoint.

## Greatest Risk
**The deployment stack has never been tested end-to-end in a real environment.** This is the fourth consecutive deployment phase (DE1-DE4) validated exclusively by static file parsing and unit tests against mocked paths. The verify_backup.sh script has never been executed against a real Postgres instance with real GPG-encrypted backups. Additionally, there is a likely PGPASSWORD gap -- the backup container does not propagate `POSTGRES_PASSWORD` as `PGPASSWORD`, which means the verify script will fail to authenticate on first real execution. This is now the most concrete manifestation of the "config-only tests" risk flagged since DE1.

## Decisions Needed
- **Add PGPASSWORD to backup service environment?** The verify_backup.sh script needs Postgres authentication. Current compose config does not provide it. This is a one-line fix (`PGPASSWORD=${POSTGRES_PASSWORD:?}`) but should be applied before first deployment.
- **Schedule a real deployment test?** Four deployment phases are now complete with zero runtime validation. A `docker compose up` test on a real host would catch the PGPASSWORD gap and any other config-time failures.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT auth on all user-facing endpoints; health endpoints intentionally unauthenticated |
| Secrets | ok | BACKUP_PASSPHRASE via env var (:?), decrypted data on tmpfs, no hardcoded secrets |
| Domain isolation | ok | No cross-domain imports, backups volume is read-only on API container |
| Input validation | ok | Health endpoint reads JSON file, handles corrupt/missing gracefully |
| Error handling | ok | Specific exception types caught (OSError, JSONDecodeError); error details logged |

## Security Posture -- Infrastructure
N/A -- mid-wave (DE4 is phase 4 of 7 in Wave 20). Full audit at wave boundary.

## Risks You Are Taking
1. **PGPASSWORD not propagated (high likelihood, medium impact).** The verify_backup.sh script will fail on first real execution because the backup container's environment does not include `PGPASSWORD`. This will surface as an auth error when the cron job fires on Sunday 03:00 UTC, silently writing "failed" to verify_status.json. Nobody will notice until someone checks `/health/backup`.

2. **Four deployment phases with zero runtime validation (high likelihood, high impact).** CI workflows, TLS proxy, container hardening, and now backup verification have all been validated by parsing YAML/Dockerfile/shell text in Python tests. The first `docker compose up` is the real integration test. ACME certs, inter-container networking, resource limits, GPG decryption, and Postgres auth could all behave differently than the config suggests.

3. **2 high-severity findings still open (low likelihood, medium impact).** BE-H4 (SSE replay cursor) and BE-H5 (raw UPDATE bypasses state machine) are pre-existing and not addressed by Wave 20. They represent real runtime correctness issues that will affect users who experience SSE disconnects or concurrent run status updates.
