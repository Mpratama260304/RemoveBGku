from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _dated_path(prefix: str, instance, extension: str) -> str:
    date = timezone.now()
    return f"{prefix}/{date:%Y/%m/%d}/{instance.id}.{extension}"


def original_upload_path(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return _dated_path("originals", instance, ext)


def result_upload_path(instance, filename: str) -> str:
    return _dated_path("results", instance, "png")


def thumbnail_upload_path(instance, filename: str) -> str:
    return _dated_path("thumbnails", instance, "webp")


class ImageJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Menunggu antrean"
        PROCESSING = "processing", "Sedang diproses"
        SUCCEEDED = "succeeded", "Selesai"
        FAILED = "failed", "Gagal"
        CANCELED = "canceled", "Dibatalkan"
        EXPIRED = "expired", "Kedaluwarsa"
        FILES_DELETED = "files_deleted", "File dihapus"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    original_file = models.FileField(upload_to=original_upload_path, max_length=500)
    result_file = models.FileField(upload_to=result_upload_path, max_length=500, blank=True)
    thumbnail_file = models.FileField(upload_to=thumbnail_upload_path, max_length=500, blank=True)
    original_filename = models.CharField(max_length=255)
    safe_download_filename = models.CharField(max_length=255)
    original_mime_type = models.CharField(max_length=80)
    result_mime_type = models.CharField(max_length=80, blank=True)
    original_size_bytes = models.PositiveBigIntegerField(default=0)
    result_size_bytes = models.PositiveBigIntegerField(default=0)
    original_width = models.PositiveIntegerField(default=0)
    original_height = models.PositiveIntegerField(default=0)
    result_width = models.PositiveIntegerField(default=0)
    result_height = models.PositiveIntegerField(default=0)
    model_name = models.CharField(max_length=80, db_index=True)
    session_owner_hash = models.CharField(max_length=64, db_index=True)
    client_ip_hash = models.CharField(max_length=64)
    user_agent_truncated = models.CharField(max_length=255, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    cancel_requested = models.BooleanField(default=False)
    error_code = models.CharField(max_length=80, blank=True)
    error_message_public = models.CharField(max_length=500, blank=True)
    error_message_internal = models.TextField(blank=True)
    queued_at = models.DateTimeField(default=timezone.now)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    files_deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    processing_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    original_sha256 = models.CharField(max_length=64)
    result_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="jobs_status_created_idx"),
            models.Index(fields=["session_owner_hash", "created_at"], name="jobs_owner_created_idx"),
        ]
        permissions = [
            ("can_view_internal_errors", "Dapat melihat error internal"),
            ("can_retry_job", "Dapat mencoba ulang job"),
            ("can_cancel_job", "Dapat membatalkan job"),
            ("can_delete_job_files", "Dapat menghapus file job"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="succeeded", completed_at__isnull=False)
                | ~models.Q(status="succeeded"),
                name="succeeded_has_completed_at",
            ),
            models.CheckConstraint(
                condition=models.Q(status="failed", failed_at__isnull=False) | ~models.Q(status="failed"),
                name="failed_has_failed_at",
            ),
        ]

    def __str__(self) -> str:
        return f"{str(self.public_id)[:8]} · {self.original_filename}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=settings.JOB_RETENTION_HOURS)
        super().save(*args, **kwargs)

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.Status.SUCCEEDED,
            self.Status.FAILED,
            self.Status.CANCELED,
            self.Status.EXPIRED,
            self.Status.FILES_DELETED,
        }

    @property
    def mode_label(self) -> str:
        return "Kualitas" if self.model_name == "isnet-general-use" else "Cepat"


class JobEvent(models.Model):
    job = models.ForeignKey(ImageJob, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80, db_index=True)
    message = models.CharField(max_length=500)
    safe_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.job_id}"


class SiteConfiguration(models.Model):
    site_name = models.CharField(max_length=100, default="HapusBackground")
    site_tagline = models.CharField(max_length=255, default="Hapus latar belakang gambar dengan mudah")
    public_upload_enabled = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.CharField(
        max_length=500, default="Kami sedang melakukan pemeliharaan singkat."
    )
    default_model = models.CharField(max_length=80, default="u2netp")
    allowed_models = models.JSONField(default=list, blank=True)
    upload_max_bytes = models.PositiveIntegerField(default=10 * 1024 * 1024)
    max_image_pixels = models.PositiveIntegerField(default=36_000_000)
    retention_hours = models.PositiveIntegerField(default=24)
    max_active_jobs_per_session = models.PositiveSmallIntegerField(default=3)
    max_queue_size = models.PositiveSmallIntegerField(default=50)
    upload_rate_limit_per_hour = models.PositiveSmallIntegerField(default=10)
    show_public_history = models.BooleanField(default=True)
    privacy_notice = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "konfigurasi situs"
        verbose_name_plural = "konfigurasi situs"
        permissions = [("can_manage_site_configuration", "Dapat mengelola konfigurasi situs")]

    def __str__(self) -> str:
        return "Konfigurasi situs"

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        result = super().save(*args, **kwargs)
        cache.delete("site_configuration")
        return result

    @classmethod
    def get_solo(cls) -> SiteConfiguration:
        cached = cache.get("site_configuration")
        if cached and cls.objects.filter(pk=cached.pk).exists():
            return cached
        if cached:
            cache.delete("site_configuration")
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "site_name": settings.SITE_NAME,
                "site_tagline": settings.SITE_TAGLINE,
                "allowed_models": settings.ALLOWED_REMBG_MODELS,
                "default_model": settings.DEFAULT_REMBG_MODEL,
                "upload_max_bytes": settings.UPLOAD_MAX_BYTES,
                "max_image_pixels": settings.MAX_IMAGE_PIXELS,
                "retention_hours": settings.JOB_RETENTION_HOURS,
                "max_active_jobs_per_session": settings.MAX_ACTIVE_JOBS_PER_SESSION,
                "max_queue_size": settings.MAX_QUEUE_SIZE,
                "upload_rate_limit_per_hour": settings.UPLOAD_RATE_LIMIT_PER_HOUR,
            },
        )
        cache.set("site_configuration", obj, 45)
        return obj

    def clean(self):
        errors = {}
        hard_limits = {
            "upload_max_bytes": settings.UPLOAD_MAX_BYTES,
            "max_image_pixels": settings.MAX_IMAGE_PIXELS,
            "max_active_jobs_per_session": settings.MAX_ACTIVE_JOBS_PER_SESSION,
            "max_queue_size": settings.MAX_QUEUE_SIZE,
            "upload_rate_limit_per_hour": settings.UPLOAD_RATE_LIMIT_PER_HOUR,
        }
        for field, limit in hard_limits.items():
            if getattr(self, field) > limit:
                errors[field] = f"Tidak boleh melebihi hard limit environment ({limit})."
        unknown = set(self.allowed_models) - set(settings.ALLOWED_REMBG_MODELS)
        if unknown:
            errors["allowed_models"] = "Model tidak diizinkan oleh environment."
        if self.default_model not in self.allowed_models:
            errors["default_model"] = "Model default wajib ada dalam daftar model yang diizinkan."
        if errors:
            raise ValidationError(errors)


class AdminAuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100)
    object_identifier = models.CharField(max_length=255, db_index=True)
    client_ip_hash = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("can_view_audit_log", "Dapat melihat audit log")]

    def __str__(self) -> str:
        return f"{self.action} · {self.object_identifier}"
