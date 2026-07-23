#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
./deploy/vps/backup.sh || echo "Lewati backup (database mungkin belum ada)." >&2
exec ./deploy/vps/deploy.sh
