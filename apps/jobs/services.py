from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.rate_limit import consume
from apps.core.security import ensure_session_owner, hash_client_ip

from .exceptions import InvalidTransitionError, QueueFullError, RateLimitedError, WorkerUnavailableError
from .models import AdminAuditLog, ImageJob, JobEvent, SiteConfiguration
from .validators import validate_and_normalize

logger = logging.getLogger(__name__)

TRANSITIONS = {
    ImageJob.Status.QUEUED: {ImageJob.Status.PROCESSING, ImageJob.Status.CANCELED, ImageJob.Status.FAILED},
    ImageJob.Status.PROCESSING: {ImageJob.Status.SUCCEEDED, ImageJob.Status.FAILED, ImageJob.Status.CANCELED},
    ImageJob.Status.FAILED: {ImageJob.Status.QUEUED, ImageJob.Status.EXPIRED, ImageJob.Status.FILES_DELETED},
    ImageJob.Status.CANCELED: {
        ImageJob.Status.QUEUED,
        ImageJob.Status.EXPIRED,
        ImageJob.Status.FILES_DELETED,
    },
    ImageJob.Status.SUCCEEDED: {ImageJob.Status.EXPIRED, ImageJob.Status.FILES_DELETED},
    ImageJob.Status.EXPIRED: {ImageJob.Status.FILES_DELETED},
    ImageJob.Status.FILES_DELETED: set(),
}


def transition(job: ImageJob, target: str, *, message: str = "", event_type: str | None = None) -> ImageJob:
    if target not in TRANSITIONS.get(job.status, set()):
        raise InvalidTransitionError(f"{job.status} -> {target}")
    now = timezone.now()
    job.status = target
    if target == ImageJob.Status.PROCESSING:
        job.processing_started_at = now
        job.attempt_count += 1
    elif target == ImageJob.Status.SUCCEEDED:
        job.completed_at = now
    elif target == ImageJob.Status.FAILED:
        job.failed_at = now
    elif target == ImageJob.Status.FILES_DELETED:
        job.files_deleted_at = now
    job.save()
    JobEvent.objects.create(
        job=job,
        event_type=event_type or target,
        message=message or job.get_status_display(),
    )
    return job


def owner_hash_for_request(request) -> str:
    return ensure_session_owner(request)


def get_owned_job(request, public_id) -> ImageJob:
    owner_hash = owner_hash_for_request(request)
    query = ImageJob.objects.filter(public_id=public_id)
    if getattr(request.user, "is_staff", False):
        return query.get()
    return query.get(session_owner_hash=owner_hash)


def _check_capacity(request, config: SiteConfiguration) -> tuple[str, str]:
    owner = owner_hash_for_request(request)
    ip_hash = hash_client_ip(request)
    if not config.public_upload_enabled:
        raise WorkerUnavailableError()
    session_limit = consume(f"upload-session:{owner}", config.upload_rate_limit_per_hour, 3600)
    ip_limit = consume(f"upload-ip:{ip_hash}", config.upload_rate_limit_per_hour * 2, 3600)
    if not session_limit.allowed or not ip_limit.allowed:
        raise RateLimitedError()
    active = ImageJob.objects.filter(
        session_owner_hash=owner,
        status__in=[ImageJob.Status.QUEUED, ImageJob.Status.PROCESSING],
    ).count()
    if active >= config.max_active_jobs_per_session:
        raise RateLimitedError()
    queued = ImageJob.objects.filter(status=ImageJob.Status.QUEUED).count()
    if queued >= config.max_queue_size:
        raise QueueFullError()
    if not settings.CELERY_TASK_ALWAYS_EAGER and cache.get("worker:heartbeat") is None:
        raise WorkerUnavailableError()
    return owner, ip_hash


def create_job(request, uploaded, model_name: str) -> ImageJob:
    config = SiteConfiguration.get_solo()
    owner, ip_hash = _check_capacity(request, config)
    allowed = set(config.allowed_models) & set(settings.ALLOWED_REMBG_MODELS)
    if model_name not in allowed:
        model_name = config.default_model if config.default_model in allowed else settings.DEFAULT_REMBG_MODEL
    validated = validate_and_normalize(uploaded, max_bytes=config.upload_max_bytes)
    with transaction.atomic():
        job = ImageJob.objects.create(
            original_file=validated.content,
            original_filename=validated.filename,
            safe_download_filename=validated.safe_download_filename,
            original_mime_type=validated.mime_type,
            original_size_bytes=validated.size,
            original_width=validated.width,
            original_height=validated.height,
            original_sha256=validated.sha256,
            model_name=model_name,
            session_owner_hash=owner,
            client_ip_hash=ip_hash,
            user_agent_truncated=request.META.get("HTTP_USER_AGENT", "")[:255],
            expires_at=timezone.now() + timedelta(hours=config.retention_hours),
        )
        JobEvent.objects.bulk_create(
            [
                JobEvent(job=job, event_type="uploaded", message="Gambar diterima server."),
                JobEvent(job=job, event_type="queued", message="Pekerjaan masuk antrean."),
            ]
        )

        def enqueue():
            from .tasks import process_image_job

            result = process_image_job.delay(str(job.id))
            ImageJob.objects.filter(pk=job.pk).update(celery_task_id=result.id or "")

        transaction.on_commit(enqueue)
    return job


def retry_job(job: ImageJob, actor=None, client_ip_hash: str = "") -> ImageJob:
    with transaction.atomic():
        job = ImageJob.objects.select_for_update().get(pk=job.pk)
        if not job.original_file or job.attempt_count >= 3:
            raise InvalidTransitionError()
        transition(
            job,
            ImageJob.Status.QUEUED,
            message="Pekerjaan dimasukkan ulang ke antrean.",
            event_type="retried",
        )
        job.error_code = job.error_message_public = job.error_message_internal = ""
        job.failed_at = None
        job.cancel_requested = False
        job.queued_at = timezone.now()
        job.save()
        if actor:
            AdminAuditLog.objects.create(
                actor=actor,
                action="retry_job",
                object_type="ImageJob",
                object_identifier=str(job.public_id),
                client_ip_hash=client_ip_hash,
            )
        transaction.on_commit(lambda: _enqueue_existing(job.pk))
    return job


def _enqueue_existing(job_id):
    from .tasks import process_image_job

    result = process_image_job.delay(str(job_id))
    ImageJob.objects.filter(pk=job_id).update(celery_task_id=result.id or "")


def delete_job_files(job: ImageJob, *, actor=None, client_ip_hash: str = "") -> int:
    deleted_bytes = job.original_size_bytes + job.result_size_bytes
    if job.status in {ImageJob.Status.QUEUED, ImageJob.Status.PROCESSING}:
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested", "updated_at"])
        transition(
            job,
            ImageJob.Status.CANCELED,
            message="Pekerjaan dibatalkan sebelum file dihapus.",
            event_type="canceled",
        )
    for field_name in ("original_file", "result_file", "thumbnail_file"):
        field = getattr(job, field_name)
        if field:
            field.delete(save=False)
            setattr(job, field_name, "")
    if job.status != ImageJob.Status.FILES_DELETED:
        transition(
            job,
            ImageJob.Status.FILES_DELETED,
            message="File pekerjaan telah dihapus.",
            event_type="files_deleted",
        )
    else:
        job.files_deleted_at = job.files_deleted_at or timezone.now()
        job.save()
    if actor:
        AdminAuditLog.objects.create(
            actor=actor,
            action="delete_job_files",
            object_type="ImageJob",
            object_identifier=str(job.public_id),
            client_ip_hash=client_ip_hash,
        )
    return deleted_bytes
