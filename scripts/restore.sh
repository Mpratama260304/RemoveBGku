#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then echo "Penggunaan: restore.sh /path/backup.dump" >&2; exit 2; fi
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$1"
python manage.py migrate --noinput
python manage.py doctor
