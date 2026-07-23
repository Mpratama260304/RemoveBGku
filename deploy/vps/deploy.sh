#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# Deploy tanpa ribet: semua secret dibuat otomatis di dalam container.
# Opsional set DOMAIN (via `export DOMAIN=contoh.com` atau file .env satu baris)
# untuk mengaktifkan HTTPS otomatis lewat Caddy.
$COMPOSE pull
$COMPOSE run --rm web ./scripts/start.sh migrate
$COMPOSE up -d

attempt=0
until $COMPOSE exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live/', timeout=3)" 2>/dev/null; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || { echo "Health check gagal. Cek: $COMPOSE logs web" >&2; exit 1; }
  sleep 2
done

echo "REMOVEBGKU aktif."
echo "Lihat password admin awal: $COMPOSE logs web | grep -A3 'admin siap'"
