from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.jobs.models import AdminAuditLog


class Command(BaseCommand):
    help = "Menghapus audit log lama dengan konfirmasi eksplisit."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-days", type=int, required=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Tambahkan --confirm untuk menjalankan penghapusan.")
        cutoff = timezone.now() - timedelta(days=options["older_than_days"])
        count, _ = AdminAuditLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"{count} audit log dihapus."))
