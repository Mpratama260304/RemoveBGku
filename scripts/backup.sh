#!/bin/sh
set -eu
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR:-/backups}/database-${timestamp}.dump"
umask 077
pg_dump --format=custom --file="$target" "$DATABASE_URL"
sha256sum "$target" > "${target}.sha256"
find "${BACKUP_DIR:-/backups}" -type f -name 'database-*.dump*' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
echo "Backup database berhasil: $target"
