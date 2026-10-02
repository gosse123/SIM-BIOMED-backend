import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_indicateurs_reserve_direction_et_admin(api_client):
    """RB-IND : indicateurs visibles par ADMINISTRATEUR et DIRECTION (IsDirection),
    aligné sur l'affichage canViewIndicators côté frontend."""
    direction = User.objects.create_user(
        username="dir_ind", password="Pass1234!", role=User.Role.DIRECTION
    )
    admin = User.objects.create_user(
        username="adm_ind", password="Pass1234!", role=User.Role.ADMINISTRATEUR
    )
    tech = User.objects.create_user(
        username="tech_ind", password="Pass1234!", role=User.Role.TECHNICIEN
    )

    api_client.force_authenticate(user=direction)
    assert api_client.get("/api/indicateurs/").status_code == 200
    api_client.force_authenticate(user=admin)
    assert api_client.get("/api/indicateurs/").status_code == 200
    api_client.force_authenticate(user=tech)
    assert api_client.get("/api/indicateurs/").status_code == 403


@pytest.mark.django_db
def test_indicateurs_anonyme_refuse(api_client):
    resp = api_client.get("/api/indicateurs/")
    assert resp.status_code in (401, 403)
