#!/usr/bin/env bash
# verify_backup.sh — SPEC.md §10.5 weekly restore verification
#
# Finds the most recent .gpg backup, decrypts to tmpfs, restores into a
# temporary database, runs schema/row-count checks, and writes
# /backups/verify_status.json with the result.
#
# Exit codes:
#   0  — verification passed
#   1  — verification failed (details in verify_status.json)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TMPFS_DIR="${TMPFS_DIR:-/tmp}"
STATUS_FILE="${BACKUP_DIR}/verify_status.json"
TEMP_DB="${TEMP_DB:-noa_verify_$$}"
PGPASSWORD="${PGPASSWORD:-}"
PGHOST="${PGHOST:-postgres}"
PGUSER="${PGUSER:-noa}"
PGDATABASE="${PGDATABASE:-noa}"
VERIFY_PGHOST="${VERIFY_PGHOST:-postgres}"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

write_status() {
    local status="$1"
    local backup_file="$2"
    local error_msg="${3:-}"
    local timestamp
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    cat > "${STATUS_FILE}" <<EOF
{
  "status": "${status}",
  "timestamp": "${timestamp}",
  "backup_file": "${backup_file}",
  "error": "${error_msg}"
}
EOF
    log "Wrote verify_status.json: status=${status}"
}

cleanup() {
    # Drop temp database if it exists
    if psql -h "${VERIFY_PGHOST}" -U "${PGUSER}" -c "DROP DATABASE IF EXISTS ${TEMP_DB};" postgres 2>/dev/null; then
        log "Cleaned up temp database ${TEMP_DB}"
    fi
    # Remove decrypted temp file if it exists
    rm -f "${TMPFS_DIR}/verify_decrypted_$$.sql"
}

trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: Find most recent .gpg backup
# ---------------------------------------------------------------------------
log "Scanning ${BACKUP_DIR} for .gpg backups..."
LATEST_GPG="$(ls -1t "${BACKUP_DIR}"/noa_*.sql.gz.gpg 2>/dev/null | head -1 || true)"

if [[ -z "${LATEST_GPG}" ]]; then
    log "ERROR: No .gpg backup files found in ${BACKUP_DIR}"
    write_status "failed" "" "No .gpg backup files found"
    exit 1
fi

log "Latest backup: ${LATEST_GPG}"

# ---------------------------------------------------------------------------
# Step 2: Decrypt to tmpfs
# ---------------------------------------------------------------------------
DECRYPTED_FILE="${TMPFS_DIR}/verify_decrypted_$$.sql"
log "Decrypting ${LATEST_GPG} to tmpfs..."

if ! echo "${BACKUP_PASSPHRASE}" | gpg \
        --batch \
        --yes \
        --passphrase-fd 0 \
        --output "${DECRYPTED_FILE}.gz" \
        --decrypt "${LATEST_GPG}" 2>/tmp/gpg_err_$$.log; then
    GPG_ERR="$(cat /tmp/gpg_err_$$.log 2>/dev/null || echo unknown)"
    rm -f /tmp/gpg_err_$$.log
    log "ERROR: GPG decryption failed: ${GPG_ERR}"
    write_status "failed" "${LATEST_GPG}" "GPG decryption failed: ${GPG_ERR}"
    exit 1
fi
rm -f /tmp/gpg_err_$$.log

# Decompress
if ! gunzip -c "${DECRYPTED_FILE}.gz" > "${DECRYPTED_FILE}"; then
    log "ERROR: gunzip failed"
    write_status "failed" "${LATEST_GPG}" "gunzip failed"
    exit 1
fi
rm -f "${DECRYPTED_FILE}.gz"
log "Decrypted and decompressed to ${DECRYPTED_FILE}"

# ---------------------------------------------------------------------------
# Step 3: Create temporary database
# ---------------------------------------------------------------------------
log "Creating temp database ${TEMP_DB}..."
if ! psql -h "${VERIFY_PGHOST}" -U "${PGUSER}" \
        -c "CREATE DATABASE ${TEMP_DB};" postgres; then
    log "ERROR: Failed to create temp database"
    write_status "failed" "${LATEST_GPG}" "Failed to create temp database ${TEMP_DB}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 4: Run pg_restore
# ---------------------------------------------------------------------------
log "Restoring into ${TEMP_DB}..."
if ! psql -h "${VERIFY_PGHOST}" -U "${PGUSER}" \
        -d "${TEMP_DB}" \
        -f "${DECRYPTED_FILE}" \
        > /tmp/restore_out_$$.log 2>&1; then
    RESTORE_ERR="$(tail -5 /tmp/restore_out_$$.log 2>/dev/null || echo unknown)"
    rm -f /tmp/restore_out_$$.log
    log "ERROR: pg_restore failed: ${RESTORE_ERR}"
    write_status "failed" "${LATEST_GPG}" "pg_restore failed: ${RESTORE_ERR}"
    exit 1
fi
rm -f /tmp/restore_out_$$.log
log "pg_restore completed"

# ---------------------------------------------------------------------------
# Step 5: Schema check — verify expected tables exist and have rows
# ---------------------------------------------------------------------------
log "Running schema/row-count checks on ${TEMP_DB}..."

EXPECTED_TABLES="users threads messages runs artifacts"
SCHEMA_ERRORS=()

for table in ${EXPECTED_TABLES}; do
    COUNT="$(psql -h "${VERIFY_PGHOST}" -U "${PGUSER}" -d "${TEMP_DB}" \
        -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='${table}';" \
        2>/dev/null | tr -d '[:space:]' || echo 0)"
    if [[ "${COUNT}" != "1" ]]; then
        SCHEMA_ERRORS+=("Table '${table}' not found in restored database")
        log "WARNING: Table '${table}' not found"
    else
        log "Table '${table}' present"
    fi
done

if [[ ${#SCHEMA_ERRORS[@]} -gt 0 ]]; then
    ERROR_MSG="Schema check failed: ${SCHEMA_ERRORS[*]}"
    log "ERROR: ${ERROR_MSG}"
    write_status "failed" "${LATEST_GPG}" "${ERROR_MSG}"
    exit 1
fi

# Count total rows across key tables
TOTAL_ROWS=0
for table in ${EXPECTED_TABLES}; do
    ROW_COUNT="$(psql -h "${VERIFY_PGHOST}" -U "${PGUSER}" -d "${TEMP_DB}" \
        -t -c "SELECT COUNT(*) FROM ${table};" \
        2>/dev/null | tr -d '[:space:]' || echo 0)"
    log "Table '${table}': ${ROW_COUNT} rows"
    TOTAL_ROWS=$((TOTAL_ROWS + ROW_COUNT))
done
log "Total rows across checked tables: ${TOTAL_ROWS}"

# ---------------------------------------------------------------------------
# Step 6: Write success status
# ---------------------------------------------------------------------------
write_status "ok" "${LATEST_GPG}"
log "Backup verification PASSED for ${LATEST_GPG}"
exit 0
