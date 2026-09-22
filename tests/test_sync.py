import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from apps.sync.models import OfflineOperation
import json

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="admin_sync",
        email="admin@sync.test",
        password="AdminPass123!",
        first_name="Admin",
        last_name="Sync",
        role=User.Role.ADMINISTRATEUR,
    )


@pytest.fixture
def tech_user():
    return User.objects.create_user(
        username="tech_sync",
        email="tech@sync.test",
        password="TechPass123!",
        first_name="Tech",
        last_name="Sync",
        role=User.Role.TECHNICIEN,
    )


@pytest.fixture
def auth_headers(admin_user):
    refresh = RefreshToken.for_user(admin_user)
    return {
        "HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}",
        "CONTENT_TYPE": "application/json",
    }


@pytest.fixture
def tech_headers(tech_user):
    refresh = RefreshToken.for_user(tech_user)
    return {
        "HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}",
        "CONTENT_TYPE": "application/json",
    }


@pytest.mark.django_db
def test_sync_status_admin_ok(api_client, auth_headers):
    response = api_client.get("/api/sync/status/", **auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "pending" in data
    assert "recent_ok_24h" in data
    assert "recent_errors_24h" in data


@pytest.mark.django_db
def test_sync_status_non_admin_forbidden(api_client, tech_headers):
    response = api_client.get("/api/sync/status/", **tech_headers)
    assert response.status_code == 403


@pytest.mark.django_db
def test_idempotency_first_request_proceeds(api_client, admin_user, auth_headers):
    """Premiere requete avec un X-Offline-Id → executée normalement."""
    offline_id = "test-uuid-001"

    # Simuler un POST equipment (sans verifier la validite du payload)
    response = api_client.post(
        "/api/equipment/",
        data=json.dumps({"nom": "Test", "num_inventaire": "T001"}),
        content_type="application/json",
        HTTP_X_OFFLINE_ID=offline_id,
        HTTP_AUTHORIZATION=auth_headers["HTTP_AUTHORIZATION"],
    )

    # L'operation devrait etre trackee
    op = OfflineOperation.objects.get(offline_id=offline_id)
    assert op.method == "POST"
    assert op.url == "/api/equipment/"


@pytest.mark.django_db
def test_idempotency_duplicate_returns_cached(api_client, admin_user, auth_headers):
    """Requete dupliquee avec meme X-Offline-Id → retourne la reponse cachee."""
    offline_id = "test-uuid-002"

    # Creer une operation deja executee avec succes
    OfflineOperation.objects.create(
        offline_id=offline_id,
        user=admin_user,
        method="POST",
        url="/api/equipment/",
        body={"nom": "EXISTING"},
        statut=OfflineOperation.StatutExecution.OK,
        response_status=201,
        response_body={"id": 42, "nom": "EXISTING"},
    )

    # Envoyer la meme requete
    response = api_client.post(
        "/api/equipment/",
        data=json.dumps({"nom": "DUPLICATE"}),
        content_type="application/json",
        HTTP_X_OFFLINE_ID=offline_id,
        HTTP_AUTHORIZATION=auth_headers["HTTP_AUTHORIZATION"],
    )

    assert response.status_code == 201
    data = json.loads(response.content)
    assert data["id"] == 42
    assert data["nom"] == "EXISTING"


@pytest.mark.django_db
def test_idempotency_failed_allows_retry(api_client, admin_user, auth_headers):
    """Requete avec meme X-Offline-Id et statut ERREUR → supprime l'ancienne entree et autorise le retry."""
    offline_id = "test-uuid-003"

    OfflineOperation.objects.create(
        offline_id=offline_id,
        user=admin_user,
        method="POST",
        url="/api/equipment/",
        body={"nom": "BAD"},
        statut=OfflineOperation.StatutExecution.ERREUR,
        response_status=400,
        response_body={"detail": "Bad request"},
        error_message="Bad request",
    )

    response = api_client.post(
        "/api/equipment/",
        data=json.dumps({"nom": "RETRY"}),
        content_type="application/json",
        HTTP_X_OFFLINE_ID=offline_id,
        HTTP_AUTHORIZATION=auth_headers["HTTP_AUTHORIZATION"],
    )

    # L'ancienne entree est supprimee, la requete est reexecutee
    # (elle peut echouer a nouveau si les donnees sont invalides, mais l'ancienne erreur est purgée)
    old_entry = OfflineOperation.objects.filter(
        offline_id=offline_id,
        statut=OfflineOperation.StatutExecution.ERREUR,
        error_message="Bad request",
    )
    assert not old_entry.exists(), "L'ancienne entree ERREUR devrait etre supprimee"


@pytest.mark.django_db
def test_no_offline_id_proceeds_normally(api_client, auth_headers):
    """Sans X-Offline-Id, la requete se comporte normalement (pas d'idempotence)."""
    response = api_client.get("/api/sync/status/", **auth_headers)
    assert response.status_code == 200
    assert OfflineOperation.objects.count() == 0


@pytest.mark.django_db
def test_retry_failed_admin_ok(api_client, admin_user, auth_headers):
    """Admin peut supprimer les operations en erreur pour permettre le retry."""
    # Creer des operations en erreur
    OfflineOperation.objects.create(
        offline_id="fail-001",
        user=admin_user,
        method="POST",
        url="/api/equipment/",
        statut=OfflineOperation.StatutExecution.ERREUR,
        response_status=500,
        error_message="Server error",
    )
    OfflineOperation.objects.create(
        offline_id="fail-002",
        user=admin_user,
        method="POST",
        url="/api/pannes/",
        statut=OfflineOperation.StatutExecution.ERREUR,
        response_status=400,
        error_message="Validation error",
    )

    response = api_client.post("/api/sync/retry/", **auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2

    # Verifier qu'elles sont supprimees
    assert OfflineOperation.objects.filter(
        statut=OfflineOperation.StatutExecution.ERREUR
    ).count() == 0


@pytest.mark.django_db
def test_retry_failed_non_admin_forbidden(api_client, tech_headers):
    response = api_client.post("/api/sync/retry/", **tech_headers)
    assert response.status_code == 403


@pytest.mark.django_db
def test_offline_id_get_request_ignored(api_client, auth_headers):
    """GET avec X-Offline-Id n'est pas traite par le middleware."""
    response = api_client.get(
        "/api/sync/status/",
        HTTP_X_OFFLINE_ID="test-get-001",
        **auth_headers,
    )
    assert response.status_code == 200
    assert OfflineOperation.objects.count() == 0
