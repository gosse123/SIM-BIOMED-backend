import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.equipment.models import Equipment, Localisation, Service
from apps.failures.models import Panne
from apps.interventions.models import Intervention


@pytest.fixture
def api_client():
    return APIClient()


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
    api_client.force_authenticate(user=biomed_user)
    resp = api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Remplacement composant RF",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["statut"] == "PLANIFIEE"


@pytest.mark.django_db
def test_start_intervention(api_client, biomed_user, equipment, panne):
    api_client.force_authenticate(user=biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Test",
        },
        format="json",
    )
    intervention_id = create_resp.json()["id"]
    resp = api_client.post(f"/api/interventions/{intervention_id}/start/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "EN_COURS"
    assert resp.json()["date_debut"] is not None


@pytest.mark.django_db
def test_finish_intervention(api_client, biomed_user, equipment, panne):
    api_client.force_authenticate(user=biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Test",
        },
        format="json",
    )
    intervention_id = create_resp.json()["id"]
    api_client.post(f"/api/interventions/{intervention_id}/start/", {}, format="json")
    resp = api_client.post(
        f"/api/interventions/{intervention_id}/finish/",
        {"temps_passe_minutes": 120, "pieces_utilisees": "Condensateur X200"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "TERMINEE"
    assert resp.json()["temps_passe_minutes"] == 120


@pytest.mark.django_db
def test_cannot_finish_not_started(api_client, biomed_user, equipment, panne):
    api_client.force_authenticate(user=biomed_user)
    create_resp = api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Test",
        },
        format="json",
    )
    intervention_id = create_resp.json()["id"]
    resp = api_client.post(f"/api/interventions/{intervention_id}/finish/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_list_interventions(api_client, biomed_user, equipment, panne):
    api_client.force_authenticate(user=biomed_user)
    api_client.post(
        "/api/interventions/",
        {
            "panne": panne.id,
            "equipement": equipment.id,
            "type_intervention": "CORRECTIVE",
            "description": "Test",
        },
        format="json",
    )
    resp = api_client.get("/api/interventions/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def _quick_intervention(api_client, equipment, panne=None, **extra):
    payload = {
        "equipement": equipment.id,
        "type_intervention": "CORRECTIVE",
        "description": "Test",
        **extra,
    }
    if panne:
        payload["panne"] = panne.id
    resp = api_client.post("/api/interventions/", payload, format="json")
    assert resp.status_code == 201, resp.json() if hasattr(resp, "json") else resp.content
    return Intervention.objects.get(pk=resp.json()["id"])


@pytest.mark.django_db
def test_create_hors_service_total_met_equipement_hors_service(
    api_client, biomed_user, equipment, panne
):
    """Nouvelle intervention avec hors_service_total → équipement HORS_SERVICE (RB-CL-002)."""
    api_client.force_authenticate(user=biomed_user)
    _quick_intervention(api_client, equipment, panne, hors_service_total=True)
    equipment.refresh_from_db()
    assert equipment.etat_operationnel == Equipment.StatutOperationnel.HORS_SERVICE


@pytest.mark.django_db
def test_create_sans_hors_service_laisse_etat_inchange(api_client, biomed_user, equipment, panne):
    """Sans hors_service_total, l'état opérationnel de l'équipement ne change pas."""
    api_client.force_authenticate(user=biomed_user)
    etat_avant = equipment.etat_operationnel
    _quick_intervention(api_client, equipment, panne)
    equipment.refresh_from_db()
    assert equipment.etat_operationnel == etat_avant


@pytest.mark.django_db
def test_finish_repare_totalement_remise_fonctionnel(api_client, biomed_user, equipment, panne):
    """finish(repare_totalement=True) → équipement FONCTIONNEL (RB-CL-002)."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne, hors_service_total=True)
    api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    resp = api_client.post(
        f"/api/interventions/{intervention.id}/finish/",
        {"repare_totalement": True},
        format="json",
    )
    assert resp.status_code == 200
    equipment.refresh_from_db()
    assert equipment.etat_operationnel == Equipment.StatutOperationnel.FONCTIONNEL


@pytest.mark.django_db
def test_finish_repare_totalement_ne_cloture_pas_la_panne(
    api_client, biomed_user, equipment, panne
):
    """RB-CL-001 : même si l'équipement est réparé, la panne liée reste ouverte
    tant qu'il n'y a pas de résultat de test."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    api_client.post(
        f"/api/interventions/{intervention.id}/finish/",
        {"repare_totalement": True},
        format="json",
    )
    panne.refresh_from_db()
    assert panne.statut != Panne.Statut.CLOSE


@pytest.mark.django_db
def test_create_intervention_equipement_autre_etablissement_refuse(api_client, equipment):
    """Cloisonnement : intervention sur l'équipement d'un autre établissement → 400."""
    from apps.accounts.models import Etablissement

    etab_a = Etablissement.objects.create(nom="Hôpital A")
    etab_b = Etablissement.objects.create(nom="Hôpital B")
    admin_b = User.objects.create_user(
        username="admin_b_int",
        password="Test1234!",
        role=User.Role.ADMINISTRATEUR,
        etablissement=etab_b,
    )
    equipment.etablissement = etab_a
    equipment.save(update_fields=["etablissement"])

    api_client.force_authenticate(user=admin_b)
    resp = api_client.post(
        "/api/interventions/",
        {"equipement": equipment.id, "type_intervention": "CORRECTIVE", "description": "Tentative"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_list_interventions_priorisee_par_criticite(api_client, biomed_user, equipment, panne):
    """RB-PR-004 : la liste est ordonnée par criticité de la panne liée."""
    api_client.force_authenticate(user=biomed_user)
    panne_critique = Panne.objects.create(
        equipement=equipment,
        signale_par=biomed_user,
        description_signalement="urgence",
        statut=Panne.Statut.EN_INTERVENTION,
        niveau_criticite="CRITIQUE",
    )
    panne.niveau_criticite = "FAIBLE"
    panne.save(update_fields=["niveau_criticite"])

    _quick_intervention(api_client, equipment, panne)  # créée en premier
    _quick_intervention(api_client, equipment, panne_critique)

    resp = api_client.get("/api/interventions/")
    results = resp.json()
    assert results[0]["panne_id"] == panne_critique.id


# --- Machine à états, RB-SEC-003 et synchronisation équipement ---


@pytest.fixture
def tech_user():
    return User.objects.create_user(
        username="tech_int",
        password="TechPass123!",
        role=User.Role.TECHNICIEN,
    )


@pytest.mark.django_db
def test_technicien_peut_executer_intervention(api_client, tech_user, equipment, panne):
    """RB-SEC-003 : le technicien exécute (consulter, créer, démarrer, terminer)."""
    api_client.force_authenticate(user=tech_user)
    assert api_client.get("/api/interventions/").status_code == 200

    intervention = _quick_intervention(api_client, equipment, panne)
    resp = api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    assert resp.status_code == 200
    resp = api_client.post(
        f"/api/interventions/{intervention.id}/finish/",
        {"temps_passe_minutes": 45},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["statut"] == "TERMINEE"


@pytest.mark.django_db
def test_technicien_ne_peut_pas_supprimer(api_client, tech_user, equipment, panne):
    """La suppression reste un acte de gestion (ADMIN/RESP)."""
    api_client.force_authenticate(user=tech_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    resp = api_client.delete(f"/api/interventions/{intervention.id}/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_suppression_laisse_trace_audit(api_client, biomed_user, equipment, panne):
    """RB-AUD-001 : toute action importante laisse une trace."""
    from apps.audit.models import AuditLog

    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    resp = api_client.delete(f"/api/interventions/{intervention.id}/")
    assert resp.status_code == 204
    assert AuditLog.objects.filter(
        action="intervention.delete", entite_id=intervention.id
    ).exists()


@pytest.mark.django_db
def test_annulation_planifiee(api_client, biomed_user, equipment, panne):
    """RB-004 : PLANIFIEE → ANNULEE via l'endpoint dédié."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    resp = api_client.post(f"/api/interventions/{intervention.id}/cancel/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["statut"] == "ANNULEE"

    # Terminal : plus aucune transition
    resp = api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_annulation_apres_fin_rejetee(api_client, biomed_user, equipment, panne):
    """RB-IN-001 : une intervention terminée ne peut plus être annulée."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    api_client.post(
        f"/api/interventions/{intervention.id}/finish/", {}, format="json"
    )
    resp = api_client.post(f"/api/interventions/{intervention.id}/cancel/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_start_met_equipement_en_maintenance(api_client, biomed_user, equipment, panne):
    """RB-CL-002 : démarrage → équipement EN_MAINTENANCE."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    equipment.refresh_from_db()
    assert equipment.etat_operationnel == Equipment.StatutOperationnel.EN_MAINTENANCE


@pytest.mark.django_db
def test_finish_partiel_avec_panne_retour_en_panne(
    api_client, biomed_user, equipment, panne
):
    """Réparation partielle : retour EN_PANNE jusqu'au test (RB-CL-001)."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    api_client.post(f"/api/interventions/{intervention.id}/start/", {}, format="json")
    resp = api_client.post(
        f"/api/interventions/{intervention.id}/finish/",
        {"repare_totalement": False},
        format="json",
    )
    assert resp.status_code == 200
    equipment.refresh_from_db()
    assert equipment.etat_operationnel == Equipment.StatutOperationnel.EN_PANNE


@pytest.mark.django_db
def test_patch_statut_intervention_ignore(api_client, biomed_user, equipment, panne):
    """RB-004 : le statut ne change pas par PATCH libre."""
    api_client.force_authenticate(user=biomed_user)
    intervention = _quick_intervention(api_client, equipment, panne)
    resp = api_client.patch(
        f"/api/interventions/{intervention.id}/",
        {"statut": "TERMINEE"},
        format="json",
    )
    assert resp.status_code == 200
    intervention.refresh_from_db()
    assert intervention.statut == Intervention.StatutIntervention.PLANIFIEE


@pytest.mark.django_db
def test_create_panne_d_autre_equipement_rejetee(api_client, biomed_user, equipment, panne):
    """Cohérence : la panne liée doit porter sur l'équipement de l'intervention."""
    autre = Equipment.objects.create(
        num_inventaire="INV-TEST-AUTRE",
        nom="Doppler",
        type_equipement="ECHO",
        categorie="Imagerie",
        marque="GE",
        modele="Vivid",
        num_serie="SN-AUTRE",
        service=equipment.service,
        localisation=equipment.localisation,
    )
    api_client.force_authenticate(user=biomed_user)
    resp = api_client.post(
        "/api/interventions/",
        {
            "equipement": autre.id,
            "panne": panne.id,
            "type_intervention": "CORRECTIVE",
            "description": "Cohérence",
        },
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_technicien_consulte_mais_ne_gere_pas_equipement(api_client, tech_user):
    """RB-SEC-002 : consultation ouverte, écriture réservée ADMIN/RESP."""
    api_client.force_authenticate(user=tech_user)
    assert api_client.get("/api/equipment/").status_code == 200
    resp = api_client.post(
        "/api/equipment/",
        {"num_inventaire": "INV-X", "nom": "Test", "type_equipement": "autre"},
        format="json",
    )
    assert resp.status_code == 403
