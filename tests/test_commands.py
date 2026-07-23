import sys
import types
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.jobs.models import AdminAuditLog, ImageJob
from apps.jobs.services import transition
from apps.jobs.tasks import cleanup_expired, record_worker_heartbeat, recover_stale
from tests.conftest import image_bytes


@pytest.mark.django_db
def test_operational_report_commands(capsys):
    call_command("storage_report")
    call_command("doctor")
    call_command("migrate_locked")
    output = capsys.readouterr().out
    assert "Backend" in output and "database" in output


@pytest.mark.django_db
def test_purge_audit_log_requires_confirmation(admin_user):
    AdminAuditLog.objects.create(actor=admin_user, action="old", object_type="test", object_identifier="1")
    with pytest.raises(CommandError):
        call_command("purge_audit_logs", older_than_days=0)
    call_command("purge_audit_logs", older_than_days=0, confirm=True)
    assert not AdminAuditLog.objects.exists()


@pytest.mark.django_db
def test_recover_stale_command_and_task(owned_job, settings):
    settings.STALE_PROCESSING_MINUTES = 1
    transition(owned_job, ImageJob.Status.PROCESSING)
    ImageJob.objects.filter(pk=owned_job.pk).update(
        processing_started_at=timezone.now() - timedelta(minutes=5)
    )
    call_command("recover_stale_jobs")
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.FAILED

    owned_job.status = ImageJob.Status.QUEUED
    owned_job.failed_at = None
    owned_job.save()
    transition(owned_job, ImageJob.Status.PROCESSING)
    ImageJob.objects.filter(pk=owned_job.pk).update(
        processing_started_at=timezone.now() - timedelta(minutes=5)
    )
    assert recover_stale.run()["recovered"] == 1


@pytest.mark.django_db
def test_cleanup_task_and_heartbeat(owned_job):
    owned_job.expires_at = timezone.now() - timedelta(hours=1)
    owned_job.save()
    assert cleanup_expired.run()["cleaned"] == 1
    heartbeat = record_worker_heartbeat.run()
    assert heartbeat


@pytest.mark.django_db
def test_benchmark_command(tmp_path, monkeypatch, capsys):
    path = tmp_path / "image.png"
    path.write_bytes(image_bytes("PNG"))
    fake = types.ModuleType("rembg")
    fake.new_session = lambda model: object()
    fake.remove = lambda raw, session, force_return_bytes: raw
    monkeypatch.setitem(sys.modules, "rembg", fake)
    monkeypatch.setattr(
        "apps.core.management.commands.benchmark_processing.get_rembg_session", lambda model: object()
    )
    call_command("benchmark_processing", input=str(path), runs=2, model="u2netp")
    assert "Waktu proses" in capsys.readouterr().out


@pytest.mark.django_db
def test_benchmark_missing_input():
    with pytest.raises(CommandError):
        call_command("benchmark_processing", input="does-not-exist.png")
