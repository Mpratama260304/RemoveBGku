# Deployment VPS Ubuntu 24.04

## Persiapan

1. (Opsional, untuk HTTPS) arahkan A record domain ke IPv4 VPS.
2. Di Security Group, izinkan TCP 80/443 dari semua alamat dan TCP 22 hanya dari IP administrator. Jangan buka 5432/6379.
3. Jalankan `sudo ./deploy/vps/bootstrap-server.sh`.
4. Salin proyek ke `/opt/removebgku`.
5. (Opsional, untuk HTTPS) set domain lewat satu baris: `echo "DOMAIN=domain-kamu.com" > .env`.
6. Jalankan `./deploy/vps/deploy.sh`.

Tidak perlu mengisi secret apa pun. `SECRET_KEY` dan password database dibuat otomatis lalu disimpan di volume Docker. Password admin awal ditampilkan sekali di log service `web`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs web | grep -A3 "admin siap"
```

Verifikasi:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 web worker
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py doctor
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py check --deploy
```

Mode minimal menonaktifkan beat (`profiles: full`) dan memakai cron host:

```cron
15 * * * * cd /opt/removebgku && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web ./scripts/start.sh cleanup
30 2 * * * cd /opt/removebgku && ./deploy/vps/backup.sh
```

Mode lengkap dijalankan dengan `docker compose ... --profile full up -d`.

Update ke image terbaru: `./deploy/vps/update.sh`. Untuk rollback ke versi tertentu: `APP_IMAGE=mpratama260304/removebgku:1.0.0 ./deploy/vps/deploy.sh`. Volume database/media/model/Caddy/secret tetap dipertahankan.

Untuk RAM 4 GB, swap 2 GB dapat mengurangi risiko OOM saat lonjakan singkat (`fallocate`, `mkswap`, `swapon`), tetapi swap bukan pengganti RAM. Pertahankan concurrency worker satu.

Restore: hentikan worker, backup database aktif, jalankan `pg_restore --clean --if-exists` ke database, migration, `doctor`, hidupkan worker, lalu smoke test. Media lokal perlu dicadangkan terpisah memakai restic/rsync dengan enkripsi.
