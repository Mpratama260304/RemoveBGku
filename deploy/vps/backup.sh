#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
env_file="${ENV_FILE:-.env.production}"
docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "data/backups/database-$(date -u +%Y%m%dT%H%M%SZ).dump"
chmod 600 data/backups/database-*.dump
find data/backups -type f -name 'database-*.dump' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
echo "Backup database selesai."
