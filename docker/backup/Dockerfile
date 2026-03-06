# Noa backup sidecar — SPEC.md §10.5
# Alpine-based container with pg_dump, gpg, and cron.
FROM alpine:3.19

RUN apk add --no-cache \
    bash \
    postgresql16-client \
    gnupg \
    dcron \
    gzip \
    tar \
    && mkdir -p /backups/private /scripts /var/log

COPY scripts/backup.sh /scripts/backup.sh
COPY scripts/restore.sh /scripts/restore.sh
COPY scripts/backup_private.sh /scripts/backup_private.sh
COPY docker/backup/crontab /etc/crontabs/root

RUN chmod +x /scripts/*.sh

# Run crond in foreground
CMD ["crond", "-f", "-l", "2"]
