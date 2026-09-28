"""Tests de cloisonnement multi-établissements (RB-SEC).

Un utilisateur de l'établissement A ne doit jamais voir ni manipuler
les données de l'établissement B.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Etablissement, User
from apps.equipment.models import Equipment, Localisation, Service
from apps.failures.models import Panne
from apps.preventive.models import MaintenancePlan, MaintenancePreventive

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def etab_a():
    return Etablissement.objects.create(nom="Hôpital A")


@pytest.fixture
def etab_b():
    return Etablissement.objects.create(nom="Hôpital B")


def _make_user(username, role, etab):
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="Test123!",
        role=role,
        etablissement=etab,
        profil_complete=True,
    )


@pytest.fixture
def admin_a(etab_a):
    return _make_user("admin_a", User.Role.ADMINISTRATEUR, etab_a)


@pytest.fixture
def admin_b(etab_b):
    return _make_user("admin_b", User.Role.ADMINISTRATEUR, etab_b)


def _make_equipment(etab, num):
    service = Service.objects.create(nom=f"Service {num}", etablissement=etab)
    loc = Localisation.objects.create(batiment="A", etablissement=etab)
    return Equipment.objects.create(
        nom=f"Equipement {num}",
        num_inventaire=num,
        type_equipement="Monitor",
        categorie="Monitoring",
        marque="M",
        modele="X",
        num_serie=f"SN-{num}",
        service=service,
        localisation=loc,
        etablissement=etab,
    )


@pytest.fixture
def equipment_a(etab_a):
    return _make_equipment(etab_a, "EQ-A-001")


@pytest.fixture
def equipment_b(etab_b):
    return _make_equipment(etab_b, "EQ-B-001")


class TestCloisonnementEquipements:
    def test_liste_equipements_cloisonnee(
        self, api_client, admin_a, admin_b, equipment_a, equipment_b
    ):
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/equipment/")
        nums = [e["num_inventaire"] for e in resp.json()]
        assert "EQ-A-001" in nums
        assert "EQ-B-001" not in nums

    def test_detail_equipement_autre_etablissement_404(self, api_client, admin_a, equipment_b):
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get(f"/api/equipment/{equipment_b.id}/")
        assert resp.status_code == 404

    def test_admin_sans_etablissement_voit_tout(self, api_client, equipment_a, equipment_b):
        super_admin = _make_user("super_admin", User.Role.ADMINISTRATEUR, None)
        api_client.force_authenticate(user=super_admin)
        resp = api_client.get("/api/equipment/")
        assert len(resp.json()) == 2


class TestCloisonnementPannes:
    def test_liste_pannes_cloisonnee(self, api_client, admin_a, admin_b, equipment_a, equipment_b):
        Panne.objects.create(
            equipement=equipment_a,
            signale_par=admin_a,
            description_signalement="Panne A",
            statut="SIGNALEE",
        )
        Panne.objects.create(
            equipement=equipment_b,
            signale_par=admin_b,
            description_signalement="Panne B",
            statut="SIGNALEE",
        )
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/pannes/")
        nums = [p["equipement_num"] for p in resp.json()]
        assert "EQ-A-001" in nums
        assert "EQ-B-001" not in nums

    def test_transition_panne_autre_etablissement_404(
        self, api_client, admin_a, admin_b, equipment_b
    ):
        panne_b = Panne.objects.create(
            equipement=equipment_b,
            signale_par=admin_b,
            description_signalement="Panne B",
            statut="SIGNALEE",
        )
        api_client.force_authenticate(user=admin_a)
        resp = api_client.post(f"/api/pannes/{panne_b.id}/qualify/", {}, format="json")
        assert resp.status_code == 404
        panne_b.refresh_from_db()
        assert panne_b.statut == "SIGNALEE"

    def test_workqueue_cloisonnee(self, api_client, admin_a, admin_b, equipment_a, equipment_b):
        Panne.objects.create(
            equipement=equipment_b,
            signale_par=admin_b,
            description_signalement="Panne B",
            statut="SIGNALEE",
        )
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/workqueue/")
        assert resp.json()["total_ouvertes"] == 0

    def test_dashboard_cloisonne(self, api_client, admin_a, equipment_a, equipment_b):
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/dashboard/")
        assert resp.json()["equipements"]["total"] == 1


class TestCloisonnementMaintenance:
    def test_maintenance_cloisonnee(self, api_client, admin_a, admin_b, equipment_a, equipment_b):
        plan = MaintenancePlan.objects.create(
            nom="Plan X", type_equipement="Monitor", frequence="MENSUELLE", delai_jours=30
        )
        MaintenancePreventive.objects.create(
            plan=plan, equipement=equipment_a, statut="PLANIFIEE", date_planifiee="2026-01-01"
        )
        MaintenancePreventive.objects.create(
            plan=plan, equipement=equipment_b, statut="PLANIFIEE", date_planifiee="2026-01-01"
        )
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/maintenance-preventive/")
        assert len(resp.json()) == 1


class TestCloisonnementUtilisateurs:
    def test_admin_a_ne_voit_pas_admin_b(self, api_client, admin_a, admin_b):
        api_client.force_authenticate(user=admin_a)
        resp = api_client.get("/api/users/")
        data = resp.json()
        items = data["results"] if isinstance(data, dict) and "results" in data else data
        usernames = [u["username"] for u in items]
        assert "admin_a" in usernames
        assert "admin_b" not in usernames

    def test_admin_a_ne_peut_pas_desactiver_admin_b(self, api_client, admin_a, admin_b):
        api_client.force_authenticate(user=admin_a)
        resp = api_client.post(f"/api/users/{admin_b.id}/deactivate/")
        assert resp.status_code == 404
        admin_b.refresh_from_db()
        assert admin_b.is_active is True

    def test_creation_utilisateur_force_etablissement_admin(self, api_client, admin_a, etab_b):
        """Un admin d'hôpital A ne peut pas créer un utilisateur rattaché à B."""
        api_client.force_authenticate(user=admin_a)
        resp = api_client.post(
            "/api/users/",
            {
                "username": "tente_b",
                "email": "b@test.com",
                "password": "Test1234!",
                "first_name": "T",
                "last_name": "B",
                "role": "TECHNICIEN",
                "etablissement": etab_b.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        user = User.objects.get(username="tente_b")
        assert user.etablissement == admin_a.etablissement


class TestEtablissementProfil:
    def test_complete_profile_ne_change_pas_etablissement(self, api_client, etab_a, etab_b):
        """La complétion de profil ne permet pas de changer d'établissement."""
        user = _make_user("marie_a", User.Role.TECHNICIEN, etab_a)
        user.profil_complete = False
        user.save()
        api_client.force_authenticate(user=user)
        resp = api_client.post(
            "/api/auth/complete-profile/",
            {
                "matricule": "MAT-1",
                "new_password": "NouveauMot2Passe!",
            },
            format="json",
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        # L'établissement est inchangé — attribué uniquement par l'admin
        assert user.etablissement == etab_a
