#!/usr/bin/env bash
# Noa Postgres restore — SPEC.md §10.5
# Decrypts, decompresses, and restores a backup into Postgres.
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-file.sql.gz.gpg>" >&2
    exit 1
fi

BACKUP_FILE="$1"
PGHOST="${PGHOST:-postgres}"
PGUSER="${PGUSER:-noa}"
PGDATABASE="${PGDATABASE:-noa}"

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
    echo "ERROR: BACKUP_PASSPHRASE environment variable is not set" >&2
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "[restore] Starting restore from ${BACKUP_FILE} at $(date -u +%FT%TZ)"

# Decrypt → decompress → restore via psql
if ! gpg --batch --yes --decrypt \
         --passphrase "${BACKUP_PASSPHRASE}" \
         "${BACKUP_FILE}" \
    | gunzip \
    | psql -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" --no-password -q; then
    echo "ERROR: Restore failed" >&2
    exit 1
fi

# Verification: run a simple SELECT to confirm the database is accessible
echo "[restore] Verifying data integrity..."
VERIFY=$(psql -h "${PGHOST}" -U "${PGUSER}" -d "${PGDATABASE}" --no-password -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")

if [ -z "${VERIFY}" ]; then
    echo "ERROR: Verification query returned empty result" >&2
    exit 1
fi

TABLE_COUNT=$(echo "${VERIFY}" | tr -d '[:space:]')
echo "[restore] Restore complete. Public schema has ${TABLE_COUNT} table(s)."
echo "[restore] Finished at $(date -u +%FT%TZ)"
