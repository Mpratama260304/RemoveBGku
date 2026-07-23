# Docker Hub

Gunakan access token, bukan password akun utama:

```bash
docker login -u mpratamamail
docker build --platform linux/amd64 -t mpratamamail/removebgku:latest .
docker push mpratamamail/removebgku:latest
```

Untuk rilis versioned, tambahkan juga tag versi:

```bash
docker build --platform linux/amd64 -t mpratamamail/removebgku:1.0.0 .
docker push mpratamamail/removebgku:1.0.0
```

Compose memakai `mpratamamail/removebgku:latest` sebagai default, jadi di VPS cukup `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` tanpa set `APP_IMAGE`.

Pada GitHub, buat Secrets `DOCKERHUB_USERNAME` dan `DOCKERHUB_TOKEN`, serta variable `DOCKERHUB_REPOSITORY` bila nama bukan `removebgku`. Checklist rilis: test, migration check, security scan, changelog, tag versi, push image, smoke test image, lalu update deployment.
