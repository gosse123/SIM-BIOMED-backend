import pytest
from django.test import Client


@pytest.mark.django_db
def test_api_health():
    client = Client()
    response = client.get("/api/")
    assert response.status_code == 200
