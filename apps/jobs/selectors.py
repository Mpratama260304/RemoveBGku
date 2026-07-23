from django.core.paginator import Paginator

from .models import ImageJob
from .services import owner_hash_for_request


def session_history(request, page_number=1, per_page=12):
    owner_hash = owner_hash_for_request(request)
    queryset = ImageJob.objects.filter(session_owner_hash=owner_hash).exclude(
        status=ImageJob.Status.FILES_DELETED
    )
    return Paginator(queryset, per_page).get_page(page_number)


def recent_jobs(limit=10):
    return ImageJob.objects.only(
        "public_id",
        "original_filename",
        "status",
        "model_name",
        "original_size_bytes",
        "original_width",
        "original_height",
        "processing_duration_ms",
        "created_at",
    )[:limit]
