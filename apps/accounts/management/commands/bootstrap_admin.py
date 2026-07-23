import os

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Membuat atau memperbarui hak administrator bootstrap secara idempoten."

    def handle(self, *args, **options):
        if os.getenv("BOOTSTRAP_ADMIN_ENABLED", "false").lower() != "true":
            self.stdout.write("Bootstrap administrator dinonaktifkan.")
            return
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "Administrator").strip()
        if not email or not password:
            raise CommandError("Email dan password bootstrap wajib tersedia di environment.")

        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if created:
            user = User.objects.create_superuser(email=email, password=password, full_name=full_name)
            user.must_review_security_notice = True
        else:
            user.email = email
            user.full_name = user.full_name or full_name
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if os.getenv("FORCE_RESET_BOOTSTRAP_ADMIN_PASSWORD", "false").lower() == "true":
                user.set_password(password)
                user.must_review_security_notice = True
        user.save()
        self.stdout.write(self.style.SUCCESS("Administrator bootstrap siap."))
