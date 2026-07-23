from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.jobs.models import ImageJob


class Command(BaseCommand):
    help = "Menampilkan ringkasan metadata penggunaan storage tanpa memindai seluruh bucket."

    def handle(self, *args, **options):
        totals = ImageJob.objects.exclude(status=ImageJob.Status.FILES_DELETED).aggregate(
            originals=Sum("original_size_bytes"), results=Sum("result_size_bytes")
        )
        self.stdout.write(
            f"Backend: {settings.STORAGE_BACKEND if hasattr(settings, 'STORAGE_BACKEND') else 'local'}"
        )
        self.stdout.write(f"Original aktif: {totals['originals'] or 0} byte")
        self.stdout.write(f"Hasil aktif: {totals['results'] or 0} byte")
