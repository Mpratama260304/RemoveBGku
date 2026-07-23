import sys
import types

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.jobs.exceptions import InvalidTransitionError
from apps.jobs.models import ImageJob, JobEvent, SiteConfiguration
from apps.jobs.services import retry_job, transition
from apps.jobs.tasks import process_image_job
from tests.conftest import image_bytes


@pytest.mark.django_db
def test_state_machine_valid_and_invalid(owned_job):
    transition(owned_job, ImageJob.Status.PROCESSING)
    assert owned_job.status == ImageJob.Status.PROCESSING
    with pytest.raises(InvalidTransitionError):
        transition(owned_job, ImageJob.Status.QUEUED)


@pytest.mark.django_db
def test_session_ownership_blocks_other_browser(client, django_user_model, owned_job):
    assert client.get(reverse("jobs:detail", args=[owned_job.public_id])).status_code == 200
    other = client.__class__()
    assert other.get(reverse("jobs:detail", args=[owned_job.public_id])).status_code == 404
    admin = django_user_model.objects.create_superuser("viewer@example.com", "secret")
    other.force_login(admin)
    assert other.get(reverse("jobs:detail", args=[owned_job.public_id])).status_code == 200


@pytest.mark.django_db
def test_protected_download_and_delete(client, owned_job):
    owned_job.status = ImageJob.Status.PROCESSING
    owned_job.save()
    owned_job.result_file.save("result.png", ContentFile(image_bytes("PNG")), save=False)
    transition(owned_job, ImageJob.Status.SUCCEEDED)
    response = client.get(reverse("jobs:download", args=[owned_job.public_id]))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    other = client.__class__()
    assert other.get(reverse("jobs:download", args=[owned_job.public_id])).status_code == 404
    response = client.post(reverse("jobs:delete", args=[owned_job.public_id]))
    assert response.status_code == 302
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.FILES_DELETED


@pytest.mark.django_db(transaction=True)
def test_upload_creates_queued_job(client, monkeypatch):
    fake_result = types.SimpleNamespace(id="task-123")
    monkeypatch.setattr("apps.jobs.tasks.process_image_job.delay", lambda job_id: fake_result)
    SiteConfiguration.get_solo()
    response = client.post(
        reverse("jobs:upload"),
        {
            "image": SimpleUploadedFile("person.png", image_bytes("PNG"), content_type="image/png"),
            "mode": "u2netp",
        },
    )
    assert response.status_code == 202
    job = ImageJob.objects.get(public_id=response.json()["id"])
    assert job.status == ImageJob.Status.QUEUED
    assert list(job.events.values_list("event_type", flat=True)) == ["uploaded", "queued"]
    assert job.client_ip_hash and job.session_owner_hash


@pytest.mark.django_db
def test_process_task_succeeds_and_is_idempotent(owned_job, monkeypatch):
    output = image_bytes("PNG", color=(255, 0, 0, 0))
    fake = types.ModuleType("rembg")
    fake.remove = lambda raw, session, force_return_bytes: output
    fake.new_session = lambda model: object()
    monkeypatch.setitem(sys.modules, "rembg", fake)
    monkeypatch.setattr("apps.jobs.tasks.get_rembg_session", lambda model: object())
    result = process_image_job.run(str(owned_job.id))
    owned_job.refresh_from_db()
    assert result["status"] == "succeeded"
    assert owned_job.status == ImageJob.Status.SUCCEEDED
    assert owned_job.result_mime_type == "image/png" and owned_job.result_sha256
    assert process_image_job.run(str(owned_job.id))["status"] == "skipped"


@pytest.mark.django_db
def test_process_failure_is_safe(owned_job, monkeypatch):
    fake = types.ModuleType("rembg")
    fake.remove = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret-internal"))
    monkeypatch.setitem(sys.modules, "rembg", fake)
    monkeypatch.setattr("apps.jobs.tasks.get_rembg_session", lambda model: object())
    process_image_job.run(str(owned_job.id))
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.FAILED
    assert "secret-internal" not in owned_job.error_message_public
    assert "secret-internal" in owned_job.error_message_internal


@pytest.mark.django_db
def test_canceled_job_not_processed(owned_job):
    transition(owned_job, ImageJob.Status.CANCELED)
    assert process_image_job.run(str(owned_job.id))["status"] == "skipped"


@pytest.mark.django_db
def test_retry_failed_job(owned_job, monkeypatch):
    transition(owned_job, ImageJob.Status.FAILED)
    monkeypatch.setattr(
        "apps.jobs.tasks.process_image_job.delay", lambda job_id: types.SimpleNamespace(id="retry-id")
    )
    retry_job(owned_job)
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.QUEUED
    assert JobEvent.objects.filter(job=owned_job, event_type="retried").exists()
