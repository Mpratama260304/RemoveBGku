#!/bin/sh
set -eu

mode="${1:-web}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
APP_STATE_DIR="${APP_STATE_DIR:-/data/state}"

# Buat SECRET_KEY sekali lalu simpan di volume; semua service memakai key yang sama.
ensure_secret_key() {
  [ -n "${DJANGO_SECRET_KEY:-}" ] && return 0
  mkdir -p "$APP_STATE_DIR" 2>/dev/null || true
  key_file="$APP_STATE_DIR/secret_key"
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$APP_STATE_DIR/.secret.lock" && flock 9
  fi
  if [ ! -s "$key_file" ]; then
    python -c "import secrets; print(secrets.token_urlsafe(64))" > "$key_file"
    chmod 600 "$key_file" 2>/dev/null || true
  fi
  if command -v flock >/dev/null 2>&1; then flock -u 9 2>/dev/null || true; fi
  DJANGO_SECRET_KEY="$(cat "$key_file")"
  export DJANGO_SECRET_KEY
}

# Admin awal otomatis. Password dibuat & disimpan di volume, ditampilkan sekali di log.
ensure_admin() {
  [ "${BOOTSTRAP_ADMIN_ENABLED:-true}" = "true" ] || return 0
  : "${BOOTSTRAP_ADMIN_EMAIL:=admin@${DOMAIN:-localhost}}"
  BOOTSTRAP_ADMIN_ENABLED=true
  export BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_ENABLED
  if [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    pw_file="$APP_STATE_DIR/admin_password"
    if [ ! -s "$pw_file" ]; then
      python -c "import secrets; print(secrets.token_urlsafe(18))" > "$pw_file"
      chmod 600 "$pw_file" 2>/dev/null || true
    fi
    BOOTSTRAP_ADMIN_PASSWORD="$(cat "$pw_file")"
    export BOOTSTRAP_ADMIN_PASSWORD
    echo "======================================================================"
    echo " REMOVEBGKU admin siap dipakai:"
    echo "   Email    : $BOOTSTRAP_ADMIN_EMAIL"
    echo "   Password : $BOOTSTRAP_ADMIN_PASSWORD"
    echo "   (tersimpan di $pw_file - ganti setelah login pertama)"
    echo "======================================================================"
  fi
  python manage.py bootstrap_admin
}

ensure_secret_key

case "$mode" in
  web)
    ./scripts/wait-for-services.sh
    python manage.py migrate_locked
    python manage.py collectstatic --noinput
    ensure_admin
    exec gunicorn config.wsgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-2}" \
      --threads "${GUNICORN_THREADS:-2}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
      --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
      --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
      --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
      --access-logfile - --error-logfile -
    ;;
  worker)
    ./scripts/wait-for-services.sh
    python scripts/download-models.py
    exec celery -A config worker --loglevel="${LOG_LEVEL:-INFO}" \
      --concurrency="${CELERY_CONCURRENCY:-1}" --prefetch-multiplier=1 --max-tasks-per-child=20
    ;;
  beat)
    ./scripts/wait-for-services.sh
    exec celery -A config beat --loglevel="${LOG_LEVEL:-INFO}" --schedule=/tmp/app/celerybeat-schedule
    ;;
  migrate)
    ./scripts/wait-for-services.sh
    exec python manage.py migrate_locked
    ;;
  cleanup)
    ./scripts/wait-for-services.sh
    exec python manage.py cleanup_expired_jobs --batch-size "${CLEANUP_BATCH_SIZE:-100}"
    ;;
  *) echo "Mode tidak dikenal: $mode" >&2; exit 2 ;;
esac
