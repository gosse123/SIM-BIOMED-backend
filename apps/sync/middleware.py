import json
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class OfflineIdempotencyMiddleware(MiddlewareMixin):
    """
    Middleware d'idempotence pour les operations hors ligne.

    Si la requete contient un header X-Offline-Id :
    1. Verifie si cette operation a deja ete executee
    2. Si oui, retourne la reponse cachee (idempotence)
    3. Si non, execute la requete et stocke le resultat
    """

    # Seules les methodes de mutation sont concernees
    MUTATION_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

    def process_request(self, request):
        offline_id = request.META.get("HTTP_X_OFFLINE_ID")
        if not offline_id:
            return None  # Pas d'ID offline, continuer normalement

        if request.method not in self.MUTATION_METHODS:
            return None

        # Lazy import pour eviter les circulaires
        from apps.sync.models import OfflineOperation

        try:
            existing = OfflineOperation.objects.get(offline_id=offline_id)
        except OfflineOperation.DoesNotExist:
            # Premiere execution, stocker l'ID pour traitement
            request._offline_id = offline_id
            return None

        # Operation deja executee — retourner la reponse cachee
        if existing.statut == OfflineOperation.StatutExecution.OK:
            logger.info(f"Offline idempotence: {offline_id} deja traite, retour cache")
            return JsonResponse(existing.response_body or {}, status=existing.response_status or 200)

        if existing.statut == OfflineOperation.StatutExecution.ERREUR:
            logger.info(f"Offline idempotence: {offline_id} en erreur, permettre le retry")
            # Delete the old failed entry so this request proceeds as new
            existing.delete()
            request._offline_id = offline_id
            return None

        # Statut EN_COURS — operation probably stuck (process crashed). Allow retry.
        logger.warning(f"Offline idempotence: {offline_id} en cours bloqué, autorise le retry")
        existing.delete()
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
            offline_id=offline_id,
            defaults={
                "user": request.user,
                "method": request.method,
                "url": request.path,
                "body": getattr(request, "_parsed_body", None),
                "statut": statut,
                "response_status": response.status_code,
                "response_body": response_body,
                "error_message": "" if statut == OfflineOperation.StatutExecution.OK else str(response_body),
            },
        )

        return response
