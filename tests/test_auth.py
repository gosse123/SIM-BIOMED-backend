import pytest
from django.test import Client
from apps.accounts.models import User


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def user_data():
    return {
        "username": "tech_test",
        "email": "tech@test.com",
        "password": "SecurePass123!",
        "first_name": "Jean",
        "last_name": "Dupont",
        "role": User.Role.TECHNICIEN,
    }


@pytest.mark.django_db
def test_register_success(api_client, user_data):
    response = api_client.post("/api/auth/register/", user_data, content_type="application/json")
    assert response.status_code == 201
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    assert data["user"]["role"] == "TECHNICIEN"
    assert data["user"]["username"] == "tech_test"


@pytest.mark.django_db
def test_register_weak_password(api_client, user_data):
    user_data["password"] = "123"
    response = api_client.post("/api/auth/register/", user_data, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_success(api_client, user_data):
    api_client.post("/api/auth/register/", user_data, content_type="application/json")
    response = api_client.post("/api/auth/login/", {
        "username": "tech_test",
        "password": "SecurePass123!",
    }, content_type="application/json")
    assert response.status_code == 200
    assert "access" in response.json()


@pytest.mark.django_db
def test_login_wrong_password(api_client, user_data):
    api_client.post("/api/auth/register/", user_data, content_type="application/json")
    response = api_client.post("/api/auth/login/", {
        "username": "tech_test",
        "password": "WrongPassword",
    }, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_me_authenticated(api_client, user_data):
    api_client.post("/api/auth/register/", user_data, content_type="application/json")
    login_response = api_client.post("/api/auth/login/", {
        "username": "tech_test",
        "password": "SecurePass123!",
    }, content_type="application/json")
    token = login_response.json()["access"]

    response = api_client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert response.json()["username"] == "tech_test"


@pytest.mark.django_db
def test_me_unauthenticated(api_client):
    response = api_client.get("/api/auth/me/")
    assert response.status_code == 401
