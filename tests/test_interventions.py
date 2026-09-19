import pytest
from django.test import Client
from apps.accounts.models import User
from apps.equipment.models import Equipment, Service, Localisation
from apps.failures.models import Panne
from apps.interventions.models import Intervention


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def biomed_user():
    return User.objects.create_user(
        username="biomed2",
        password="BiomedPass123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
    )


@pytest.fixture
def service():
    return Service.objects.create(nom="Radiologie")


@pytest.fixture
def localisation():
    return Localisation.objects.create(batiment="B3", etage="0", salle="R201")


@pytest.fixture
def equipment(service, localisation):
    return Equipment.objects.create(
        num_inventaire="INV-TEST-002",
        nom="IRM 3T",
        type_equipement="IRM",
        categorie="Imagerie",
        marque="Siemens",
        modele="Magnetom Vida",
        num_serie="SN-IRM-999",
        service=service,
        localisation=localisation,
    )


@pytest.fixture
def panne(equipment, biomed_user):
    return Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="IRM en panne",
        statut=Panne.Statut.EN_INTERVENTION,
    )


@pytest.mark.django_db
def test_create_intervention(api_client, biomed_user, equipment, panne):
    api_client.force_login(biomed_user)
    resp = api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Remplacement composant RF",
        },
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["statut"] == "PLANIFIEE"


@pytest.mark.django_db
def test_start_intervention(api_client, biomed_user, equipment, panne):
    api_client.force_login(biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {"panne": panne.id, "equipement": equipment.id, "type_intervention": "CORRECTIVE", "description": "Test"},
        content_type="application/json",
    )
    intervention_id = create_resp.json()["id"]
    resp = api_client.post(f"/api/interventions/{intervention_id}/start/", {}, content_type="application/json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_COURS"
    assert resp.json()["date_debut"] is not None


@pytest.mark.django_db
def test_finish_intervention(api_client, biomed_user, equipment, panne):
    api_client.force_login(biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {"panne": panne.id, "equipement": equipment.id, "type_intervention": "CORRECTIVE", "description": "Test"},
        content_type="application/json",
    )
    intervention_id = create_resp.json()["id"]
    api_client.post(f"/api/interventions/{intervention_id}/start/", {}, content_type="application/json")
    resp = api_client.post(
        f"/api/interventions/{intervention_id}/finish/",
        {"temps_passe_minutes": 120, "pieces_utilisees": "Condensateur X200"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "TERMINEE"
    assert resp.json()["temps_passe_minutes"] == 120


@pytest.mark.django_db
def test_cannot_finish_not_started(api_client, biomed_user, equipment, panne):
    api_client.force_login(biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {"panne": panne.id, "equipement": equipment.id, "type_intervention": "CORRECTIVE", "description": "Test"},
        content_type="application/json",
    )
    intervention_id = create_resp.json()["id"]
    resp = api_client.post(f"/api/interventions/{intervention_id}/finish/", {}, content_type="application/json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_list_interventions(api_client, biomed_user, equipment, panne):
    api_client.force_login(biomed_user)
    api_client.post(
        "/api/interventions/",
        {"panne": panne.id, "equipement": equipment.id, "type_intervention": "CORRECTIVE", "description": "Test"},
        content_type="application/json",
    )
    resp = api_client.get("/api/interventions/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
