from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.core.health import readiness_report


class Command(BaseCommand):
    help = "Memeriksa konfigurasi, database, cache, storage, worker, dan akun bootstrap."

    def handle(self, *args, **options):
        ready, checks = readiness_report(check_worker=not settings.CELERY_TASK_ALWAYS_EAGER)
        checks["debug_off"] = "ok" if not settings.DEBUG else "warning"
        checks["secret_key"] = "ok" if len(settings.SECRET_KEY) >= 32 else "warning"
        checks["media_root"] = (
            "ok" if settings.STORAGE_BACKEND == "s3" or settings.MEDIA_ROOT.exists() else "warning"
        )
        checks["bootstrap_admin"] = (
            "ok" if User.objects.filter(is_superuser=True, is_active=True).exists() else "missing"
        )
        model_dir = Path(settings.MODEL_CACHE_DIR)
        checks["fast_model"] = "ok" if (model_dir / "u2netp.onnx").is_file() else "missing"
        if "isnet-general-use" in settings.ALLOWED_REMBG_MODELS:
            checks["quality_model"] = (
                "ok" if (model_dir / "isnet-general-use.onnx").is_file() else "not_preloaded"
            )
        for name, status in checks.items():
            self.stdout.write(f"{name:24} {status.upper()}")
        if not ready:
            self.stderr.write(
                self.style.WARNING("Aplikasi belum ready. Periksa komponen berstatus selain OK.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Komponen inti siap."))
