#!/usr/bin/env bash
# Noa Postgres backup — SPEC.md §10.5
# Runs pg_dump, compresses, encrypts with GPG symmetric cipher, and rotates.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP="${BACKUP_KEEP:-7}"
TIMESTAMP="$(date -u +%Y-%m-%d_%H%M)"
DUMP_FILE="${BACKUP_DIR}/noa_${TIMESTAMP}.sql.gz.gpg"
PGHOST="${PGHOST:-postgres}"
PGUSER="${PGUSER:-noa}"
PGDATABASE="${PGDATABASE:-noa}"

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
    echo "ERROR: BACKUP_PASSPHRASE environment variable is not set" >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[backup] Starting Postgres backup at $(date -u +%FT%TZ)"

# Dump → gzip → GPG symmetric encryption
if ! pg_dump -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" --no-password \
    | gzip -9 \
    | gpg --batch --yes --symmetric --cipher-algo AES256 \
          --passphrase "${BACKUP_PASSPHRASE}" \
          --output "${DUMP_FILE}"; then
    echo "ERROR: pg_dump or encryption failed" >&2
    rm -f "${DUMP_FILE}"
    exit 1
fi

# Verify the output file exists and is non-empty
if [ ! -s "${DUMP_FILE}" ]; then
    echo "ERROR: Backup file is empty or missing: ${DUMP_FILE}" >&2
    exit 1
fi

echo "[backup] Backup saved: ${DUMP_FILE} ($(du -h "${DUMP_FILE}" | cut -f1))"

# Rotate: keep only the newest $KEEP backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -maxdepth 1 -name 'noa_*.sql.gz.gpg' -type f | wc -l)
if [ "${BACKUP_COUNT}" -gt "${KEEP}" ]; then
    REMOVE_COUNT=$((BACKUP_COUNT - KEEP))
    # shellcheck disable=SC2012
    ls -1t "${BACKUP_DIR}"/noa_*.sql.gz.gpg | tail -n "${REMOVE_COUNT}" | xargs rm -f
    echo "[backup] Rotated ${REMOVE_COUNT} old backup(s), keeping ${KEEP}"
fi

echo "[backup] Backup complete at $(date -u +%FT%TZ)"
