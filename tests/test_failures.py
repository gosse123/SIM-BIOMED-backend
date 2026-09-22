import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.equipment.models import Equipment, Service, Localisation
from apps.failures.models import Panne
from django.core.exceptions import ValidationError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def biomed_user():
    return User.objects.create_user(
        username="biomed1",
        password="BiomedPass123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
    )


@pytest.fixture
def direction_user():
    return User.objects.create_user(
        username="direction",
        password="DirPass123!",
        role=User.Role.DIRECTION,
    )


@pytest.fixture
def service():
    return Service.objects.create(nom="Cardiologie")


@pytest.fixture
def localisation():
    return Localisation.objects.create(batiment="B2", etage="1", salle="S101")


@pytest.fixture
def equipment(service, localisation):
    return Equipment.objects.create(
        num_inventaire="INV-TEST-001",
        nom="ECG PortaBit",
        type_equipement="ECG",
        categorie="Surveillance",
        marque="Philips",
        modele="PageWriter TC70",
        num_serie="SN-12345",
        service=service,
        localisation=localisation,
    )


@pytest.fixture
def panne_report_data(equipment):
    return {"equipement": equipment.id, "description_signalement": "L'ECG ne demarre plus"}


# --- Test transitions valides ---

@pytest.mark.django_db
def test_full_happy_path(api_client, biomed_user, panne_report_data):
    """Test complet : Signaler → Qualifier → Criticité → Diagnostic → Intervention → Test → Clôturer."""
    api_client.force_authenticate(user=biomed_user)

    # 1. Signaler
    resp = api_client.post("/api/pannes/", panne_report_data, format="json")
    assert resp.status_code == 201
    panne_id = resp.json()["id"]

    # 2. Qualifier
    resp = api_client.post(
        f"/api/pannes/{panne_id}/qualify/",
        {"observation_qualification": "Panne confirmee", "critere_urgence": "Urgence moyenne"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "QUALIFIEE"

    # 3. Evaluer criticite
    resp = api_client.post(
        f"/api/pannes/{panne_id}/evaluate-criticite/",
        {"critere_impact": "Patient en soins intensifs", "niveau_criticite": "ELEVE"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "CRITICITE_EVALUEE"
    assert resp.json()["niveau_criticite"] == "ELEVE"

    # 4. Diagnostiquer
    resp = api_client.post(
        f"/api/pannes/{panne_id}/diagnose/",
        {"description_diagnostic": "Connexion defaillante", "cause_identifiee": "Cable defaillant"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_DIAGNOSTIC"

    # 5. Intervention
    resp = api_client.post(f"/api/pannes/{panne_id}/start-intervention/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_INTERVENTION"

    # 6. Test
    resp = api_client.post(
        f"/api/pannes/{panne_id}/start-test/",
        {"resultat_test": "CONFORME"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_TEST"

    # 7. Cloturer
    resp = api_client.post(
        f"/api/pannes/{panne_id}/close/",
        {"commentaire_cloture": "Intervention OK"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "CLOSE"
    assert resp.json()["date_cloture"] is not None


@pytest.mark.django_db
def test_invalid_transition_rejected(api_client, biomed_user, equipment):
    """On ne peut pas sauter d'etapes."""
    api_client.force_authenticate(user=biomed_user)
    panne = Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="Test",
        statut=Panne.Statut.SIGNALEE,
    )
    resp = api_client.post(
        f"/api/pannes/{panne.id}/start-intervention/",
        {},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_close_without_conform_test_rejected(api_client, biomed_user, equipment):
    """RB-CL-001 : pas de cloture sans test conforme."""
    api_client.force_authenticate(user=biomed_user)
    panne = Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="Test",
        statut=Panne.Statut.EN_TEST,
        resultat_test=Panne.ResultatTest.TOUJOURS_EN_PANNE,
    )
    resp = api_client.post(f"/api/pannes/{panne.id}/close/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_qualify_without_observation_rejected(api_client, biomed_user, equipment):
    """RB-PANNE-001 : observation obligatoire pour la qualification."""
    api_client.force_authenticate(user=biomed_user)
    panne = Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="Test",
        statut=Panne.Statut.SIGNALEE,
    )
    resp = api_client.post(
        f"/api/pannes/{panne.id}/qualify/",
        {"observation_qualification": "", "critere_urgence": "Test"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_wait_piece_then_resume(api_client, biomed_user, equipment):
    """Test du circuit EN_ATTENTE_PIECE."""
    api_client.force_authenticate(user=biomed_user)
    panne = Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="Test",
        statut=Panne.Statut.EN_DIAGNOSTIC,
        description_diagnostic="Panne hardware",
        cause_identifiee="Condensateur defaillant",
    )
    # Diagnostique → En attente piece
    resp = api_client.post(f"/api/pannes/{panne.id}/wait-piece/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_ATTENTE_PIECE"

    # Attente piece → Intervention
    resp = api_client.post(f"/api/pannes/{panne.id}/start-intervention/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_INTERVENTION"


@pytest.mark.django_db
def test_list_pannes(api_client, biomed_user, panne_report_data):
    api_client.force_authenticate(user=biomed_user)
    api_client.post("/api/pannes/", panne_report_data, format="json")
    resp = api_client.get("/api/pannes/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
