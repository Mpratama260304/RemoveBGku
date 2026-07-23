# Deployment VPS Ubuntu 24.04

## Persiapan

1. Arahkan A record domain ke IPv4 VPS Tencent.
2. Di Tencent Security Group, izinkan TCP 80/443 dari semua alamat dan TCP 22 hanya dari IP administrator. Jangan buka 5432/6379.
3. Jalankan `sudo ./deploy/vps/bootstrap-server.sh`.
4. Salin proyek ke `/opt/hapusbackground`, lalu `cp .env.production.example .env.production` dan isi semua nilai `replace-*` dengan secret acak. Jangan tempel secret langsung ke command shell.
5. Jalankan `./deploy/vps/deploy.sh`.

Verifikasi:

```bash
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 web worker
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py doctor
docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py check --deploy
```

Mode minimal menonaktifkan beat (`profiles: full`) dan memakai cron host:

```cron
15 * * * * cd /opt/hapusbackground && docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml run --rm web ./scripts/start.sh cleanup
30 2 * * * cd /opt/hapusbackground && ./deploy/vps/backup.sh
```

Mode lengkap dijalankan dengan `docker compose ... --profile full up -d`.

Update memakai tag image versioned: ubah `APP_IMAGE`, lalu `./deploy/vps/update.sh`. Jika update gagal, script menampilkan tag sebelumnya untuk rollback. Volume database/media/model/Caddy tetap dipertahankan.

Untuk RAM 4 GB, swap 2 GB dapat mengurangi risiko OOM saat lonjakan singkat (`fallocate`, `mkswap`, `swapon`), tetapi swap bukan pengganti RAM. Pertahankan concurrency worker satu.

Restore: hentikan worker, backup database aktif, jalankan `pg_restore --clean --if-exists` ke database, migration, `doctor`, hidupkan worker, lalu smoke test. Media lokal perlu dicadangkan terpisah memakai restic/rsync dengan enkripsi.
