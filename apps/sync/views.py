from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from .models import OfflineOperation


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sync_status(request):
    """Retourne l'etat de la file de synchronisation."""
    if request.user.role != "ADMINISTRATEUR":
        return Response(
            {"detail": "Seuls les administrateurs peuvent consulter le statut de sync."},
            status=status.HTTP_403_FORBIDDEN,
        )

    pending = OfflineOperation.objects.filter(
        statut=OfflineOperation.StatutExecution.EN_COURS
    ).count()
    recent_errors = OfflineOperation.objects.filter(
        statut=OfflineOperation.StatutExecution.ERREUR,
        executed_at__gte=timezone.now() - timedelta(hours=24),
    ).count()
    recent_ok = OfflineOperation.objects.filter(
        statut=OfflineOperation.StatutExecution.OK,
        executed_at__gte=timezone.now() - timedelta(hours=24),
    ).count()

    return Response({
        "pending": pending,
        "recent_ok_24h": recent_ok,
        "recent_errors_24h": recent_errors,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_failed(request):
    """Supprime les operations en erreur des dernieres 24h pour permettre au client de les renvoyer."""
    if request.user.role != "ADMINISTRATEUR":
        return Response(
            {"detail": "Seuls les administrateurs peuvent relancer les operations."},
            status=status.HTTP_403_FORBIDDEN,
        )

    failed = OfflineOperation.objects.filter(
        statut=OfflineOperation.StatutExecution.ERREUR,
        executed_at__gte=timezone.now() - timedelta(hours=24),
    )

    # Collect info before deleting
    operations = [
        {"offline_id": op.offline_id, "method": op.method, "url": op.url}
        for op in failed
    ]
    count = failed.count()

    # Delete so the middleware won't block retries with the same X-Offline-Id
    failed.delete()

    return Response({
        "detail": f"{count} operation(s) supprimée(s). Le client peut maintenant les renvoyer.",
        "count": count,
        "operations": operations,
    })
