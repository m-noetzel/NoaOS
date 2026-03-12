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
COPY docker/backup/verify_backup.sh /scripts/verify_backup.sh
COPY docker/backup/crontab /etc/crontabs/root

RUN chmod +x /scripts/*.sh

# Weekly verify cron: Sunday 03:00 UTC (SPEC.md §10.5)
RUN echo "0 3 * * 0 /scripts/verify_backup.sh >> /var/log/backup.log 2>&1" >> /etc/crontabs/root

# Run crond in foreground
CMD ["crond", "-f", "-l", "2"]
