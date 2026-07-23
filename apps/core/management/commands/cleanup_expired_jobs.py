from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import ImageJob
from apps.jobs.services import delete_job_files


class Command(BaseCommand):
    help = "Menghapus file pekerjaan yang kedaluwarsa secara idempoten."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--purge-records-older-than-days", type=int)

    def handle(self, *args, **options):
        queryset = ImageJob.objects.filter(expires_at__lte=timezone.now(), is_pinned=False).exclude(
            status=ImageJob.Status.FILES_DELETED
        )[: max(1, min(options["batch_size"], 1000))]
        ids = list(queryset.values_list("pk", flat=True))
        if options["dry_run"]:
            self.stdout.write(f"Dry-run: {len(ids)} pekerjaan akan dibersihkan.")
            return
        cleaned = failed = bytes_deleted = 0
        for job_id in ids:
            try:
                with transaction.atomic():
                    job = ImageJob.objects.select_for_update().get(pk=job_id)
                    if job.is_pinned or job.expires_at > timezone.now():
                        continue
                    bytes_deleted += delete_job_files(job)
                    cleaned += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Gagal membersihkan job {job_id}: {type(exc).__name__}")
        purged = 0
        if days := options.get("purge_records_older_than_days"):
            cutoff = timezone.now() - timedelta(days=days)
            purged, _ = ImageJob.objects.filter(
                status=ImageJob.Status.FILES_DELETED, files_deleted_at__lt=cutoff
            ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup selesai: {cleaned} job, {bytes_deleted} byte, "
                f"{failed} gagal, {purged} record dipurge."
            )
        )
