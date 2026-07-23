# Railway

The repository-level `railway.toml` selects the Dockerfile builder. Runtime
commands stay service-specific because the web and worker services share this
same source repository.

1. Buat project, tambahkan PostgreSQL dan Redis.
2. Buat Web service dan Worker service dari repository/Dockerfile yang sama.
3. Command Web: `./scripts/start.sh web`; Worker: `./scripts/start.sh worker`.
4. Tambahkan semua variable dari `.env.production.example`. Gunakan `STORAGE_BACKEND=s3`; filesystem service bersifat ephemeral dan volume satu service tidak otomatis dibagi ke service lain.
5. Set `DATABASE_URL` dan `CELERY_BROKER_URL` dari managed services. Masukkan credential S3/private bucket serta bootstrap admin melalui Variables, bukan source.
6. Web harus memiliki `APP_BASE_URL`, `ALLOWED_HOSTS`, dan `CSRF_TRUSTED_ORIGINS` sesuai generated/custom domain. Port dibaca dari `$PORT`.
7. Gunakan `/health/ready/` sebagai health check. Migration dan bootstrap dijalankan oleh Web memakai advisory lock.
8. Tambahkan Cron service per jam dengan command `./scripts/start.sh cleanup`, atau Beat service terpisah.

Verifikasi dari shell service Web: `python manage.py doctor`, `python manage.py check --deploy`, dan `python manage.py bootstrap_admin`. Untuk rollback, pilih deployment image/revision sebelumnya di Railway; jangan mengubah atau menghapus volume/database.
