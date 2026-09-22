import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.equipment.models import Equipment, Service, Localisation
from apps.preventive.models import MaintenancePlan, MaintenancePreventive


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def biomed_user():
    return User.objects.create_user(
        username="biomed3",
        password="BiomedPass123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
    )


@pytest.fixture
def service():
    return Service.objects.create(nom="Chirurgie")


@pytest.fixture
def localisation():
    return Localisation.objects.create(batiment="B1", etage="3", salle="S301")


@pytest.fixture
def equipment(service, localisation):
    return Equipment.objects.create(
        num_inventaire="INV-TEST-003",
        nom="Table chirurgicale",
        type_equipement="Table chirurgicale",
        categorie="Chirurgie",
        marque="Maquet",
        modele="ALPHAMAXX",
        num_serie="SN-TABLE-001",
        service=service,
        localisation=localisation,
    )


@pytest.fixture
def plan():
    return MaintenancePlan.objects.create(
        nom="Maintenance trimestrielle tables chirurgie",
        type_equipement="Table chirurgicale",
        frequence=MaintenancePlan.Frequence.TRIMESTRIELLE,
        delai_jours=90,
    )


@pytest.mark.django_db
def test_create_plan(api_client, biomed_user):
    api_client.force_authenticate(user=biomed_user)
    resp = api_client.post(
        "/api/maintenance-plans/",
        {"nom": "Plan test", "type_equipement": "ECG", "frequence": "MENSUELLE", "delai_jours": 30},
        format="json",
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_create_preventive_maintenance(api_client, biomed_user, plan, equipment):
    api_client.force_authenticate(user=biomed_user)
    resp = api_client.post(
        "/api/maintenance-preventive/",
        {"plan": plan.id, "equipement": equipment.id, "date_planifiee": "2026-12-01"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["statut"] == "PLANIFIEE"


@pytest.mark.django_db
def test_start_and_finish_preventive(api_client, biomed_user, plan, equipment):
    api_client.force_authenticate(user=biomed_user)
    create_resp = api_client.post(
        "/api/maintenance-preventive/",
        {"plan": plan.id, "equipement": equipment.id, "date_planifiee": "2026-12-01"},
        format="json",
    )
    mp_id = create_resp.json()["id"]

    resp = api_client.post(f"/api/maintenance-preventive/{mp_id}/start/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_COURS"

    resp = api_client.post(
        f"/api/maintenance-preventive/{mp_id}/finish/",
        {"commentaire": "Terminée avec succès"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "TERMINEE"
    assert resp.json()["date_effective"] is not None


@pytest.mark.django_db
def test_cannot_finish_not_started(api_client, biomed_user, plan, equipment):
    api_client.force_authenticate(user=biomed_user)
    create_resp = api_client.post(
        "/api/maintenance-preventive/",
        {"plan": plan.id, "equipement": equipment.id, "date_planifiee": "2026-12-01"},
        format="json",
    )
    mp_id = create_resp.json()["id"]
    resp = api_client.post(f"/api/maintenance-preventive/{mp_id}/finish/", {}, format="json")
    assert resp.status_code == 400
