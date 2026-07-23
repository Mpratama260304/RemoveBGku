from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.core.security import hash_client_ip

from .models import AdminAuditLog


@receiver(user_logged_in)
def audit_staff_login(sender, request, user, **kwargs):
    admin_prefix = f"/{settings.ADMIN_URL_PATH}"
    if request and user.is_staff and request.path.startswith(admin_prefix):
        AdminAuditLog.objects.create(
            actor=user,
            action="admin_login",
            object_type="User",
            object_identifier=str(user.pk),
            client_ip_hash=hash_client_ip(request),
        )
