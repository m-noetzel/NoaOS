#!/usr/bin/env bash
# Noa private data backup — SPEC.md §10.5
# Tars /data/, encrypts with GPG, and rotates old backups.
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
BACKUP_DIR="${BACKUP_DIR:-/backups/private}"
KEEP="${BACKUP_KEEP:-7}"
TIMESTAMP="$(date -u +%Y-%m-%d_%H%M)"
ARCHIVE_FILE="${BACKUP_DIR}/private_${TIMESTAMP}.tar.gz.gpg"

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
    echo "ERROR: BACKUP_PASSPHRASE environment variable is not set" >&2
    exit 1
fi

if [ ! -d "${DATA_DIR}" ]; then
    echo "ERROR: Data directory not found: ${DATA_DIR}" >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[backup-private] Starting private data backup at $(date -u +%FT%TZ)"

# Tar → gzip → GPG symmetric encryption
if ! tar -czf - -C "${DATA_DIR}" . \
    | gpg --batch --yes --symmetric --cipher-algo AES256 \
          --passphrase "${BACKUP_PASSPHRASE}" \
          --output "${ARCHIVE_FILE}"; then
    echo "ERROR: Private data backup failed" >&2
    rm -f "${ARCHIVE_FILE}"
    exit 1
fi

if [ ! -s "${ARCHIVE_FILE}" ]; then
    echo "ERROR: Archive file is empty or missing: ${ARCHIVE_FILE}" >&2
    exit 1
fi

echo "[backup-private] Backup saved: ${ARCHIVE_FILE} ($(du -h "${ARCHIVE_FILE}" | cut -f1))"

# Rotate: keep only the newest $KEEP backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -maxdepth 1 -name 'private_*.tar.gz.gpg' -type f | wc -l)
if [ "${BACKUP_COUNT}" -gt "${KEEP}" ]; then
    REMOVE_COUNT=$((BACKUP_COUNT - KEEP))
    # shellcheck disable=SC2012
    ls -1t "${BACKUP_DIR}"/private_*.tar.gz.gpg | tail -n "${REMOVE_COUNT}" | xargs rm -f
    echo "[backup-private] Rotated ${REMOVE_COUNT} old backup(s), keeping ${KEEP}"
fi

echo "[backup-private] Backup complete at $(date -u +%FT%TZ)"
