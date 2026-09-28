import json
import logging

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class OfflineIdempotencyMiddleware(MiddlewareMixin):
    """Middleware d'idempotence pour les opérations hors ligne.

    Si la requête contient un header X-Offline-Id :
    1. Vérifie si cette opération a déjà été exécutée (par cet utilisateur)
    2. Si oui, retourne la réponse cachée (idempotence)
    3. Si non, execute la requête et stocke le résultat

    L'idempotence est isolée par utilisateur : deux utilisateurs peuvent
    réutiliser le même X-Offline-Id sans conflit."""

    # Seules les méthodes de mutation sont concernées
    MUTATION_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

    def process_request(self, request):
        offline_id = request.META.get("HTTP_X_OFFLINE_ID")
        if not offline_id:
            return None  # Pas d'ID offline, continuer normalement

        if request.method not in self.MUTATION_METHODS:
            return None

        # Parser le corps JSON une seule fois pour l'archiver avec l'opération
        try:
            request._parsed_body = (
                json.loads(request.body.decode("utf-8")) if request.body else None
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            request._parsed_body = None

        # Import lazy pour éviter les circulaires
        from apps.sync.models import OfflineOperation

        # Si l'utilisateur n'est pas encore résolu (JWT non décodé), on ne peut pas
        # faire de vérification d'idempotence. On passe et on stockera en process_response.
        if not request.user.is_authenticated:
            request._offline_id = offline_id
            return None

        # Rechercher par (utilisateur, offline_id)
        existing = OfflineOperation.objects.filter(
            offline_id=offline_id,
            user=request.user,
        ).first()

        if existing is None:
            # Première exécution, stocker l'ID pour traitement
            request._offline_id = offline_id
            return None

        # Opération déjà exécutée — retourner la réponse cachée
        if existing.statut == OfflineOperation.StatutExecution.OK:
            logger.info(f"Idempotence offline : {offline_id} déjà traité, retour du cache")
            return JsonResponse(
                existing.response_body or {}, status=existing.response_status or 200
            )

        # Statut ERREUR ou EN_COURS bloqué — autoriser le retry SANS supprimer
        # l'enregistrement : process_response le mettra à jour via update_or_create,
        # ce qui conserve la trace (pas de suppression silencieuse du journal).
        logger.warning(
            f"Idempotence offline : {offline_id} en statut {existing.statut}, retry autorisé"
        )
        request._offline_id = offline_id
        return None

    def process_response(self, request, response):
        offline_id = getattr(request, "_offline_id", None)
        if not offline_id:
            return response

        if request.method not in self.MUTATION_METHODS:
            return response

        if not request.user.is_authenticated:
            return response

        from apps.sync.models import OfflineOperation

        try:
            response_body = json.loads(response.content.decode("utf-8")) if response.content else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_body = {"raw": response.content.decode("utf-8", errors="replace")}

        statut = (
            OfflineOperation.StatutExecution.OK
            if 200 <= response.status_code < 400
            else OfflineOperation.StatutExecution.ERREUR
        )

        OfflineOperation.objects.update_or_create(
            user=request.user,
            offline_id=offline_id,
            defaults={
                "method": request.method,
                "url": request.path,
                "body": getattr(request, "_parsed_body", None),
                "statut": statut,
                "response_status": response.status_code,
                "response_body": response_body,
                "error_message": ""
                if statut == OfflineOperation.StatutExecution.OK
                else str(response_body),
            },
        )

        return response
