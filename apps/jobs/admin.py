import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.core.security import hash_client_ip

from .models import AdminAuditLog, ImageJob, JobEvent, SiteConfiguration
from .services import delete_job_files, retry_job, transition


class JobEventInline(admin.TabularInline):
    model = JobEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "message", "safe_metadata", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImageJob)
class ImageJobAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "original_filename",
        "status_badge",
        "mode",
        "dimensions",
        "duration",
        "attempt_count",
        "created_at",
        "expires_at",
        "is_pinned",
    )
    list_filter = ("status", "model_name", "is_pinned", "created_at", "expires_at")
    search_fields = ("public_id", "original_filename", "original_sha256", "result_sha256")
    date_hierarchy = "created_at"
    list_per_page = 50
    readonly_fields = [field.name for field in ImageJob._meta.fields] + ["original_preview", "result_preview"]
    inlines = (JobEventInline,)
    actions = (
        "retry_selected",
        "cancel_selected",
        "pin_selected",
        "unpin_selected",
        "delete_files_selected",
        "extend_day",
        "extend_week",
        "export_csv",
    )

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.public_id)[:8]

    @admin.display(description="Status")
    def status_badge(self, obj):
        return format_html(
            '<span class="status-pill status-{}">{}</span>', obj.status, obj.get_status_display()
        )

    @admin.display(description="Mode")
    def mode(self, obj):
        return obj.mode_label

    @admin.display(description="Dimensi")
    def dimensions(self, obj):
        return f"{obj.original_width}×{obj.original_height}"

    @admin.display(description="Durasi")
    def duration(self, obj):
        return f"{obj.processing_duration_ms / 1000:.2f} dtk" if obj.processing_duration_ms else "—"

    @admin.display(description="Preview original")
    def original_preview(self, obj):
        if not obj or not obj.original_file:
            return "—"
        url = reverse("jobs:asset", args=[obj.public_id, "original"])
        return format_html('<img class="admin-preview" src="{}" alt="Original">', url)

    @admin.display(description="Preview hasil")
    def result_preview(self, obj):
        if not obj or not obj.result_file:
            return "—"
        url = reverse("jobs:asset", args=[obj.public_id, "result"])
        return format_html('<img class="admin-preview" src="{}" alt="Hasil">', url)

    @admin.action(description="Coba ulang pekerjaan terpilih")
    def retry_selected(self, request, queryset):
        if not (request.user.is_superuser or request.user.has_perm("jobs.can_retry_job")):
            raise PermissionDenied
        done = 0
        for job in queryset.filter(status__in=[ImageJob.Status.FAILED, ImageJob.Status.CANCELED]):
            try:
                retry_job(job, actor=request.user, client_ip_hash=hash_client_ip(request))
                done += 1
            except Exception:
                continue
        self.message_user(request, f"{done} pekerjaan dimasukkan ulang.")

    @admin.action(description="Batalkan pekerjaan queued")
    def cancel_selected(self, request, queryset):
        if not (request.user.is_superuser or request.user.has_perm("jobs.can_cancel_job")):
            raise PermissionDenied
        done = 0
        for job in queryset.filter(status=ImageJob.Status.QUEUED):
            transition(
                job, ImageJob.Status.CANCELED, message="Dibatalkan administrator.", event_type="canceled"
            )
            AdminAuditLog.objects.create(
                actor=request.user,
                action="cancel_job",
                object_type="ImageJob",
                object_identifier=str(job.public_id),
                client_ip_hash=hash_client_ip(request),
            )
            done += 1
        self.message_user(request, f"{done} pekerjaan dibatalkan.")

    @admin.action(description="Pin pekerjaan terpilih")
    def pin_selected(self, request, queryset):
        count = 0
        for job in queryset.filter(is_pinned=False):
            job.is_pinned = True
            job.save(update_fields=["is_pinned", "updated_at"])
            JobEvent.objects.create(job=job, event_type="pinned", message="Pekerjaan dipin administrator.")
            self._audit(request, "pin_job", job)
            count += 1
        self.message_user(request, f"{count} pekerjaan dipin.")

    @admin.action(description="Lepas pin pekerjaan terpilih")
    def unpin_selected(self, request, queryset):
        count = 0
        for job in queryset.filter(is_pinned=True):
            job.is_pinned = False
            job.save(update_fields=["is_pinned", "updated_at"])
            JobEvent.objects.create(job=job, event_type="unpinned", message="Pin pekerjaan dilepas.")
            self._audit(request, "unpin_job", job)
            count += 1
        self.message_user(request, f"{count} pin dilepas.")

    @admin.action(description="Hapus file pekerjaan terpilih")
    def delete_files_selected(self, request, queryset):
        if not (request.user.is_superuser or request.user.has_perm("jobs.can_delete_job_files")):
            raise PermissionDenied
        done = 0
        for job in queryset:
            delete_job_files(job, actor=request.user, client_ip_hash=hash_client_ip(request))
            done += 1
        self.message_user(request, f"File dari {done} pekerjaan dihapus.", messages.WARNING)

    @admin.action(description="Perpanjang retensi 24 jam")
    def extend_day(self, request, queryset):
        for job in queryset:
            job.expires_at = timezone.now() + timedelta(days=1)
            job.save(update_fields=["expires_at", "updated_at"])
            self._audit(request, "extend_retention_24h", job)

    @admin.action(description="Perpanjang retensi 7 hari")
    def extend_week(self, request, queryset):
        for job in queryset:
            job.expires_at = timezone.now() + timedelta(days=7)
            job.save(update_fields=["expires_at", "updated_at"])
            self._audit(request, "extend_retention_7d", job)

    @admin.action(description="Ekspor metadata CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="jobs.csv"'
        writer = csv.writer(response)
        writer.writerow(["public_id", "filename", "status", "model", "size", "created_at"])
        for job in queryset.iterator():
            writer.writerow(
                [
                    job.public_id,
                    job.original_filename,
                    job.status,
                    job.model_name,
                    job.original_size_bytes,
                    job.created_at.isoformat(),
                ]
            )
        return response

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def _audit(self, request, action, job):
        AdminAuditLog.objects.create(
            actor=request.user,
            action=action,
            object_type="ImageJob",
            object_identifier=str(job.public_id),
            client_ip_hash=hash_client_ip(request),
        )

    def delete_model(self, request, obj):
        self._audit(request, "delete_job_record", obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for job in queryset:
            self._audit(request, "delete_job_record", job)
        super().delete_queryset(request, queryset)


@admin.register(JobEvent)
class JobEventAdmin(admin.ModelAdmin):
    list_display = ("job", "event_type", "message", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("job__public_id", "message")
    readonly_fields = ("job", "event_type", "message", "safe_metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Identitas", {"fields": ("site_name", "site_tagline")}),
        ("Operasional", {"fields": ("public_upload_enabled", "maintenance_mode", "maintenance_message")}),
        ("Model", {"fields": ("default_model", "allowed_models")}),
        (
            "Batas aman",
            {
                "fields": (
                    "upload_max_bytes",
                    "max_image_pixels",
                    "retention_hours",
                    "max_active_jobs_per_session",
                    "max_queue_size",
                    "upload_rate_limit_per_hour",
                )
            },
        ),
        ("Privasi", {"fields": ("show_public_history", "privacy_notice")}),
    )
    readonly_fields = ("updated_by", "updated_at")

    def has_add_permission(self, request):
        return request.user.is_superuser and not SiteConfiguration.objects.exists()

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        AdminAuditLog.objects.create(
            actor=request.user,
            action="update_site_configuration",
            object_type="SiteConfiguration",
            object_identifier="1",
            client_ip_hash=hash_client_ip(request),
            metadata={"changed_fields": list(form.changed_data)},
        )


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "object_type", "object_identifier")
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("object_identifier", "actor__email")
    readonly_fields = (
        "actor",
        "action",
        "object_type",
        "object_identifier",
        "client_ip_hash",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
