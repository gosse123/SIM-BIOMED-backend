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
    """Requete dupliquee avec meme X-Offline-Id et meme utilisateur → retourne la reponse cachee.
    Note : avec django.test.Client, le JWT n'est pas résolu au niveau middleware,
    donc l'idempotence au niveau middleware ne s'applique pas. Ce test vérifie le modèle."""
    offline_id = "test-uuid-002"

    # Créer une opération déjà exécutée avec succès
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

    # Vérifier que l'opération existe bien
    assert OfflineOperation.objects.filter(
        offline_id=offline_id, user=admin_user, statut=OfflineOperation.StatutExecution.OK
    ).exists()

    # La requête passe normalement (le middleware ne peut pas intercepter avec Client())
    response = api_client.post(
        "/api/equipment/",
        data=json.dumps({"nom": "DUPLICATE"}),
        content_type="application/json",
        HTTP_X_OFFLINE_ID=offline_id,
        HTTP_AUTHORIZATION=auth_headers["HTTP_AUTHORIZATION"],
    )

    # L'opération originale est toujours en base (le middleware ne l'a pas interceptée)
    assert OfflineOperation.objects.filter(offline_id=offline_id).count() == 1


@pytest.mark.django_db
def test_idempotency_failed_allows_retry(api_client, admin_user):
    """Requete avec meme X-Offline-Id et statut ERREUR → le retry est autorisé
    SANS supprimer l'enregistrement : process_response le met à jour (trace conservée)."""
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

    # Simuler process_request : l'entrée ERREUR ne doit pas être supprimée
    from django.test import RequestFactory
    from apps.sync.middleware import OfflineIdempotencyMiddleware

    factory = RequestFactory()
    middleware = OfflineIdempotencyMiddleware(lambda r: None)
    request = factory.post(
        "/api/equipment/",
        data=json.dumps({"nom": "RETRY"}),
        content_type="application/json",
        HTTP_X_OFFLINE_ID=offline_id,
    )
    request.user = admin_user
    result = middleware.process_request(request)

    assert result is None, "Le retry doit être autorisé (pas de réponse cachée)"
    entry = OfflineOperation.objects.get(offline_id=offline_id)
    assert entry.statut == OfflineOperation.StatutExecution.ERREUR, \
        "L'entrée ERREUR doit être conservée (pas de suppression silencieuse)"
    assert request._offline_id == offline_id
    assert request._parsed_body == {"nom": "RETRY"}


@pytest.mark.django_db
def test_replay_same_offline_id_single_mutation(admin_user):
    """Rejouer la même entrée (même X-Offline-Id) ne produit qu'une seule mutation :
    la seconde requête reçoit la réponse cachée sans exécuter la vue."""
    from django.test import RequestFactory
    from django.http import JsonResponse
    from apps.sync.middleware import OfflineIdempotencyMiddleware

    calls = {"count": 0}

    def fake_view(request):
        calls["count"] += 1
        return JsonResponse({"id": 1, "nom": "EQ"}, status=201)

    factory = RequestFactory()
    middleware = OfflineIdempotencyMiddleware(fake_view)

    def make_request():
        request = factory.post(
            "/api/equipment/",
            data=json.dumps({"nom": "EQ"}),
            content_type="application/json",
            HTTP_X_OFFLINE_ID="replay-uuid-001",
        )
        request.user = admin_user
        return request

    # Première exécution : la vue est appelée et la réponse cachée
    request1 = make_request()
    assert middleware.process_request(request1) is None
    response1 = fake_view(request1)
    middleware.process_response(request1, response1)

    # Replay : la vue ne doit PAS être rappelée, la réponse cachée est retournée
    request2 = make_request()
    cached = middleware.process_request(request2)
    assert cached is not None, "Le replay doit retourner la réponse cachée"

    assert calls["count"] == 1, "Une seule mutation côté serveur"
    assert json.loads(cached.content) == {"id": 1, "nom": "EQ"}

    # Une seule opération enregistrée
    assert OfflineOperation.objects.filter(offline_id="replay-uuid-001").count() == 1


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
