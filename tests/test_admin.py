import pytest
from django.urls import reverse

from apps.jobs.models import AdminAuditLog, ImageJob


@pytest.mark.django_db
def test_admin_dashboard_requires_staff(client, user, admin_user):
    client.force_login(user)
    assert client.get("/admin/").status_code == 302
    client.force_login(admin_user)
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Dashboard Operasional" in response.content


@pytest.mark.django_db
def test_admin_cancel_action_audited(client, admin_user, owned_job):
    client.force_login(admin_user)
    response = client.post(
        reverse("admin:jobs_imagejob_changelist"),
        {"action": "cancel_selected", "_selected_action": [str(owned_job.pk)]},
        follow=True,
    )
    assert response.status_code == 200
    owned_job.refresh_from_db()
    assert owned_job.status == ImageJob.Status.CANCELED
    assert AdminAuditLog.objects.filter(
        action="cancel_job", object_identifier=str(owned_job.public_id)
    ).exists()


@pytest.mark.django_db
def test_audit_log_is_read_only(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("admin:jobs_adminauditlog_add")).status_code == 403
