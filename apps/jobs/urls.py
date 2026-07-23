from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("<uuid:job_id>/", views.detail, name="detail"),
    path("<uuid:job_id>/status/", views.status, name="status"),
    path("<uuid:job_id>/retry/", views.retry, name="retry"),
    path("<uuid:job_id>/delete/", views.delete, name="delete"),
    path("<uuid:job_id>/download/", views.download, name="download"),
    path("<uuid:job_id>/asset/<str:kind>/", views.asset, name="asset"),
]
