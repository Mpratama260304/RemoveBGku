#!/bin/sh
set -eu

if [ "$(uname -m)" != "x86_64" ]; then echo "Script ini ditujukan untuk x86_64." >&2; exit 1; fi
if ! grep -q 'Ubuntu 24.04' /etc/os-release; then echo "Peringatan: target tervalidasi adalah Ubuntu 24.04." >&2; fi
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; $SUDO -v; fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker Engine dan Compose sudah tersedia; konfigurasi yang ada dipertahankan."
else
  $SUDO apt-get update
  $SUDO apt-get install -y ca-certificates curl
  $SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO tee /etc/apt/keyrings/docker.asc >/dev/null
  $SUDO chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
  $SUDO apt-get update
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

$SUDO install -d -m 0750 -o "${SUDO_USER:-$USER}" -g "${SUDO_USER:-$USER}" /opt/removebgku
echo "Server siap. Buka TCP 80/443 pada Tencent Security Group; batasi TCP 22 ke IP Anda."
echo "Jangan membuka port PostgreSQL 5432 atau Redis 6379 ke internet."
