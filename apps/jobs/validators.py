from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename
from PIL import Image, ImageOps, UnidentifiedImageError

from .exceptions import FileTooLargeError, InvalidImageError

FORMAT_MAP = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
EXTENSIONS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


@dataclass
class ValidatedImage:
    content: ContentFile
    filename: str
    safe_download_filename: str
    mime_type: str
    width: int
    height: int
    size: int
    sha256: str


def sanitize_filename(name: str) -> str:
    safe = get_valid_filename(Path(name).name)[:220]
    return safe or "gambar"


def _read_limited(uploaded, max_bytes: int) -> bytes:
    output = io.BytesIO()
    total = 0
    while chunk := uploaded.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError()
        output.write(chunk)
    uploaded.seek(0)
    return output.getvalue()


def streaming_sha256(data: bytes) -> str:
    digest = hashlib.sha256()
    view = memoryview(data)
    for offset in range(0, len(view), 1024 * 1024):
        digest.update(view[offset : offset + 1024 * 1024])
    return digest.hexdigest()


def validate_and_normalize(uploaded, *, max_bytes: int | None = None) -> ValidatedImage:
    max_bytes = min(max_bytes or settings.UPLOAD_MAX_BYTES, settings.UPLOAD_MAX_BYTES)
    if not uploaded or getattr(uploaded, "size", 0) <= 0:
        raise InvalidImageError("empty")
    if uploaded.size > max_bytes:
        raise FileTooLargeError()
    raw = _read_limited(uploaded, max_bytes)
    safe_name = sanitize_filename(uploaded.name)
    ext = Path(safe_name).suffix.lower()
    if ext not in EXTENSIONS:
        raise InvalidImageError("extension")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected_format = probe.format
            if detected_format not in FORMAT_MAP or EXTENSIONS[ext] != detected_format:
                raise InvalidImageError("mismatch")
            if getattr(probe, "is_animated", False) or getattr(probe, "n_frames", 1) != 1:
                raise InvalidImageError("animated")
            width, height = probe.size
            if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
                raise InvalidImageError("too-small")
            if (
                width > settings.MAX_IMAGE_WIDTH
                or height > settings.MAX_IMAGE_HEIGHT
                or width * height > settings.MAX_IMAGE_PIXELS
            ):
                raise InvalidImageError("too-large")
            probe.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if (
                width > settings.MAX_IMAGE_WIDTH
                or height > settings.MAX_IMAGE_HEIGHT
                or width * height > settings.MAX_IMAGE_PIXELS
            ):
                raise InvalidImageError("too-large")
            image.load()
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            pixels = width * height
            if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
                raise InvalidImageError("too-small")
            if (
                width > settings.MAX_IMAGE_WIDTH
                or height > settings.MAX_IMAGE_HEIGHT
                or pixels > settings.MAX_IMAGE_PIXELS
            ):
                raise InvalidImageError("too-large")
            output = io.BytesIO()
            mime, normalized_ext = FORMAT_MAP[detected_format]
            if detected_format == "JPEG":
                image.convert("RGB").save(output, "JPEG", quality=95, optimize=True)
            elif detected_format == "PNG":
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(output, "PNG", optimize=True)
            else:
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(
                    output, "WEBP", quality=95, method=4
                )
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImageError("corrupt") from exc

    normalized = output.getvalue()
    stem = Path(safe_name).stem[:180] or "gambar"
    filename = f"{stem}{normalized_ext}"
    return ValidatedImage(
        content=ContentFile(normalized, name=filename),
        filename=filename,
        safe_download_filename=f"{stem}-tanpa-background.png",
        mime_type=mime,
        width=width,
        height=height,
        size=len(normalized),
        sha256=streaming_sha256(normalized),
    )
