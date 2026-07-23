#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
env_file="${ENV_FILE:-.env.production}"
[ -f "$env_file" ] || { echo "$env_file tidak ditemukan." >&2; exit 1; }
set -a; . "./$env_file"; set +a
case "${APP_IMAGE:-}" in *:latest) echo "Gunakan tag versioned untuk update dan rollback." >&2; exit 1;; esac
./deploy/vps/backup.sh
current_file=".previous-image"
if [ -f .current-image ]; then cp .current-image "$current_file"; fi
printf '%s\n' "$APP_IMAGE" > .current-image
if ! ./deploy/vps/deploy.sh; then
  if [ -f "$current_file" ]; then
    previous="$(sed -n '1p' "$current_file")"
    echo "Update gagal. Untuk rollback: APP_IMAGE=$previous ./deploy/vps/deploy.sh"
  fi
  exit 1
fi
