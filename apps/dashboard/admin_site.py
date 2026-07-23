from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.core.health import readiness_report


class HapusAdminSite(AdminSite):
    site_header = "REMOVEBGKU"
    site_title = "REMOVEBGKU Admin"
    index_title = "Dashboard Operasional"
    index_template = "admin/dashboard.html"

    def each_context(self, request):
        context = super().each_context(request)
        context.update(site_header=settings.SITE_NAME, site_title=f"{settings.SITE_NAME} Admin")
        return context

    def index(self, request, extra_context=None):
        from apps.jobs.models import ImageJob
        from apps.jobs.selectors import recent_jobs

        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        base = ImageJob.objects.all()
        success = base.filter(status=ImageJob.Status.SUCCEEDED).count()
        failed = base.filter(status=ImageJob.Status.FAILED).count()
        finished = success + failed
        stats = base.aggregate(
            queued=Count("id", filter=Q(status=ImageJob.Status.QUEUED)),
            processing=Count("id", filter=Q(status=ImageJob.Status.PROCESSING)),
            succeeded=Count("id", filter=Q(status=ImageJob.Status.SUCCEEDED)),
            failed=Count("id", filter=Q(status=ImageJob.Status.FAILED)),
            total_original=Sum("original_size_bytes"),
            total_result=Sum("result_size_bytes"),
            avg_duration=Avg("processing_duration_ms", filter=Q(status=ImageJob.Status.SUCCEEDED)),
            pinned=Count("id", filter=Q(is_pinned=True)),
        )
        daily = list(
            base.filter(created_at__gte=today - timedelta(days=29))
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), succeeded=Count("id", filter=Q(status=ImageJob.Status.SUCCEEDED)))
            .order_by("day")
        )
        durations = list(
            base.filter(
                status=ImageJob.Status.SUCCEEDED,
                processing_duration_ms__isnull=False,
                created_at__gte=today - timedelta(days=29),
            )
            .order_by("processing_duration_ms")
            .values_list("processing_duration_ms", flat=True)
        )
        p95_duration = durations[min(int(len(durations) * 0.95), len(durations) - 1)] if durations else None
        model_usage = list(base.values("model_name").annotate(total=Count("id")).order_by("-total")[:8])
        error_distribution = list(
            base.filter(status=ImageJob.Status.FAILED)
            .values("error_code")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )
        _, health = readiness_report(check_worker=False)
        model_dir = Path(settings.MODEL_CACHE_DIR)
        health["model cepat"] = "ok" if (model_dir / "u2netp.onnx").is_file() else "missing"
        if "isnet-general-use" in settings.ALLOWED_REMBG_MODELS:
            health["model kualitas"] = (
                "ok" if (model_dir / "isnet-general-use.onnx").is_file() else "not_preloaded"
            )
        extra_context = {
            **(extra_context or {}),
            "kpis": {
                "today": base.filter(created_at__gte=today).count(),
                "seven_days": base.filter(created_at__gte=today - timedelta(days=6)).count(),
                "thirty_days": base.filter(created_at__gte=today - timedelta(days=29)).count(),
                "success_rate": round(success / finished * 100, 1) if finished else 0,
                "p95_duration": p95_duration,
                **stats,
                "expired": base.filter(expires_at__lte=now)
                .exclude(status=ImageJob.Status.FILES_DELETED)
                .count(),
            },
            "daily": daily,
            "model_usage": model_usage,
            "error_distribution": error_distribution,
            "recent_jobs": recent_jobs(),
            "system_health": health,
            "server_time": now,
            "app_version": settings.APP_VERSION,
            "deployed_at": settings.APP_DEPLOYED_AT,
        }
        return super().index(request, extra_context=extra_context)


class HapusAdminConfig(AdminConfig):
    default_site = "apps.dashboard.admin_site.HapusAdminSite"
