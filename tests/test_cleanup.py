from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.jobs.models import ImageJob


@pytest.mark.django_db
def test_cleanup_expired_and_idempotent(owned_job):
    owned_job.expires_at = timezone.now() - timedelta(hours=1)
    owned_job.save()
    call_command("cleanup_expired_jobs")
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.FILES_DELETED
    call_command("cleanup_expired_jobs")


@pytest.mark.django_db
def test_cleanup_skips_pinned_and_dry_run(owned_job):
    owned_job.expires_at = timezone.now() - timedelta(hours=1)
    owned_job.is_pinned = True
    owned_job.save()
    call_command("cleanup_expired_jobs", dry_run=True)
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.QUEUED
    call_command("cleanup_expired_jobs")
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.QUEUED
