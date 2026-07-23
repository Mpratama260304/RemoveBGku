import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.jobs.models import ImageJob, JobEvent, SiteConfiguration
from apps.jobs.services import transition
from tests.conftest import image_bytes


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/history/", "/privacy/", "/terms/", "/faq/"])
def test_public_pages(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert b"HapusBackground" in response.content


@pytest.mark.django_db
def test_job_status_and_assets(client, owned_job):
    response = client.get(reverse("jobs:status", args=[owned_job.public_id]))
    assert response.json()["status"] == "queued"
    original = client.get(reverse("jobs:asset", args=[owned_job.public_id, "original"]))
    assert original.status_code == 200 and original["Content-Type"] == "image/png"
    assert client.get(reverse("jobs:asset", args=[owned_job.public_id, "unknown"])).status_code == 404

    transition(owned_job, ImageJob.Status.PROCESSING)
    owned_job.result_file.save("result.png", ContentFile(image_bytes("PNG")), save=False)
    transition(owned_job, ImageJob.Status.SUCCEEDED)
    response = client.get(reverse("jobs:status", args=[owned_job.public_id]))
    assert response.json()["terminal"] is True
    assert response.json()["result_url"]


@pytest.mark.django_db
def test_api_get_and_delete(client, owned_job):
    response = client.get(reverse("api:job-detail", args=[owned_job.public_id]))
    assert response.status_code == 200
    response = client.delete(reverse("api:job-detail", args=[owned_job.public_id]))
    assert response.status_code == 204
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.FILES_DELETED


@pytest.mark.django_db
def test_upload_invalid_response(client):
    response = client.post(reverse("jobs:upload"), {"image": SimpleUploadedFile("bad.png", b"not an image")})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_FILE_TYPE"


@pytest.mark.django_db
def test_retry_view_conflict_then_success(client, owned_job, monkeypatch):
    assert client.post(reverse("jobs:retry", args=[owned_job.public_id])).status_code == 409
    transition(owned_job, ImageJob.Status.FAILED)
    monkeypatch.setattr(
        "apps.jobs.tasks.process_image_job.delay", lambda job_id: type("R", (), {"id": "task"})()
    )
    response = client.post(reverse("jobs:retry", args=[owned_job.public_id]), HTTP_ACCEPT="application/json")
    assert response.status_code == 202


@pytest.mark.django_db
def test_failed_detail_shows_public_message(client, owned_job):
    owned_job.error_message_public = "Pesan aman"
    owned_job.save()
    transition(owned_job, ImageJob.Status.FAILED)
    response = client.get(reverse("jobs:detail", args=[owned_job.public_id]))
    assert b"Pesan aman" in response.content


@pytest.mark.django_db
def test_maintenance_mode_and_staff_bypass(client, admin_user):
    config = SiteConfiguration.get_solo()
    config.maintenance_mode = True
    config.save()
    assert client.get("/").status_code == 503
    client.force_login(admin_user)
    assert client.get("/").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_upload_rate_limit(client, settings, monkeypatch):
    settings.UPLOAD_RATE_LIMIT_PER_HOUR = 1
    config = SiteConfiguration.get_solo()
    config.upload_rate_limit_per_hour = 1
    config.save()
    monkeypatch.setattr(
        "apps.jobs.tasks.process_image_job.delay", lambda job_id: type("R", (), {"id": "task"})()
    )
    first = client.post(reverse("jobs:upload"), {"image": SimpleUploadedFile("one.png", image_bytes("PNG"))})
    second = client.post(reverse("jobs:upload"), {"image": SimpleUploadedFile("two.png", image_bytes("PNG"))})
    assert first.status_code == 202
    assert second.status_code == 429


@pytest.mark.django_db
def test_history_pagination(client, owned_job):
    response = client.get("/history/?page=999")
    assert response.status_code == 200
    assert owned_job.original_filename.encode() in response.content


@pytest.mark.django_db
def test_download_records_event(client, owned_job):
    transition(owned_job, ImageJob.Status.PROCESSING)
    owned_job.result_file.save("result.png", ContentFile(image_bytes("PNG")), save=False)
    transition(owned_job, ImageJob.Status.SUCCEEDED)
    assert client.get(reverse("jobs:download", args=[owned_job.public_id])).status_code == 200
    assert JobEvent.objects.filter(job=owned_job, event_type="downloaded").exists()
