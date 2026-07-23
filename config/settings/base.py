from __future__ import annotations

import contextlib
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_local_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    return int(env(name, str(default)))


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def _resolve_secret_key() -> str:
    value = env("DJANGO_SECRET_KEY")
    if value:
        return value
    state_dir = env("APP_STATE_DIR")
    if state_dir:
        key_path = Path(state_dir) / "secret_key"
        try:
            if key_path.is_file():
                existing = key_path.read_text(encoding="utf-8").strip()
                if existing:
                    return existing
            import secrets as _secrets

            generated = _secrets.token_urlsafe(64)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(generated, encoding="utf-8")
            with contextlib.suppress(OSError):
                key_path.chmod(0o600)
            return generated
        except OSError:
            pass
    return "development-only-change-me"


SECRET_KEY = _resolve_secret_key()
DEBUG = env_bool("DEBUG", False)
DOMAIN = env("DOMAIN")
_default_allowed_hosts = "localhost,127.0.0.1,testserver,web"
if DOMAIN:
    _default_allowed_hosts = f"{_default_allowed_hosts},{DOMAIN}"
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", _default_allowed_hosts)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or ([f"https://{DOMAIN}"] if DOMAIN else [])

SITE_NAME = env("SITE_NAME", "REMOVEBGKU")
SITE_TAGLINE = env("SITE_TAGLINE", "Hapus latar belakang gambar dengan mudah")
APP_BASE_URL = env("APP_BASE_URL") or (f"https://{DOMAIN}" if DOMAIN else "http://localhost:8000")
APP_VERSION = env("APP_VERSION", "dev")
APP_DEPLOYED_AT = env("APP_DEPLOYED_AT", "")
ADMIN_URL_PATH = env("ADMIN_URL_PATH", "admin/").strip("/") + "/"

INSTALLED_APPS = [
    "apps.dashboard.admin_site.HapusAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "apps.accounts",
    "apps.core",
    "apps.jobs",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.AdminLoginRateLimitMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.MaintenanceModeMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_context",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL")
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "/admin/login/"

LANGUAGE_CODE = "id"
TIME_ZONE = env("APP_TIME_ZONE", "Asia/Jakarta")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/media-private/"

storage_backend = env("STORAGE_BACKEND", "local")
STORAGE_BACKEND = storage_backend
AWS_QUERYSTRING_EXPIRE = env_int("AWS_QUERYSTRING_EXPIRE", 300)
if storage_backend == "s3":
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": env("AWS_ACCESS_KEY_ID"),
                "secret_key": env("AWS_SECRET_ACCESS_KEY"),
                "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
                "endpoint_url": env("AWS_S3_ENDPOINT_URL") or None,
                "region_name": env("AWS_S3_REGION_NAME", "auto"),
                "signature_version": env("AWS_S3_SIGNATURE_VERSION", "s3v4"),
                "addressing_style": env("AWS_S3_ADDRESSING_STYLE", "auto"),
                "querystring_auth": True,
                "querystring_expire": env_int("AWS_QUERYSTRING_EXPIRE", 300),
                "default_acl": None,
                "file_overwrite": False,
                "location": env("STORAGE_PREFIX", "development").strip("/"),
            },
        },
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("UPLOAD_MAX_BYTES", 50 * 1024 * 1024) + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("UPLOAD_MAX_BYTES", 50 * 1024 * 1024)
UPLOAD_MAX_BYTES = env_int("UPLOAD_MAX_BYTES", 50 * 1024 * 1024)
MAX_IMAGE_PIXELS = env_int("MAX_IMAGE_PIXELS", 36_000_000)
MAX_IMAGE_WIDTH = env_int("MAX_IMAGE_WIDTH", 6000)
MAX_IMAGE_HEIGHT = env_int("MAX_IMAGE_HEIGHT", 6000)
MIN_IMAGE_WIDTH = env_int("MIN_IMAGE_WIDTH", 32)
MIN_IMAGE_HEIGHT = env_int("MIN_IMAGE_HEIGHT", 32)
JOB_RETENTION_HOURS = env_int("JOB_RETENTION_HOURS", 24)
METADATA_RETENTION_DAYS = env_int("METADATA_RETENTION_DAYS", 30)
MAX_ACTIVE_JOBS_PER_SESSION = env_int("MAX_ACTIVE_JOBS_PER_SESSION", 3)
MAX_QUEUE_SIZE = env_int("MAX_QUEUE_SIZE", 50)
UPLOAD_RATE_LIMIT_PER_HOUR = env_int("UPLOAD_RATE_LIMIT_PER_HOUR", 10)
DOWNLOAD_RATE_LIMIT_PER_MINUTE = env_int("DOWNLOAD_RATE_LIMIT_PER_MINUTE", 30)
ADMIN_LOGIN_RATE_LIMIT_PER_15_MINUTES = env_int("ADMIN_LOGIN_RATE_LIMIT_PER_15_MINUTES", 10)
STALE_PROCESSING_MINUTES = env_int("STALE_PROCESSING_MINUTES", 10)
SESSION_HASH_SECRET = env("SESSION_HASH_SECRET", SECRET_KEY)
IP_HASH_SECRET = env("IP_HASH_SECRET", SECRET_KEY)

DEFAULT_REMBG_MODEL = env("DEFAULT_REMBG_MODEL", "u2netp")
ALLOWED_REMBG_MODELS = env_list("ALLOWED_REMBG_MODELS", "u2netp,isnet-general-use")
MODEL_CACHE_DIR = env("MODEL_CACHE_DIR", str(BASE_DIR / "models"))
os.environ.setdefault("U2NET_HOME", env("U2NET_HOME", MODEL_CACHE_DIR))

REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = env_int("CELERY_PREFETCH_MULTIPLIER", 1)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 240)
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 300)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 3600
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-hourly": {"task": "apps.jobs.tasks.cleanup_expired", "schedule": 3600.0},
    "recover-stale-every-five-minutes": {"task": "apps.jobs.tasks.recover_stale", "schedule": 300.0},
    "worker-heartbeat": {"task": "apps.jobs.tasks.record_worker_heartbeat", "schedule": 30.0},
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache"
        if env_bool("USE_REDIS_CACHE", bool(DATABASE_URL))
        else "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": REDIS_URL if env_bool("USE_REDIS_CACHE", bool(DATABASE_URL)) else "removebgku-cache",
    }
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.core.logging.JSONFormatter",
            "environment": env("APP_ENV", "development"),
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}

SENTRY_DSN = env("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", env("APP_ENV", "production")),
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
    )
