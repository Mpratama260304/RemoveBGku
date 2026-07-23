from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from apps.core import health
from apps.jobs import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True),
    ),
    path("history/", views.history, name="history"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("faq/", views.faq, name="faq"),
    path("jobs/", include("apps.jobs.urls")),
    path("api/v1/", include("apps.jobs.api_urls")),
    path("health/live/", health.live, name="health-live"),
    path("health/ready/", health.ready, name="health-ready"),
    path(settings.ADMIN_URL_PATH if hasattr(settings, "ADMIN_URL_PATH") else "admin/", admin.site.urls),
]

handler400 = "apps.jobs.views.error_400"
handler403 = "apps.jobs.views.error_403"
handler404 = "apps.jobs.views.error_404"
handler500 = "apps.jobs.views.error_500"
