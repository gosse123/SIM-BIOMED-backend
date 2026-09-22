import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_api_health():
    client = APIClient()
    response = client.get("/api/")
    assert response.status_code in (200, 401)
