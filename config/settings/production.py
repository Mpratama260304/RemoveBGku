from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

# Deploy tanpa ribet: SECRET_KEY dibuat & disimpan otomatis di volume, DATABASE_URL
# dan host diisi default oleh docker-compose. Validasi ketat opsional: STRICT_ENV=true.
if env_bool("STRICT_ENV", False):  # noqa: F405
    required = ["DJANGO_SECRET_KEY", "DATABASE_URL", "ALLOWED_HOSTS", "APP_BASE_URL"]
    missing = [name for name in required if not env(name)]  # noqa: F405
    if missing:
        raise ImproperlyConfigured("Environment produksi wajib belum lengkap: " + ", ".join(missing))

# TLS diterminasi oleh Caddy. Biarkan Caddy yang redirect HTTP->HTTPS supaya tidak terjadi
# loop dan health check internal (http://127.0.0.1) tetap berjalan.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^health/"]
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)  # noqa: F405
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)  # noqa: F405
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31_536_000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)  # noqa: F405
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
