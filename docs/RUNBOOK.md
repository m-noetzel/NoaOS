# Noa Operational Runbook

Reference: SPEC.md sections 10.5, 28, 30, 31.

---

## 1. Pre-Flight Checklist

Run automated checks before first deployment:

```bash
python scripts/preflight.py
```

### Required Environment Variables

| Variable | Purpose | Where to set |
|----------|---------|-------------|
| `DATABASE_URL` | Postgres connection string | `.env.secrets` or compose env |
| `JWT_SECRET` | Auth token signing | `.env.secrets` |
| `BACKUP_PASSPHRASE` | GPG symmetric key for backups | `.env.secrets` |
| `SECRET_KEY` | FastAPI secret key | `.env.secrets` |
| `POSTGRES_PASSWORD` | Postgres user password | `.env.secrets` |

### Optional Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | External LLM (Anthropic) |
| `OPENAI_API_KEY` | External LLM (OpenAI) |
| `GOOGLE_AI_API_KEY` | External LLM (Google) |

### Docker Requirements

- Docker Engine 24+
- Docker Compose v2 (`docker compose version` must succeed)
- Sufficient resources: 9.5 CPU cores, ~40 GB RAM total across containers

### Volume Verification

Compose creates these automatically on first `up`:
- `postgres-data` -- Postgres database files
- `private-data` -- Private worker encrypted data
- `backups` -- Encrypted backup files
- `coding-workspace` -- External worker scratch space

### Network Isolation Verification

```bash
./scripts/verify_isolation.sh
```

This confirms the private-worker container has no internet egress (IPv4, IPv6, DNS).

---

## 2. Starting Noa

```bash
# Start all services (detached)
docker compose up -d

# Verify all containers are healthy
docker compose ps

# Check API liveness (returns 200 when process is running)
curl -f http://localhost:8000/health

# Check readiness (returns 200 when DB + workers are connected)
curl -f http://localhost:8000/health/ready
```

**Startup order** (handled by `depends_on` with `service_healthy`):
1. postgres (healthy when `pg_isready` succeeds)
2. private-worker + external-worker (healthy when `/health` returns 200)
3. noa-api (waits for all three above)
4. backup (waits for postgres)

---

## 3. Daily Operations

### Health Monitoring

```bash
# Aggregate metrics (pool stats, uptime, worker availability)
curl http://localhost:8000/health/metrics

# Tool-specific health (error rates, latency)
curl http://localhost:8000/health/tools
```

### Log Review

```bash
# All services, last 24h
docker compose logs --since 24h

# Specific service
docker compose logs noa-api --since 1h
docker compose logs backup --since 24h
```

Logs use `json-file` driver, capped at 50 MB x 5 files per container. No manual rotation needed.

### Scheduled Tasks (automatic)

| Time | Task | Reference |
|------|------|-----------|
| Daily 02:00 | Postgres backup (`scripts/backup.sh`) | SPEC 10.5 |
| Daily 02:30 | Private data backup (`scripts/backup_private.sh`) | SPEC 10.5 |
| Sunday 03:00 | Automated restore test | SPEC 10.5 |
| Daily | `VACUUM ANALYZE` via DbMaintenanceScheduler | SPEC 30 |
| Daily | 90-day audit log purge via RetentionScheduler | SPEC 28 |

---

## 4. Backup & Restore

### Backup Schedule

Backups run automatically via the `backup` container's cron. Each backup is:
- `pg_dump` -> gzip -> GPG AES-256 symmetric encryption
- Rotation keeps last 7 backups

### Manual Backup

```bash
docker compose exec backup /scripts/backup.sh
```

### Restore Procedure

```bash
# 1. Stop the API to prevent writes
docker compose stop noa-api

# 2. List available backups
docker compose exec backup ls -lt /backups/

# 3. Restore from a specific backup
docker compose exec backup /scripts/restore.sh /backups/noa_2026-03-06_0200.sql.gz.gpg

# 4. Restart services
docker compose start noa-api
```

### Backup Verification

Check the latest backup exists and is non-empty:

```bash
docker compose exec backup ls -lh /backups/ | head -5
```

The Sunday 03:00 restore test automatically validates backup integrity.

---

## 5. Failure Recovery

### 5.1 Private Worker Down

**Symptom:** `/health/metrics` shows private worker availability drop; requests to private LLM fail.

```bash
# Check logs
docker compose logs private-worker --tail 50

# Restart
docker compose restart private-worker

# If persistent: verify Ollama model is loaded
docker compose exec private-worker ollama list
```

Check resource limits -- the private-worker needs 4 CPU / 32 GB RAM.

### 5.2 Database Failure

**Symptom:** `/health/ready` returns degraded; API returns 500s on data operations.

```bash
# Check postgres logs
docker compose logs postgres --tail 50

# Restart
docker compose restart postgres

# If data corruption: restore from backup (Section 4)
```

### 5.3 External Worker Errors

**Symptom:** Tool calls to external APIs failing; `/health/tools` shows high error rates.

```bash
# Check logs for API errors
docker compose logs external-worker --tail 50

# Verify API keys are set
docker compose exec external-worker env | grep -E 'API_KEY'

# Restart
docker compose restart external-worker
```

Common causes: expired API keys, rate limits, external service outages.

### 5.4 Disk Space

```bash
# Docker disk usage
docker system df

# Detailed breakdown
docker system df -v

# Clean unused images/containers (preserves volumes)
docker system prune -f

# WARNING: never run 'docker volume prune' -- it removes data volumes
```

Backup rotation keeps only the last 7 files automatically.

### 5.5 Connection Pool Exhaustion

**Symptom:** Slow or timed-out API responses; `/health/metrics` shows `pool_checkedout` near 30.

Pool settings: `pool_size=10`, `max_overflow=20`, `pool_recycle=1800s`.

```bash
# Check current pool stats
curl http://localhost:8000/health/metrics | python -m json.tool

# If consistently near max: restart to reset stale connections
docker compose restart noa-api
```

If recurring, consider increasing `pool_size` in configuration.

---

## 6. Capacity Planning

### Resource Allocation

| Container | CPU | RAM | Notes |
|-----------|-----|-----|-------|
| noa-api | 2 | 2 GB | FastAPI + connection pool |
| postgres | 1 | 2 GB | PostgreSQL 16 |
| private-worker | 4 | 32 GB | Ollama LLM inference |
| external-worker | 2 | 4 GB | External API calls |
| backup | 0.5 | 512 MB | pg_dump + GPG |
| **Total** | **9.5** | **40.5 GB** | |

### Signs of Overload

- `pool_checkedout` consistently above 25 (of 30 max)
- Private worker response times > 30s
- Backup jobs taking > 30 minutes
- Container OOM kills in `docker compose logs`

### Scaling Notes

Phase 1 runs on a single machine. If resource limits are hit:
1. Increase container resource limits in `docker-compose.yml`
2. Add swap space as emergency buffer (not for sustained use)
3. Phase 2 design supports physical machine isolation for private-worker

---

## 7. Security Checklist

Run periodically (weekly recommended):

```bash
# 1. Verify network isolation
./scripts/verify_isolation.sh

# 2. Verify containers are read-only with no capabilities
docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' $(docker compose ps -q) | grep -v true && echo "FAIL: not all read-only"

# 3. Verify no-new-privileges
docker inspect --format '{{.HostConfig.SecurityOpt}}' $(docker compose ps -q)
```

### Checklist

- [ ] Network isolation passes (`verify_isolation.sh`)
- [ ] All containers `read_only: true` and `cap_drop: ALL`
- [ ] API bound to `127.0.0.1:8000` (not `0.0.0.0`)
- [ ] `BACKUP_PASSPHRASE` is set and backup files are GPG-encrypted
- [ ] `JWT_SECRET` rotated (update `.env.secrets`, restart noa-api)
- [ ] External worker egress allowlist reviewed (compose labels)
- [ ] Audit retention running (check logs for retention purge entries)

---

## 8. Troubleshooting

| Problem | Check | Fix |
|---------|-------|-----|
| Container won't start | `docker compose logs <svc>` | Fix config/resource issue, restart |
| Slow API responses | `/health/metrics` pool stats | Restart noa-api; check DB VACUUM schedule |
| Audit log growing large | Retention purge running? | Verify `RETENTION_DAYS` (default 90) |
| Backup failures | `docker compose logs backup` | Check `BACKUP_PASSPHRASE`, disk space |
| Health check flapping | Container resource limits | Increase limits or check for memory leaks |
| Private worker OOM | `docker compose logs private-worker` | Reduce model size or increase memory limit |
| DB connection refused | `docker compose ps postgres` | Restart postgres; check `POSTGRES_PASSWORD` |
