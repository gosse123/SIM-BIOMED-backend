import pytest
from django.test import Client

from apps.accounts.models import Etablissement, User


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def etab():
    return Etablissement.objects.create(nom="Site Central", adresse="123 Rue Test")


@pytest.fixture
def admin_user(etab):
    return User.objects.create_user(
        username="admin_rbac",
        email="admin@test.com",
        password="Admin123!",
        role=User.Role.ADMINISTRATEUR,
        etablissement=etab,
    )


@pytest.fixture
def biomed_user(etab):
    return User.objects.create_user(
        username="biomed_rbac",
        email="biomed@test.com",
        password="Biomed123!",
        role=User.Role.RESPONSABLE_BIOMEDICAL,
        etablissement=etab,
    )


@pytest.fixture
def tech_user(etab):
    return User.objects.create_user(
        username="tech_rbac",
        email="tech@test.com",
        password="Tech123!",
        role=User.Role.TECHNICIEN,
        etablissement=etab,
    )


@pytest.fixture
def soignant_user(etab):
    return User.objects.create_user(
        username="soignant_rbac",
        email="soignant@test.com",
        password="Soignant123!",
        role=User.Role.PERSONNEL_SOIGNANT,
        etablissement=etab,
    )


@pytest.fixture
def direction_user(etab):
    return User.objects.create_user(
        username="direction_rbac",
        email="direction@test.com",
        password="Direction123!",
        role=User.Role.DIRECTION,
        etablissement=etab,
    )


def _login(client, username, password):
    resp = client.post(
        "/api/auth/login/",
        {"username": username, "password": password},
        content_type="application/json",
    )
    return resp.json()["access"]


# ======================== UserViewSet ========================


@pytest.mark.django_db
class TestUserViewSetList:
    def test_admin_can_list_users(self, api_client, admin_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.get("/api/users/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        # May be paginated dict or plain list
        count = data["count"] if isinstance(data, dict) else len(data)
        assert count >= 1

    def test_biomed_cannot_list_users(self, api_client, biomed_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.get("/api/users/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_tech_cannot_list_users(self, api_client, tech_user):
        token = _login(api_client, "tech_rbac", "Tech123!")
        resp = api_client.get("/api/users/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_soignant_cannot_list_users(self, api_client, soignant_user):
        token = _login(api_client, "soignant_rbac", "Soignant123!")
        resp = api_client.get("/api/users/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_direction_cannot_list_users(self, api_client, direction_user):
        token = _login(api_client, "direction_rbac", "Direction123!")
        resp = api_client.get("/api/users/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list_users(self, api_client):
        resp = api_client.get("/api/users/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestUserViewSetCreate:
    def test_admin_can_create_user(self, api_client, admin_user, etab):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            "/api/users/",
            {
                "username": "new_tech",
                "email": "new@test.com",
                "password": "NewTech123!",
                "first_name": "New",
                "last_name": "Tech",
                "role": User.Role.TECHNICIEN,
                "etablissement": etab.id,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "new_tech"

    def test_biomed_cannot_create_user(self, api_client, biomed_user, etab):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.post(
            "/api/users/",
            {
                "username": "fail_tech",
                "email": "fail@test.com",
                "password": "FailTech123!",
                "role": User.Role.TECHNICIEN,
                "etablissement": etab.id,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestUserViewSetRetrieve:
    def test_admin_can_get_user_detail(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.get(f"/api/users/{tech_user.id}/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        assert resp.json()["username"] == "tech_rbac"

    def test_biomed_cannot_get_user_detail(self, api_client, biomed_user, tech_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.get(f"/api/users/{tech_user.id}/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestUserViewSetUpdate:
    def test_admin_can_update_user(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.patch(
            f"/api/users/{tech_user.id}/",
            {
                "first_name": "Updated",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Updated"

    def test_biomed_cannot_update_user(self, api_client, biomed_user, tech_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.patch(
            f"/api/users/{tech_user.id}/",
            {
                "first_name": "Hacked",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestUserViewSetDelete:
    def test_admin_can_delete_user(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.delete(
            f"/api/users/{tech_user.id}/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 204

    def test_biomed_cannot_delete_user(self, api_client, biomed_user, tech_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.delete(
            f"/api/users/{tech_user.id}/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 403


# ======================== Deactivate User ========================


@pytest.mark.django_db
class TestDeactivateUser:
    def test_admin_can_deactivate_user(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            f"/api/users/{tech_user.id}/deactivate/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 200
        tech_user.refresh_from_db()
        assert tech_user.is_active is False

    def test_admin_cannot_deactivate_self(self, api_client, admin_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            f"/api/users/{admin_user.id}/deactivate/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 400

    def test_biomed_cannot_deactivate_user(self, api_client, biomed_user, tech_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.post(
            f"/api/users/{tech_user.id}/deactivate/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 403

    def test_deactivate_nonexistent_returns_404(self, api_client, admin_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post("/api/users/99999/deactivate/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 404


# ======================== Set Role ========================


@pytest.mark.django_db
class TestSetRole:
    def test_admin_can_change_role(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            f"/api/users/{tech_user.id}/set-role/",
            {
                "role": User.Role.RESPONSABLE_BIOMEDICAL,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        tech_user.refresh_from_db()
        assert tech_user.role == User.Role.RESPONSABLE_BIOMEDICAL

    def test_admin_cannot_change_own_role(self, api_client, admin_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            f"/api/users/{admin_user.id}/set-role/",
            {
                "role": User.Role.TECHNICIEN,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 403

    def test_biomed_cannot_change_role(self, api_client, biomed_user, tech_user):
        token = _login(api_client, "biomed_rbac", "Biomed123!")
        resp = api_client.post(
            f"/api/users/{tech_user.id}/set-role/",
            {
                "role": User.Role.PERSONNEL_SOIGNANT,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 403

    def test_set_role_nonexistent_returns_404(self, api_client, admin_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            "/api/users/99999/set-role/",
            {
                "role": User.Role.TECHNICIEN,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 404

    def test_invalid_role_returns_400(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        resp = api_client.post(
            f"/api/users/{tech_user.id}/set-role/",
            {
                "role": "INVALID_ROLE",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 400


# ======================== Register Restriction ========================


@pytest.mark.django_db
class TestRegisterRestriction:
    def test_register_admin_role_forbidden(self, api_client):
        resp = api_client.post(
            "/api/auth/register/",
            {
                "username": "new_admin",
                "email": "newadmin@test.com",
                "password": "Admin123!",
                "role": User.Role.ADMINISTRATEUR,
            },
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_biomed_role_forbidden(self, api_client):
        resp = api_client.post(
            "/api/auth/register/",
            {
                "username": "new_biomed",
                "email": "newbiomed@test.com",
                "password": "Biomed123!",
                "role": User.Role.RESPONSABLE_BIOMEDICAL,
            },
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_tech_role_allowed(self, api_client):
        resp = api_client.post(
            "/api/auth/register/",
            {
                "username": "reg_tech",
                "email": "regtech@test.com",
                "password": "Tech123!",
                "role": User.Role.TECHNICIEN,
            },
            content_type="application/json",
        )
        assert resp.status_code == 201

    def test_register_soignant_role_allowed(self, api_client):
        resp = api_client.post(
            "/api/auth/register/",
            {
                "username": "reg_soignant",
                "email": "regsoignant@test.com",
                "password": "Soignant123!",
                "role": User.Role.PERSONNEL_SOIGNANT,
            },
            content_type="application/json",
        )
        assert resp.status_code == 201


# ======================== Change Password ========================


@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self, api_client, tech_user):
        token = _login(api_client, "tech_rbac", "Tech123!")
        resp = api_client.post(
            "/api/auth/change-password/",
            {
                "old_password": "Tech123!",
                "new_password": "NewTech456!",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        # Verify new password works
        resp2 = api_client.post(
            "/api/auth/login/",
            {"username": "tech_rbac", "password": "NewTech456!"},
            content_type="application/json",
        )
        assert resp2.status_code == 200

    def test_change_password_wrong_old(self, api_client, tech_user):
        token = _login(api_client, "tech_rbac", "Tech123!")
        resp = api_client.post(
            "/api/auth/change-password/",
            {
                "old_password": "WrongPass!",
                "new_password": "NewTech456!",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 400


# ======================== Etablissement ========================


@pytest.mark.django_db
class TestEtablissementCourant:
    def test_user_with_etab_returns_200(self, api_client, tech_user):
        token = _login(api_client, "tech_rbac", "Tech123!")
        resp = api_client.get("/api/auth/etablissement/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        assert resp.json()["nom"] == "Site Central"

    def test_user_without_etab_returns_404(self, api_client):
        User.objects.create_user(
            username="noetab",
            email="noetab@test.com",
            password="Noetab123!",
            role=User.Role.TECHNICIEN,
        )
        token = _login(api_client, "noetab", "Noetab123!")
        resp = api_client.get("/api/auth/etablissement/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get("/api/auth/etablissement/")
        assert resp.status_code == 401


# ======================== Audit Logs ========================


@pytest.mark.django_db
class TestAuditLogs:
    def test_user_create_creates_audit_log(self, api_client, admin_user, etab):
        token = _login(api_client, "admin_rbac", "Admin123!")
        api_client.post(
            "/api/users/",
            {
                "username": "audit_target",
                "email": "audit@test.com",
                "password": "Audit123!",
                "role": User.Role.TECHNICIEN,
                "etablissement": etab.id,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        from apps.audit.models import AuditLog

        logs = AuditLog.objects.filter(action="user.create")
        assert logs.exists()
        log = logs.first()
        assert log.utilisateur == admin_user
        assert log.entite == "User"

    def test_deactivate_creates_audit_log(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        api_client.post(
            f"/api/users/{tech_user.id}/deactivate/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        from apps.audit.models import AuditLog

        logs = AuditLog.objects.filter(action="user.deactivate")
        assert logs.exists()

    def test_set_role_creates_audit_log(self, api_client, admin_user, tech_user):
        token = _login(api_client, "admin_rbac", "Admin123!")
        api_client.post(
            f"/api/users/{tech_user.id}/set-role/",
            {
                "role": User.Role.PERSONNEL_SOIGNANT,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        from apps.audit.models import AuditLog

        logs = AuditLog.objects.filter(action="user.role_change")
        assert logs.exists()
        log = logs.first()
        assert log.ancienne_valeur["role"] == "TECHNICIEN"
        assert log.nouvelle_valeur["role"] == "PERSONNEL_SOIGNANT"
