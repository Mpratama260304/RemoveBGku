import pytest


@pytest.mark.django_db
def test_live_health(client):
    response = client.get("/health/live/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "web"}


@pytest.mark.django_db
def test_ready_health(client):
    response = client.get("/health/ready/")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    body = response.content.decode()
    assert "password" not in body and "DATABASE_URL" not in body


@pytest.mark.django_db
def test_ready_database_failure(client, monkeypatch):
    monkeypatch.setattr("apps.core.health.connection.cursor", lambda: (_ for _ in ()).throw(RuntimeError()))
    response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"
