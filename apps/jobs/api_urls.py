from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("jobs/", views.upload, name="jobs-create"),
    path("jobs/<uuid:job_id>/", views.api_job, name="job-detail"),
    path("jobs/<uuid:job_id>/status/", views.status, name="job-status"),
    path("jobs/<uuid:job_id>/download/", views.download, name="job-download"),
]
