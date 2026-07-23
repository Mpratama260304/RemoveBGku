from .base import *  # noqa: F403

DEBUG = env_bool("DEBUG", True)  # noqa: F405
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")  # noqa: F405
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405
# Default eager: proses gambar berjalan inline di web (tanpa Redis/worker) supaya
# `runserver` bisa dipakai upload/proses langsung. Set CELERY_TASK_ALWAYS_EAGER=false
# untuk memakai Redis + Celery worker sungguhan saat dev.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)  # noqa: F405
