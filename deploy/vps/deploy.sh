#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
env_file="${ENV_FILE:-.env.production}"
[ -f "$env_file" ] || { echo "$env_file tidak ditemukan." >&2; exit 1; }
set -a
. "./$env_file"
set +a
for name in DOMAIN DJANGO_SECRET_KEY POSTGRES_PASSWORD BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_PASSWORD APP_IMAGE; do
  eval "value=\${$name:-}"
  [ -n "$value" ] || { echo "Variable wajib belum diisi: $name" >&2; exit 1; }
done
[ "${#DJANGO_SECRET_KEY}" -ge 50 ] || { echo "DJANGO_SECRET_KEY minimal 50 karakter." >&2; exit 1; }
docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml run --rm web ./scripts/start.sh migrate
docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py bootstrap_admin
docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml up -d
attempt=0
until docker compose --env-file "$env_file" -f docker-compose.yml -f docker-compose.prod.yml exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live/',timeout=3)"; do
  attempt=$((attempt + 1)); [ "$attempt" -lt 30 ] || { echo "Health check gagal. Periksa logs." >&2; exit 1; }; sleep 2
done
echo "Deployment aktif di https://$DOMAIN"
