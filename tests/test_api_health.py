import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_api_health():
    client = APIClient()
    response = client.get("/api/")
    assert response.status_code in (200, 401)


@pytest.mark.django_db
def test_healthz_accessible_sans_authentification():
    client = APIClient()
    response = client.get("/api/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


@pytest.mark.django_db
def test_healthz_racine_pour_load_balancer():
    client = APIClient()
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
