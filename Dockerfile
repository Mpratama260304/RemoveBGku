# syntax=docker/dockerfile:1.7
FROM python:3.12.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements.txt

FROM python:3.12.12-slim-bookworm AS runtime
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="REMOVEBGKU" \
      org.opencontainers.image.description="Server-side background removal with Django and rembg" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="$APP_VERSION"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production APP_VERSION="$APP_VERSION" \
    HOME=/tmp/app XDG_CACHE_HOME=/tmp/app/.cache
RUN apt-get update && apt-get install -y --no-install-recommends tini libgomp1 libgl1 libglib2.0-0 postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . /app
RUN mkdir -p /data/media /data/state /models /tmp/app /backups /app/staticfiles /opt/models \
    && chown -R app:app /data /models /tmp/app /backups /app/staticfiles /opt/models \
    && chmod +x /app/scripts/*.sh /app/deploy/vps/*.sh
# Pra-unduh model rembg ke dalam image saat build agar runtime tidak perlu akses
# internet (VPS mungkin tidak dapat menjangkau GitHub). scripts/download-models.py
# menyalin file ini dari /opt/models ke U2NET_HOME saat container start.
ARG BAKE_MODELS="u2netp"
RUN for m in $BAKE_MODELS; do \
      U2NET_HOME=/opt/models HOME=/tmp/app python -c "import sys; from rembg import new_session; new_session(sys.argv[1])" "$m"; \
    done \
    && chown -R app:app /opt/models
USER app
EXPOSE 8000
VOLUME ["/data/media", "/models", "/data/state"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live/', timeout=3)"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["./scripts/start.sh", "web"]
