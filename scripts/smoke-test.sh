#!/bin/sh
set -eu
base_url="${APP_BASE_URL:-http://localhost}"
python - "$base_url" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
with urllib.request.urlopen(base + "/health/live/", timeout=10) as response:
    assert response.status == 200
    assert json.load(response)["status"] == "ok"
print("Live health smoke test lulus.")
PY
