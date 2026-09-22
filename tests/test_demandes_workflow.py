import pytest
from django.test import Client
from apps.accounts.models import User, Etablissement, DemandeAcces, Notification


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def etab():
    return Etablissement.objects.create(nom="Site Central", adresse="123 Rue Test")


@pytest.fixture
def admin_user(etab):
    return User.objects.create_user(
        username="admin_demande",
        email="admin@demande.com",
        password="Admin123!",
        role=User.Role.ADMINISTRATEUR,
        etablissement=etab,
    )


@pytest.fixture
def biomed_user(etab):
    return User.objects.create_user(
        username="biomed_demande",
        email="biomed@demande.com",
        password="Biomed123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
        etablissement=etab,
    )


@pytest.fixture
def tech_user(etab):
    return User.objects.create_user(
        username="tech_demande",
        email="tech@demande.com",
        password="Tech123!",
        role=User.Role.TECHNICIEN,
        etablissement=etab,
    )


def _login(client, username, password):
    resp = client.post("/api/auth/login/", {"username": username, "password": password}, content_type="application/json")
    return resp.json()["access"]


def _get_temp_password(user):
    """Extract the temporary password from the user's notification."""
    notif = user.notifications.order_by("-date_creation").first()
    assert notif, f"Aucune notification pour {user.username}"
    # Message format: ...Mot de passe temporaire : <password>\n\n...
    for line in notif.message.split("\n"):
        if line.startswith("Mot de passe temporaire :"):
            return line.split(":", 1)[1].strip()
    pytest.fail(f"Mot de passe temporaire introuvable dans : {notif.message}")


# ======================== Request Access ========================

@pytest.mark.django_db
class TestRequestAccess:
    def test_submit_demande_success(self, api_client):
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Jean Dupont",
            "email": "jean@hospital.com",
            "role_souhaite": "TECHNICIEN",
            "justification": "Je suis technicien biomédical.",
            "service": "Biomedical",
        }, content_type="application/json")
        assert resp.status_code == 201
        assert DemandeAcces.objects.filter(email="jean@hospital.com").exists()

    def test_submit_demande_duplicate_email_pending(self, api_client):
        api_client.post("/api/auth/request-access/", {
            "nom_complet": "Jean Dupont",
            "email": "dup@hospital.com",
            "role_souhaite": "TECHNICIEN",
            "justification": "Test",
        }, content_type="application/json")
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Jean Autre",
            "email": "dup@hospital.com",
            "role_souhaite": "PERSONNEL_SOIGNANT",
            "justification": "Test 2",
        }, content_type="application/json")
        assert resp.status_code == 400

    def test_submit_demande_existing_user_email(self, api_client, tech_user):
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Test",
            "email": tech_user.email,
            "role_souhaite": "TECHNICIEN",
            "justification": "Test",
        }, content_type="application/json")
        assert resp.status_code == 400

    def test_submit_demande_admin_role_forbidden(self, api_client):
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Hack Admin",
            "email": "hack@hospital.com",
            "role_souhaite": "ADMINISTRATEUR",
            "justification": "Want admin",
        }, content_type="application/json")
        assert resp.status_code == 400

    def test_submit_demande_biomed_role_forbidden(self, api_client):
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Hack Biomed",
            "email": "hack2@hospital.com",
            "role_souhaite": "RESPONSABLE_BIOMEDICAL",
            "justification": "Want biomed",
        }, content_type="application/json")
        assert resp.status_code == 400

    def test_submit_demande_missing_fields(self, api_client):
        resp = api_client.post("/api/auth/request-access/", {}, content_type="application/json")
        assert resp.status_code == 400


# ======================== Admin List Demandes ========================

@pytest.mark.django_db
class TestListDemandes:
    def _create_demande(self, api_client, email="test@h.com"):
        api_client.post("/api/auth/request-access/", {
            "nom_complet": "Test User",
            "email": email,
            "role_souhaite": "TECHNICIEN",
            "justification": "Test",
        }, content_type="application/json")

    def test_admin_can_list_demandes(self, api_client, admin_user):
        self._create_demande(api_client, "a@h.com")
        self._create_demande(api_client, "b@h.com")
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.get("/api/demandes/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        count = data["count"] if isinstance(data, dict) else len(data)
        assert count >= 2

    def test_admin_can_filter_by_statut(self, api_client, admin_user):
        self._create_demande(api_client, "c@h.com")
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.get("/api/demandes/?statut=EN_ATTENTE", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200

    def test_biomed_cannot_list_demandes(self, api_client, biomed_user):
        token = _login(api_client, "biomed_demande", "Biomed123!")
        resp = api_client.get("/api/demandes/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_tech_cannot_list_demandes(self, api_client, tech_user):
        token = _login(api_client, "tech_demande", "Tech123!")
        resp = api_client.get("/api/demandes/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403


# ======================== Approve / Reject ========================

@pytest.mark.django_db
class TestApproveDemande:
    def _create_demande(self, api_client, email="approve@h.com"):
        api_client.post("/api/auth/request-access/", {
            "nom_complet": "Approuver Test",
            "email": email,
            "role_souhaite": "TECHNICIEN",
            "justification": "Je veux être tech.",
            "service": "Cardiologie",
        }, content_type="application/json")
        return DemandeAcces.objects.get(email=email)

    def test_admin_can_approve(self, api_client, admin_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200

        # Vérifier que l'utilisateur a été créé
        demande.refresh_from_db()
        assert demande.statut == DemandeAcces.Statut.APPROUVEE
        assert User.objects.filter(email="approve@h.com").exists()

        # Vérifier la notification
        user = User.objects.get(email="approve@h.com")
        assert Notification.objects.filter(destinataire=user, titre__contains="approuvée").exists()

    def test_admin_cannot_approve_twice(self, api_client, admin_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "admin_demande", "Admin123!")
        api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 400

    def test_biomed_cannot_approve(self, api_client, biomed_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "biomed_demande", "Biomed123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_approve_nonexistent_returns_404(self, api_client, admin_user):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post("/api/demandes/99999/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 404

    def test_approved_user_has_profil_complete_false(self, api_client, admin_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "admin_demande", "Admin123!")
        api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        user = User.objects.get(email="approve@h.com")
        assert user.profil_complete is False
        assert user.is_active is True


@pytest.mark.django_db
class TestRejectDemande:
    def _create_demande(self, api_client, email="reject@h.com"):
        api_client.post("/api/auth/request-access/", {
            "nom_complet": "Rejeter Test",
            "email": email,
            "role_souhaite": "PERSONNEL_SOIGNANT",
            "justification": "Je veux être soignant.",
        }, content_type="application/json")
        return DemandeAcces.objects.get(email=email)

    def test_admin_can_reject(self, api_client, admin_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/reject/", {
            "motif": "Profil non qualifié.",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        demande.refresh_from_db()
        assert demande.statut == DemandeAcces.Statut.REFUSEE
        assert demande.motif_rejet == "Profil non qualifié."

    def test_admin_can_reject_without_motif(self, api_client, admin_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/reject/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        demande.refresh_from_db()
        assert demande.statut == DemandeAcces.Statut.REFUSEE

    def test_biomed_cannot_reject(self, api_client, biomed_user):
        demande = self._create_demande(api_client)
        token = _login(api_client, "biomed_demande", "Biomed123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/reject/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403


# ======================== Notifications ========================

@pytest.mark.django_db
class TestNotifications:
    def _create_approved_user(self, api_client, admin_user, email="notif@h.com"):
        api_client.post("/api/auth/request-access/", {
            "nom_complet": "Notif Test",
            "email": email,
            "role_souhaite": "TECHNICIEN",
            "justification": "Test",
        }, content_type="application/json")
        demande = DemandeAcces.objects.get(email=email)
        token = _login(api_client, "admin_demande", "Admin123!")
        api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token}")
        return User.objects.get(email=email)

    def test_user_can_list_notifications(self, api_client, admin_user):
        user = self._create_approved_user(api_client, admin_user)
        token = _login(api_client, user.username, _get_temp_password(user))
        resp = api_client.get("/api/notifications/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        assert resp.json()["non_lues"] >= 1

    def test_user_can_mark_notification_read(self, api_client, admin_user):
        user = self._create_approved_user(api_client, admin_user)
        notif = user.notifications.first()
        token = _login(api_client, user.username, _get_temp_password(user))
        resp = api_client.post(f"/api/notifications/{notif.id}/read/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.lu is True

    def test_user_can_mark_all_read(self, api_client, admin_user):
        user = self._create_approved_user(api_client, admin_user)
        token = _login(api_client, user.username, _get_temp_password(user))
        resp = api_client.post("/api/notifications/read-all/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        assert user.notifications.filter(lu=False).count() == 0

    def test_unauthenticated_cannot_list_notifications(self, api_client):
        resp = api_client.get("/api/notifications/")
        assert resp.status_code == 401


# ======================== Profile Completion ========================

@pytest.mark.django_db
class TestProfileCompletion:
    def test_uncomplete_profile_returns_false(self, api_client, admin_user):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.get("/api/auth/profile-complete/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        # admin_user was created directly, profil_complete defaults to False
        assert resp.json()["profil_complete"] is False

    def test_complete_profile_success(self, api_client, admin_user, etab):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post("/api/auth/complete-profile/", {
            "matricule": "MAT-001",
            "etablissement": etab.id,
            "service": "Cardiologie",
            "new_password": "NouveauMot2024!",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.profil_complete is True
        assert admin_user.matricule == "MAT-001"

    def test_complete_profile_already_complete(self, api_client, admin_user, etab):
        admin_user.profil_complete = True
        admin_user.save()
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post("/api/auth/complete-profile/", {
            "matricule": "MAT-002",
            "etablissement": etab.id,
            "new_password": "NouveauMot2024!",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 400

    def test_complete_profile_missing_matricule(self, api_client, admin_user, etab):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post("/api/auth/complete-profile/", {
            "etablissement": etab.id,
            "new_password": "NouveauMot2024!",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 400

    def test_complete_profile_invalid_etablissement(self, api_client, admin_user):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post("/api/auth/complete-profile/", {
            "matricule": "MAT-003",
            "etablissement": 99999,
            "new_password": "NouveauMot2024!",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 400

    def test_unauthenticated_cannot_complete_profile(self, api_client, etab):
        resp = api_client.post("/api/auth/complete-profile/", {
            "matricule": "MAT-004",
            "etablissement": etab.id,
            "new_password": "NouveauMot2024!",
        }, content_type="application/json")
        assert resp.status_code == 401


# ======================== Etablissements List ========================

@pytest.mark.django_db
class TestEtablissementsList:
    def test_list_active_etablissements(self, api_client, admin_user, etab):
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.get("/api/auth/etablissements/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        noms = [e["nom"] for e in data]
        assert etab.nom in noms

    def test_inactive_etablissement_not_listed(self, api_client, admin_user):
        Etablissement.objects.create(nom="Fermé", actif=False)
        token = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.get("/api/auth/etablissements/", HTTP_AUTHORIZATION=f"Bearer {token}")
        data = resp.json()
        assert not any(e["nom"] == "Fermé" for e in data)


# ======================== Full Workflow E2E ========================

@pytest.mark.django_db
class TestFullWorkflowE2E:
    def test_complete_lifecycle(self, api_client, admin_user, etab):
        """Test complet : demande → admin approuve → user se connecte → complète profil."""
        # 1. Soumettre la demande
        resp = api_client.post("/api/auth/request-access/", {
            "nom_complet": "Marie Curie",
            "email": "marie@hospital.com",
            "role_souhaite": "TECHNICIEN",
            "justification": "Technicienne biomédicale expérimentée.",
            "service": "Radiologie",
        }, content_type="application/json")
        assert resp.status_code == 201
        demande = DemandeAcces.objects.get(email="marie@hospital.com")
        assert demande.statut == DemandeAcces.Statut.EN_ATTENTE

        # 2. Admin approuve
        token_admin = _login(api_client, "admin_demande", "Admin123!")
        resp = api_client.post(f"/api/demandes/{demande.id}/approve/", HTTP_AUTHORIZATION=f"Bearer {token_admin}")
        assert resp.status_code == 200
        user = User.objects.get(email="marie@hospital.com")
        assert user.username == "marie"  # email prefix
        assert user.profil_complete is False

        # 3. Notification créée
        assert Notification.objects.filter(destinataire=user, titre__contains="approuvée").exists()

        # 4. User se connecte
        token_user = _login(api_client, "marie", _get_temp_password(user))
        resp = api_client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token_user}")
        assert resp.status_code == 200
        assert resp.json()["profil_complete"] is False

        # 5. Vérifie profil pas complet
        resp = api_client.get("/api/auth/profile-complete/", HTTP_AUTHORIZATION=f"Bearer {token_user}")
        assert resp.json()["profil_complete"] is False

        # 6. Complète le profil
        resp = api_client.post("/api/auth/complete-profile/", {
            "matricule": "NUR-123",
            "etablissement": etab.id,
            "service": "Radiologie",
            "new_password": "NouveauMot2024!",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token_user}")
        assert resp.status_code == 200

        # 7. Vérifie profil complet
        resp = api_client.get("/api/auth/profile-complete/", HTTP_AUTHORIZATION=f"Bearer {token_user}")
        assert resp.json()["profil_complete"] is True
