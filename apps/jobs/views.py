from __future__ import annotations

import json
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.rate_limit import consume

from .exceptions import JobError, RateLimitedError
from .forms import UploadForm
from .models import ImageJob, JobEvent, SiteConfiguration
from .selectors import session_history
from .services import create_job, delete_job_files, get_owned_job, owner_hash_for_request, retry_job


def _config():
    return SiteConfiguration.get_solo()


@require_GET
def home(request):
    config = _config()
    return render(
        request,
        "pages/home.html",
        {"config": config, "form": UploadForm(allowed_models=config.allowed_models)},
    )


@require_GET
def privacy(request):
    return render(request, "pages/privacy.html", {"config": _config()})


@require_GET
def terms(request):
    return render(request, "pages/terms.html", {"config": _config()})


@require_GET
def faq(request):
    return render(request, "pages/faq.html", {"config": _config()})


@require_GET
def history(request):
    config = _config()
    page = session_history(request, request.GET.get("page", 1)) if config.show_public_history else None
    return render(request, "jobs/history.html", {"page_obj": page, "config": config})


def _job_or_404(request, job_id) -> ImageJob:
    try:
        return get_owned_job(request, job_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


@require_GET
def detail(request, job_id):
    job = _job_or_404(request, job_id)
    return render(request, "jobs/detail.html", {"job": job})


@require_GET
def status(request, job_id):
    job = _job_or_404(request, job_id)
    payload = {
        "id": str(job.public_id),
        "status": job.status,
        "status_label": job.get_status_display(),
        "terminal": job.is_terminal,
        "error": job.error_message_public,
        "expires_at": job.expires_at.isoformat(),
    }
    if job.status == ImageJob.Status.SUCCEEDED:
        payload.update(
            {
                "result_url": reverse("jobs:asset", args=[job.public_id, "result"]),
                "download_url": reverse("jobs:download", args=[job.public_id]),
            }
        )
    return JsonResponse(payload)


def _request_payload(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return {}
    return request.POST


@require_POST
def upload(request):
    config = _config()
    form = UploadForm(request.POST, request.FILES, allowed_models=config.allowed_models)
    if not form.is_valid():
        return JsonResponse(
            {"error": "Pilih file JPG, PNG, atau WebP yang valid.", "code": "INVALID_FILE_TYPE"}, status=422
        )
    try:
        job = create_job(
            request, form.cleaned_data["image"], form.cleaned_data.get("mode") or config.default_model
        )
    except JobError as exc:
        response = JsonResponse({"error": exc.public_message, "code": exc.code}, status=exc.status_code)
        if exc.status_code in {429, 503}:
            response["Retry-After"] = "60"
        return response
    return JsonResponse(
        {
            "id": str(job.public_id),
            "status": job.status,
            "status_url": reverse("jobs:status", args=[job.public_id]),
            "job_url": reverse("jobs:detail", args=[job.public_id]),
        },
        status=202,
    )


@require_POST
def retry(request, job_id):
    job = _job_or_404(request, job_id)
    try:
        retry_job(job)
    except JobError as exc:
        return JsonResponse({"error": exc.public_message, "code": exc.code}, status=exc.status_code)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"status": "queued"}, status=202)
    messages.success(request, "Pekerjaan dimasukkan kembali ke antrean.")
    return redirect("jobs:detail", job_id=job.public_id)


@require_POST
def delete(request, job_id):
    job = _job_or_404(request, job_id)
    delete_job_files(job)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"status": "files_deleted"})
    messages.success(request, "File gambar telah dihapus.")
    return redirect("history")


def _asset_field(job: ImageJob, kind: str):
    return {"original": job.original_file, "result": job.result_file, "thumbnail": job.thumbnail_file}.get(
        kind
    )


@require_GET
def asset(request, job_id, kind):
    job = _job_or_404(request, job_id)
    field = _asset_field(job, kind)
    if not field:
        raise Http404
    content_type = (
        job.original_mime_type
        if kind == "original"
        else ("image/webp" if kind == "thumbnail" else "image/png")
    )
    if settings.STORAGE_BACKEND == "s3":
        return redirect(
            default_storage.url(
                field.name,
                expire=getattr(settings, "AWS_QUERYSTRING_EXPIRE", 300),
            )
        )
    try:
        return FileResponse(default_storage.open(field.name, "rb"), content_type=content_type)
    except FileNotFoundError as exc:
        raise Http404 from exc


@require_GET
def download(request, job_id):
    job = _job_or_404(request, job_id)
    if job.status != ImageJob.Status.SUCCEEDED or not job.result_file:
        raise Http404
    key = f"download:{owner_hash_for_request(request)}"
    if not consume(key, settings.DOWNLOAD_RATE_LIMIT_PER_MINUTE, 60).allowed:
        return JsonResponse(
            {"error": RateLimitedError.public_message, "code": RateLimitedError.code}, status=429
        )
    JobEvent.objects.create(job=job, event_type="downloaded", message="Hasil diunduh pengguna.")
    if settings.STORAGE_BACKEND == "s3":
        disposition = f"attachment; filename*=UTF-8''{quote(job.safe_download_filename)}"
        return redirect(
            default_storage.url(
                job.result_file.name,
                parameters={
                    "ResponseContentDisposition": disposition,
                    "ResponseContentType": "image/png",
                },
                expire=getattr(settings, "AWS_QUERYSTRING_EXPIRE", 300),
            )
        )
    response = FileResponse(default_storage.open(job.result_file.name, "rb"), content_type="image/png")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(job.safe_download_filename)}"
    return response


@require_http_methods(["GET", "POST", "DELETE"])
def api_job(request, job_id):
    job = _job_or_404(request, job_id)
    if request.method == "DELETE":
        delete_job_files(job)
        return JsonResponse({}, status=204)
    return status(request, job_id)


def error_400(request, exception=None):
    return render(request, "errors/error.html", {"code": 400, "title": "Permintaan tidak valid"}, status=400)


def error_403(request, exception=None):
    return render(request, "errors/error.html", {"code": 403, "title": "Akses ditolak"}, status=403)


def error_404(request, exception=None):
    return render(request, "errors/error.html", {"code": 404, "title": "Halaman tidak ditemukan"}, status=404)


def error_500(request):
    return render(
        request, "errors/error.html", {"code": 500, "title": "Terjadi kesalahan server"}, status=500
    )
