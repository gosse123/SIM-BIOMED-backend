import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.equipment.models import Equipment, Service, Localisation


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        role=User.Role.ADMINISTRATEUR,
    )


@pytest.fixture
def service():
    return Service.objects.create(nom="Réanimation")


@pytest.fixture
def localisation():
    return Localisation.objects.create(batiment="Bâtiment A", etage="2", salle="R1")


@pytest.fixture
def equipment_data(service, localisation):
    return {
        "num_inventaire": "INV-2024-001",
        "nom": "Respirateur V500",
        "type_equipement": "Respirateur lourd",
        "categorie": "Ventilation",
        "marque": "Dräger",
        "modele": "Evita V500",
        "num_serie": "SN-981245",
        "service": service.id,
        "localisation": localisation.id,
    }


@pytest.mark.django_db
def test_create_equipment(api_client, admin_user, equipment_data):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(
        "/api/equipment/", equipment_data, format="json"
    )
    assert response.status_code == 201
    data = response.json()
    assert data["num_inventaire"] == "INV-2024-001"
    assert data["etat_operationnel"] == "FONCTIONNEL"


@pytest.mark.django_db
def test_list_equipment(api_client, admin_user, equipment_data):
    api_client.force_authenticate(user=admin_user)
    api_client.post("/api/equipment/", equipment_data, format="json")
    response = api_client.get("/api/equipment/")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_get_equipment_detail(api_client, admin_user, equipment_data):
    api_client.force_authenticate(user=admin_user)
    create_response = api_client.post(
        "/api/equipment/", equipment_data, format="json"
    )
    eq_id = create_response.json()["id"]
    response = api_client.get(f"/api/equipment/{eq_id}/")
    assert response.status_code == 200
    assert response.json()["nom"] == "Respirateur V500"


@pytest.mark.django_db
def test_update_equipment(api_client, admin_user, equipment_data):
    api_client.force_authenticate(user=admin_user)
    create_response = api_client.post(
        "/api/equipment/", equipment_data, format="json"
    )
    eq_id = create_response.json()["id"]
    response = api_client.patch(
        f"/api/equipment/{eq_id}/",
        {"etat_operationnel": "EN_PANNE"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["etat_operationnel"] == "EN_PANNE"


@pytest.mark.django_db
def test_duplicate_inventory_rejected(api_client, admin_user, equipment_data):
    api_client.force_authenticate(user=admin_user)
    api_client.post("/api/equipment/", equipment_data, format="json")
    response = api_client.post(
        "/api/equipment/", equipment_data, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_unauthenticated_rejected(api_client, equipment_data):
    response = api_client.post(
        "/api/equipment/", equipment_data, format="json"
    )
    assert response.status_code in (401, 403)
