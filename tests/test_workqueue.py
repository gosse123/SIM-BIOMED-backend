import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.equipment.models import Equipment, Localisation, Service
from apps.failures.models import Panne
from apps.interventions.models import Intervention


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def resp_biomed():
    return User.objects.create_user(
        username="resp_wq",
        password="RespPass123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
    )


@pytest.fixture
def tech_wq():
    return User.objects.create_user(
        username="tech_wq",
        password="TechPass123!",
        role=User.Role.TECHNICIEN,
    )


@pytest.fixture
def equipment():
    service = Service.objects.create(nom="Réanimation")
    localisation = Localisation.objects.create(batiment="A", etage="1", salle="101")
    return Equipment.objects.create(
        num_inventaire="INV-WQ-001",
        nom="Respirateur V500",
        type_equipement="Respirateur",
        categorie="Vital",
        marque="Dräger",
        modele="V500",
        num_serie="SN-WQ-1",
        service=service,
        localisation=localisation,
    )


@pytest.fixture
def panne_signalee(equipment, resp_biomed):
    return Panne.objects.create(
        equipement=equipment,
        signale_par=resp_biomed,
        description_signalement="Défaut d'alimentation",
        statut=Panne.Statut.SIGNALEE,
    )


@pytest.mark.django_db
def test_workqueue_transitions_pilotees_par_serveur(
    api_client, resp_biomed, panne_signalee
):
    """RB-004 : les transitions viennent de la carte domaine, pas du client."""
    api_client.force_authenticate(user=resp_biomed)
    resp = api_client.get("/api/workqueue/")
    assert resp.status_code == 200
    data = resp.json()
    item = next(p for p in data["pannes"] if p["id"] == panne_signalee.id)
    assert item["transitions_valides"] == ["QUALIFIEE"]
    assert "CLOSE" not in item["transitions_valides"]
    assert item["service_nom"] == "Réanimation"


@pytest.mark.django_db
def test_workqueue_expose_techniciens_reels_avec_charge(
    api_client, resp_biomed, tech_wq, equipment
):
    """Garde biomédicale : liste et charge calculées depuis les données."""
    tech_wq.etablissement = resp_biomed.etablissement
    tech_wq.save(update_fields=["etablissement"])
    panne = Panne.objects.create(
        equipement=equipment,
        signale_par=resp_biomed,
        description_signalement="Test",
        statut=Panne.Statut.EN_INTERVENTION,
    )
    Intervention.objects.create(
        equipement=equipment,
        panne=panne,
        type_intervention="CORRECTIVE",
        description="En cours",
        statut="EN_COURS",
        realisee_par=tech_wq,
    )
    api_client.force_authenticate(user=resp_biomed)
    data = api_client.get("/api/workqueue/").json()
    tech = next((t for t in data["techniciens"] if t["id"] == tech_wq.id), None)
    assert tech is not None
    assert tech["interventions_en_cours"] == 1
    assert tech["initiales"]
    assert any(t["id"] == resp_biomed.id for t in data["techniciens"])


@pytest.mark.django_db
def test_workqueue_age_moyen_reel(api_client, resp_biomed, panne_signalee):
    api_client.force_authenticate(user=resp_biomed)
    data = api_client.get("/api/workqueue/").json()
    assert data["age_moyen_minutes"] is not None
    assert data["age_moyen_minutes"] >= 0


@pytest.mark.django_db
def test_affecter_panne_paire(api_client, resp_biomed, tech_wq, panne_signalee):
    """Prise en charge : POST vide → affectation à l'utilisateur courant."""
    api_client.force_authenticate(user=tech_wq)
    resp = api_client.post(f"/api/pannes/{panne_signalee.id}/affecter/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["affecte_a"] == tech_wq.id
    assert resp.json()["affecte_a_nom"]
    assert AuditLog.objects.filter(
        action="panne.affecter", entite_id=panne_signalee.id
    ).exists()


@pytest.mark.django_db
def test_affecter_a_paire_et_desaffecter(api_client, resp_biomed, tech_wq, panne_signalee):
    api_client.force_authenticate(user=resp_biomed)
    resp = api_client.post(
        f"/api/pannes/{panne_signalee.id}/affecter/",
        {"utilisateur": tech_wq.id},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["affecte_a"] == tech_wq.id

    resp = api_client.post(
        f"/api/pannes/{panne_signalee.id}/affecter/", {"utilisateur": None}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["affecte_a"] is None


@pytest.mark.django_db
def test_affecter_roles_non_techniciens_rejete(api_client, resp_biomed, panne_signalee):
    direction = User.objects.create_user(
        username="dir_wq",
        password="DirPass123!",
        role=User.Role.DIRECTION,
    )
    api_client.force_authenticate(user=resp_biomed)
    resp = api_client.post(
        f"/api/pannes/{panne_signalee.id}/affecter/", {"utilisateur": direction.id}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_affecter_autre_etablissement_rejete(api_client, resp_biomed, panne_signalee):
    from apps.accounts.models import Etablissement

    etab_a = Etablissement.objects.create(nom="Hôpital A")
    resp_biomed.etablissement = etab_a
    resp_biomed.save(update_fields=["etablissement"])
    panne_signalee.equipement.etablissement = etab_a
    panne_signalee.equipement.save(update_fields=["etablissement"])
    etab_b = Etablissement.objects.create(nom="Hôpital B")
    user_b = User.objects.create_user(
        username="tech_etab_b",
        password="TechPass123!",
        role=User.Role.TECHNICIEN,
        etablissement=etab_b,
    )
    api_client.force_authenticate(user=resp_biomed)
    resp = api_client.post(
        f"/api/pannes/{panne_signalee.id}/affecter/", {"utilisateur": user_b.id}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_workqueue_reflete_affectation(api_client, resp_biomed, tech_wq, panne_signalee):
    api_client.force_authenticate(user=tech_wq)
    api_client.post(f"/api/pannes/{panne_signalee.id}/affecter/", {}, format="json")
    data = api_client.get("/api/workqueue/").json()
    item = next(p for p in data["pannes"] if p["id"] == panne_signalee.id)
    assert item["affecte_a"] == tech_wq.id


@pytest.mark.django_db
def test_workqueue_agregats_groupes_correctement(api_client, resp_biomed, equipment):
    """Les compteurs par_statut / par_criticite doivent sommer au total
    (régression : le order_by du tri était ajouté au GROUP BY et chaque
    ligne devenait son propre groupe, le dict effaçant les doublons)."""
    for i in range(2):
        Panne.objects.create(
            equipement=equipment,
            signale_par=resp_biomed,
            description_signalement=f"Signalée {i}",
            statut=Panne.Statut.SIGNALEE,
            niveau_criticite="MOYEN",
        )
    Panne.objects.create(
        equipement=equipment,
        signale_par=resp_biomed,
        description_signalement="En diagnostic",
        statut=Panne.Statut.EN_DIAGNOSTIC,
        niveau_criticite="CRITIQUE",
    )
    api_client.force_authenticate(user=resp_biomed)
    data = api_client.get("/api/workqueue/").json()
    assert data["total_ouvertes"] == 3
    assert data["par_statut"] == {"SIGNALEE": 2, "EN_DIAGNOSTIC": 1}
    assert data["par_criticite"] == {"MOYEN": 2, "CRITIQUE": 1}
    assert sum(data["par_statut"].values()) == data["total_ouvertes"]
    assert sum(data["par_criticite"].values()) == data["total_ouvertes"]
