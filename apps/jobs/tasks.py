from __future__ import annotations

import io
import logging
import time
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import heartbeat_sent, worker_ready
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image

from .models import ImageJob
from .services import delete_job_files, transition
from .validators import streaming_sha256, validate_and_normalize

logger = logging.getLogger(__name__)
_sessions: dict[str, object] = {}


def _set_worker_heartbeat() -> str:
    value = timezone.now().isoformat()
    cache.set("worker:heartbeat", value, timeout=90)
    return value


@worker_ready.connect
@heartbeat_sent.connect
def worker_heartbeat_signal(**kwargs):
    _set_worker_heartbeat()


def get_rembg_session(model_name: str):
    if model_name not in settings.ALLOWED_REMBG_MODELS:
        raise ValueError("Model tidak diizinkan")
    if model_name not in _sessions:
        from rembg import new_session

        _sessions[model_name] = new_session(model_name)
    return _sessions[model_name]


def _mark_failed(job_id, code: str, public_message: str, internal: str = "") -> None:
    with transaction.atomic():
        job = ImageJob.objects.select_for_update().get(pk=job_id)
        if job.status == ImageJob.Status.PROCESSING:
            job.error_code = code
            job.error_message_public = public_message
            job.error_message_internal = internal[:4000]
            transition(job, ImageJob.Status.FAILED, message=public_message, event_type="processing_failed")


@shared_task(bind=True, autoretry_for=(), max_retries=2)
def process_image_job(self, job_id: str):
    started = time.monotonic()
    try:
        with transaction.atomic():
            job = ImageJob.objects.select_for_update().get(pk=job_id)
            if job.status != ImageJob.Status.QUEUED or job.cancel_requested:
                return {"status": "skipped"}
            transition(
                job,
                ImageJob.Status.PROCESSING,
                message="Model AI mulai memproses gambar.",
                event_type="processing_started",
            )

        with job.original_file.open("rb") as source:
            raw = source.read(settings.UPLOAD_MAX_BYTES + 1)
        if len(raw) > settings.UPLOAD_MAX_BYTES:
            raise ValueError("source exceeds hard size limit")
        revalidated = validate_and_normalize(
            SimpleUploadedFile(job.original_filename, raw, content_type=job.original_mime_type)
        )
        raw = revalidated.content.read()

        from rembg import remove

        result_bytes = remove(raw, session=get_rembg_session(job.model_name), force_return_bytes=True)
        with Image.open(io.BytesIO(result_bytes)) as result_image:
            result_image.load()
            if "A" not in result_image.getbands():
                raise ValueError("result missing alpha")
            rgba = result_image.convert("RGBA")
            output = io.BytesIO()
            rgba.save(output, "PNG", optimize=True)
            output_bytes = output.getvalue()
            thumbnail = rgba.copy()
            thumbnail.thumbnail((512, 512), Image.Resampling.LANCZOS)
            thumb_out = io.BytesIO()
            thumbnail.save(thumb_out, "WEBP", quality=82, method=4)
            width, height = rgba.size

        with transaction.atomic():
            job = ImageJob.objects.select_for_update().get(pk=job_id)
            if job.status != ImageJob.Status.PROCESSING:
                return {"status": "state_changed"}
            job.result_file.save(f"{job.id}.png", ContentFile(output_bytes), save=False)
            job.thumbnail_file.save(f"{job.id}.webp", ContentFile(thumb_out.getvalue()), save=False)
            job.result_mime_type = "image/png"
            job.result_size_bytes = len(output_bytes)
            job.result_width = width
            job.result_height = height
            job.result_sha256 = streaming_sha256(output_bytes)
            job.processing_duration_ms = int((time.monotonic() - started) * 1000)
            transition(
                job,
                ImageJob.Status.SUCCEEDED,
                message="Background berhasil dihapus.",
                event_type="processing_succeeded",
            )
        return {"status": "succeeded"}
    except SoftTimeLimitExceeded:
        _mark_failed(
            job_id, "PROCESSING_TIMEOUT", "Pemrosesan melewati batas waktu. Coba gambar yang lebih kecil."
        )
        return {"status": "failed"}
    except Exception as exc:
        logger.exception("Pemrosesan gambar gagal", extra={"job_id": job_id})
        _mark_failed(
            job_id, "PROCESSING_FAILED", "Gambar tidak dapat diproses. Silakan coba lagi.", repr(exc)
        )
        return {"status": "failed"}


@shared_task
def cleanup_expired() -> dict[str, int]:
    count = 0
    for job in ImageJob.objects.filter(expires_at__lte=timezone.now(), is_pinned=False).exclude(
        status=ImageJob.Status.FILES_DELETED
    )[:100]:
        try:
            delete_job_files(job)
            count += 1
        except Exception:
            logger.exception("Cleanup gagal", extra={"job_id": job.pk})
    return {"cleaned": count}


@shared_task
def recover_stale() -> dict[str, int]:
    cutoff = timezone.now() - timedelta(minutes=settings.STALE_PROCESSING_MINUTES)
    count = 0
    for job in ImageJob.objects.filter(status=ImageJob.Status.PROCESSING, processing_started_at__lt=cutoff):
        _mark_failed(
            job.pk,
            "PROCESSING_TIMEOUT",
            "Pemrosesan terhenti dan dapat dicoba ulang.",
            "stale processing job",
        )
        count += 1
    return {"recovered": count}


@shared_task
def record_worker_heartbeat() -> str:
    return _set_worker_heartbeat()
