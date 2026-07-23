# Docker Hub

Gunakan access token, bukan password akun utama:

```bash
docker login
docker build --platform linux/amd64 -t USERNAME/hapusbackground:1.0.0 .
docker push USERNAME/hapusbackground:1.0.0
```

Pada GitHub, buat Secrets `DOCKERHUB_USERNAME` dan `DOCKERHUB_TOKEN`, serta variable `DOCKERHUB_REPOSITORY` bila nama bukan `hapusbackground`. Checklist rilis: test, migration check, security scan, changelog, tag versi, push image, smoke test image, lalu update deployment memakai tag versioned.
