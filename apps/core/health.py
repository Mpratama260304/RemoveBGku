from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse


def live(request):
    return JsonResponse({"status": "ok", "service": "web"})


def readiness_report(check_worker: bool = True) -> tuple[bool, dict[str, str]]:
    checks: dict[str, str] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    if settings.CELERY_TASK_ALWAYS_EAGER:
        checks["redis"] = "ok"
    else:
        try:
            import redis

            checks["redis"] = "ok" if redis.from_url(settings.REDIS_URL, socket_timeout=2).ping() else "error"
        except Exception:
            checks["redis"] = "error"

    cached_storage = cache.get("health:storage_probe")
    if cached_storage:
        checks["storage"] = cached_storage
    else:
        try:
            probe = default_storage.save("healthcheck/probe.txt", ContentFile(b"ok"))
            with default_storage.open(probe, "rb") as handle:
                valid = handle.read() == b"ok"
            default_storage.delete(probe)
            checks["storage"] = "ok" if valid else "error"
        except Exception:
            checks["storage"] = "error"
        cache.set("health:storage_probe", checks["storage"], timeout=60)

    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        checks["migrations"] = "ok" if not plan else "pending"
    except Exception:
        checks["migrations"] = "error"

    if check_worker:
        heartbeat = cache.get("worker:heartbeat")
        checks["worker"] = "ok" if heartbeat else "stale"
    ready = all(value == "ok" for value in checks.values())
    return ready, checks


def ready(request):
    is_ready, checks = readiness_report(check_worker=not settings.CELERY_TASK_ALWAYS_EAGER)
    return JsonResponse(
        {"status": "ready" if is_ready else "not_ready", "checks": checks}, status=200 if is_ready else 503
    )
