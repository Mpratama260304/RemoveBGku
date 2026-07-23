# Render

Deploy `render.yaml` sebagai Blueprint. Blueprint membuat Web, Worker, cron cleanup, PostgreSQL, dan Key Value. Masukkan setiap variable `sync: false` melalui dashboard: secret Django/HMAC, domain/CSRF, S3 credentials, serta bootstrap admin. Gunakan bucket private S3-compatible karena filesystem container ephemeral.

Web dan Worker memakai Dockerfile yang sama dengan command berbeda. Setelah deploy, buka Shell Web dan jalankan `python manage.py doctor` serta `python manage.py check --deploy`. Health check berada di `/health/ready/`. Custom domain dan TLS diatur pada Settings Web Service. Rollback dilakukan dengan redeploy revision sebelumnya; periksa kompatibilitas migration sebelum rollback aplikasi.
