#!/bin/sh
set -eu

mode="${1:-web}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"

case "$mode" in
  web)
    ./scripts/wait-for-services.sh
    python manage.py migrate_locked
    python manage.py collectstatic --noinput
    python manage.py bootstrap_admin
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
