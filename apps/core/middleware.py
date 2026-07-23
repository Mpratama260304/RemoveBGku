import uuid

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class AdminLoginRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_path = f"/{settings.ADMIN_URL_PATH}login/"
        if request.method == "POST" and request.path == login_path:
            from apps.core.rate_limit import consume
            from apps.core.security import hash_client_ip

            result = consume(
                f"admin-login:{hash_client_ip(request)}",
                settings.ADMIN_LOGIN_RATE_LIMIT_PER_15_MINUTES,
                900,
            )
            if not result.allowed:
                response = HttpResponse("Terlalu banyak percobaan login. Coba lagi nanti.", status=429)
                response["Retry-After"] = str(result.retry_after)
                return response
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response


class MaintenanceModeMiddleware:
    bypass_prefixes = ("/admin/", "/health/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.bypass_prefixes) or getattr(request.user, "is_staff", False):
            return self.get_response(request)
        try:
            from apps.jobs.models import SiteConfiguration

            config = SiteConfiguration.get_solo()
            if config.maintenance_mode:
                if request.path.startswith("/api/") or request.path.endswith("/status/"):
                    return HttpResponse("Layanan sedang dalam pemeliharaan.", status=503)
                return render(request, "errors/maintenance.html", {"config": config}, status=503)
        except Exception:
            pass
        return self.get_response(request)
