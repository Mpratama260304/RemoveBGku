import pytest

from apps.accounts.forms import UserChangeForm, UserCreationForm


@pytest.mark.django_db
def test_user_creation_form_success_and_mismatch():
    form = UserCreationForm(
        data={
            "email": "new@example.com",
            "full_name": "New User",
            "password1": "a-secure-password",
            "password2": "a-secure-password",
        }
    )
    assert form.is_valid()
    user = form.save()
    assert user.check_password("a-secure-password")

    mismatch = UserCreationForm(
        data={"email": "bad@example.com", "password1": "first-value", "password2": "second-value"}
    )
    assert not mismatch.is_valid()


@pytest.mark.django_db
def test_user_change_form_preserves_hash(user):
    form = UserChangeForm(
        instance=user,
        data={
            "email": user.email,
            "full_name": "Changed",
            "password": user.password,
            "is_active": "on",
            "date_joined": user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert form.is_valid()
    changed = form.save()
    assert changed.full_name == "Changed"
