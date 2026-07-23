import io
from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from apps.core.security import hash_session_key
from apps.jobs.models import ImageJob


def image_bytes(fmt="PNG", size=(64, 64), color=(200, 30, 50, 255)):
    output = io.BytesIO()
    image = Image.new("RGBA", size, color)
    if fmt == "JPEG":
        image.convert("RGB").save(output, fmt)
    else:
        image.save(output, fmt)
    return output.getvalue()


@pytest.fixture
def png_bytes():
    return image_bytes()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        "staff@example.com", "a-long-test-password", full_name="Staff"
    )


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_superuser(
        "admin@example.com", "a-long-test-password", full_name="Admin"
    )


@pytest.fixture
def owned_job(client, png_bytes):
    session = client.session
    session["started"] = True
    session.save()
    return ImageJob.objects.create(
        original_file=ContentFile(png_bytes, name="source.png"),
        original_filename="source.png",
        safe_download_filename="source-tanpa-background.png",
        original_mime_type="image/png",
        original_size_bytes=len(png_bytes),
        original_width=64,
        original_height=64,
        original_sha256="a" * 64,
        model_name="u2netp",
        session_owner_hash=hash_session_key(session.session_key),
        client_ip_hash="b" * 64,
        expires_at=timezone.now() + timedelta(hours=24),
    )
