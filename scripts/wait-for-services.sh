#!/bin/sh
set -eu
python - <<'PY'
import os
import time
from urllib.parse import urlparse

import psycopg
import redis

deadline = time.monotonic() + 60
while True:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        break
    except Exception:
        if time.monotonic() > deadline:
            raise SystemExit("Database belum siap setelah 60 detik.")
        time.sleep(2)

if os.environ.get("WAIT_FOR_REDIS", "true").lower() == "true":
    client = redis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"), socket_timeout=3)
    while True:
        try:
            client.ping()
            break
        except Exception:
            if time.monotonic() > deadline:
                raise SystemExit("Redis belum siap setelah 60 detik.")
            time.sleep(2)
PY
