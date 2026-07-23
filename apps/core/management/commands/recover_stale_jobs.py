from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.jobs.models import ImageJob
from apps.jobs.tasks import _mark_failed


class Command(BaseCommand):
    help = "Menandai job processing yang stale sebagai gagal agar dapat dicoba ulang."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=settings.STALE_PROCESSING_MINUTES)
        ids = list(
            ImageJob.objects.filter(
                status=ImageJob.Status.PROCESSING, processing_started_at__lt=cutoff
            ).values_list("pk", flat=True)
        )
        for job_id in ids:
            _mark_failed(
                job_id, "PROCESSING_TIMEOUT", "Pemrosesan terhenti dan dapat dicoba ulang.", "stale job"
            )
        self.stdout.write(self.style.SUCCESS(f"{len(ids)} pekerjaan stale dipulihkan."))
