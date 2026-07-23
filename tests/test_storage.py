import pytest
from storages.backends.s3 import S3Storage

from apps.jobs.models import original_upload_path, result_upload_path, thumbnail_upload_path


def test_s3_backend_is_private_and_signed():
    storage = S3Storage(
        access_key="test-access",
        secret_key="test-secret",
        bucket_name="private-test-bucket",
        endpoint_url="https://objects.example.test",
        querystring_auth=True,
        querystring_expire=300,
        default_acl=None,
        file_overwrite=False,
    )
    assert storage.default_acl is None
    assert storage.querystring_auth is True
    assert storage.querystring_expire == 300
    assert storage.file_overwrite is False


@pytest.mark.django_db
def test_storage_paths_use_job_uuid(owned_job):
    original = original_upload_path(owned_job, "unsafe-name.png")
    result = result_upload_path(owned_job, "ignored.png")
    thumbnail = thumbnail_upload_path(owned_job, "ignored.webp")
    assert str(owned_job.id) in original
    assert str(owned_job.id) in result
    assert str(owned_job.id) in thumbnail
    assert "unsafe-name" not in original
