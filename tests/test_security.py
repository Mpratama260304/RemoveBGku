import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.security import hash_client_ip
from apps.jobs.models import SiteConfiguration


@pytest.mark.django_db
def test_security_headers(client):
    response = client.get("/")
    assert response["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response["Content-Security-Policy"]
    assert response["Permissions-Policy"]


@pytest.mark.django_db
def test_csrf_enforced(django_user_model):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    assert client.post(reverse("jobs:upload"), {}).status_code == 403


@pytest.mark.django_db
def test_site_configuration_singleton_and_hard_limits(settings):
    config = SiteConfiguration.get_solo()
    settings.UPLOAD_MAX_BYTES = 100
    config.upload_max_bytes = 101
    with pytest.raises(ValidationError):
        config.full_clean()
    config.refresh_from_db()
    config.upload_max_bytes = 100
    config.pk = 2
    config.site_name = "Second"
    config.save()
    assert SiteConfiguration.objects.count() == 1


def test_ip_is_hashed(rf):
    request = rf.get("/", REMOTE_ADDR="192.0.2.10")
    hashed = hash_client_ip(request)
    assert hashed != "192.0.2.10" and len(hashed) == 64
