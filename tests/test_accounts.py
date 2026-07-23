import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_create_user_normalizes_email(django_user_model):
    user = django_user_model.objects.create_user("Person@EXAMPLE.COM", "secret")
    assert user.email == "person@example.com"
    assert user.check_password("secret")
    assert not user.is_staff


@pytest.mark.django_db
def test_create_superuser_requires_password(django_user_model):
    with pytest.raises(ValueError):
        django_user_model.objects.create_superuser("admin@example.com", "")


@pytest.mark.django_db
def test_admin_login_uses_email(client, admin_user):
    response = client.post(
        "/admin/login/", {"username": admin_user.email, "password": "a-long-test-password"}
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_bootstrap_admin_create_and_idempotent(monkeypatch, django_user_model, capsys):
    values = {
        "BOOTSTRAP_ADMIN_ENABLED": "true",
        "BOOTSTRAP_ADMIN_EMAIL": "bootstrap@example.com",
        "BOOTSTRAP_ADMIN_PASSWORD": "initial-secret-value",
        "BOOTSTRAP_ADMIN_FULL_NAME": "Bootstrap Admin",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    call_command("bootstrap_admin")
    user = django_user_model.objects.get(email="bootstrap@example.com")
    assert user.is_superuser and user.is_staff and user.must_review_security_notice
    assert user.check_password("initial-secret-value")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "another-secret")
    call_command("bootstrap_admin")
    user.refresh_from_db()
    assert user.check_password("initial-secret-value")
    assert "initial-secret-value" not in capsys.readouterr().out


@pytest.mark.django_db
def test_bootstrap_force_reset(monkeypatch, django_user_model):
    user = django_user_model.objects.create_superuser("bootstrap@example.com", "old-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", user.email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "new-secret")
    monkeypatch.setenv("FORCE_RESET_BOOTSTRAP_ADMIN_PASSWORD", "true")
    call_command("bootstrap_admin")
    user.refresh_from_db()
    assert user.check_password("new-secret")


@pytest.mark.django_db
def test_bootstrap_disabled(monkeypatch, django_user_model):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")
    call_command("bootstrap_admin")
    assert not django_user_model.objects.exists()
