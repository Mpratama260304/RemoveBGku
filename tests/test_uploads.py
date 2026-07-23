import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.jobs.exceptions import FileTooLargeError, InvalidImageError
from apps.jobs.validators import sanitize_filename, validate_and_normalize
from tests.conftest import image_bytes


@pytest.mark.parametrize(
    ("fmt", "name", "mime"),
    [
        ("JPEG", "photo.jpg", "image/jpeg"),
        ("PNG", "photo.png", "image/png"),
        ("WEBP", "photo.webp", "image/webp"),
    ],
)
def test_valid_image_formats(fmt, name, mime):
    raw = image_bytes(fmt)
    result = validate_and_normalize(SimpleUploadedFile(name, raw, content_type=mime))
    assert result.mime_type == mime
    assert result.width == 64 and result.height == 64
    assert len(result.sha256) == 64


@pytest.mark.parametrize(
    "uploaded",
    [
        SimpleUploadedFile("empty.png", b"", content_type="image/png"),
        SimpleUploadedFile("malware.png", b"MZ executable", content_type="image/png"),
        SimpleUploadedFile("vector.svg", b"<svg></svg>", content_type="image/svg+xml"),
        SimpleUploadedFile("wrong.jpg", image_bytes("PNG"), content_type="image/jpeg"),
    ],
)
def test_invalid_files_rejected(uploaded):
    with pytest.raises(InvalidImageError):
        validate_and_normalize(uploaded)


def test_file_too_large(settings):
    settings.UPLOAD_MAX_BYTES = 10
    uploaded = SimpleUploadedFile("large.png", image_bytes("PNG"), content_type="image/png")
    with pytest.raises(FileTooLargeError):
        validate_and_normalize(uploaded)


def test_too_small_and_too_many_pixels(settings):
    with pytest.raises(InvalidImageError):
        validate_and_normalize(SimpleUploadedFile("small.png", image_bytes("PNG", (8, 8))))
    settings.MAX_IMAGE_PIXELS = 1000
    with pytest.raises(InvalidImageError):
        validate_and_normalize(SimpleUploadedFile("large.png", image_bytes("PNG", (64, 64))))


def test_animated_image_rejected():
    output = io.BytesIO()
    frames = [Image.new("RGB", (64, 64), color) for color in ("red", "blue")]
    frames[0].save(output, "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0)
    with pytest.raises(InvalidImageError):
        validate_and_normalize(SimpleUploadedFile("animated.webp", output.getvalue()))


def test_path_traversal_is_sanitized():
    assert sanitize_filename("../../secret/photo.png") == "photo.png"


def test_exif_is_removed_and_orientation_normalized():
    raw = image_bytes("JPEG", (80, 60))
    result = validate_and_normalize(SimpleUploadedFile("camera.jpg", raw))
    with Image.open(io.BytesIO(result.content.read())) as image:
        assert not image.getexif()
