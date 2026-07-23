from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

required = [
    "DJANGO_SECRET_KEY",
    "DATABASE_URL",
    "ALLOWED_HOSTS",
    "APP_BASE_URL",
    "SESSION_HASH_SECRET",
    "IP_HASH_SECRET",
]
missing = [name for name in required if not env(name)]  # noqa: F405
if missing and not env_bool("SKIP_PRODUCTION_ENV_VALIDATION", False):  # noqa: F405
    raise ImproperlyConfigured("Environment produksi wajib belum lengkap: " + ", ".join(missing))

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)  # noqa: F405
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
